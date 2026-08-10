"""Generic S3 content-addressed original-object boundary."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


BUCKET_RE = re.compile(r"^(?=.{3,63}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
PUBLIC_GRANTEE_URIS = frozenset(
    {
        "http://acs.amazonaws.com/groups/global/AllUsers",
        "http://acs.amazonaws.com/groups/global/AuthenticatedUsers",
    }
)


class ObjectStoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class ObjectStoreConfig:
    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"

    def validate(self) -> None:
        parsed = urlparse(self.endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ObjectStoreError("object_config_invalid", "S3 endpoint must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ObjectStoreError("object_config_invalid", "S3 endpoint must not contain credentials, paths, queries, or fragments")
        if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
            raise ObjectStoreError("object_endpoint_insecure", "non-loopback S3 endpoints must use HTTPS")
        if not BUCKET_RE.fullmatch(self.bucket) or ".." in self.bucket or ".-" in self.bucket or "-." in self.bucket:
            raise ObjectStoreError("object_config_invalid", "S3 bucket name is invalid")
        if not self.access_key or not self.secret_key:
            raise ObjectStoreError("object_config_invalid", "S3 credentials are required")


@dataclass(frozen=True)
class ObjectFact:
    content_sha256: str
    object_key: str
    bucket: str
    byte_size: int
    media_type: str
    state: str


def object_key_for(content_sha256: str) -> str:
    if not isinstance(content_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
        raise ObjectStoreError("object_hash_invalid", "content SHA-256 must be lowercase hexadecimal")
    return f"sha256/{content_sha256[:2]}/{content_sha256[2:4]}/{content_sha256}"


def _stream_sha256(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(128 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _error_code(exc: ClientError) -> str:
    response = exc.response.get("Error", {})
    return str(response.get("Code", ""))


def _not_found(exc: ClientError) -> bool:
    return _error_code(exc) in {"404", "NoSuchKey", "NoSuchBucket", "NotFound"}


def _is_loopback_host(hostname: str) -> bool:
    """Allow plaintext only for a literal loopback address.

    Resolving hostnames would make the security decision DNS-dependent, so a
    name such as ``localhost`` is deliberately not treated as loopback here.
    """

    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _policy_absent(exc: ClientError) -> bool:
    return _error_code(exc) in {"404", "NoSuchBucketPolicy", "NoSuchBucketPolicyException", "NoSuchKey", "NotFound"}


def _contains_principal_wildcard(value: Any) -> bool:
    if isinstance(value, str):
        return "*" in value or "?" in value
    if isinstance(value, list):
        return any(_contains_principal_wildcard(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_principal_wildcard(item) for item in value.values())
    return False


def _prove_private_aws_principal(value: Any) -> None:
    if not isinstance(value, str) or not value or _contains_principal_wildcard(value):
        raise ValueError("bucket policy AWS principal cannot be proven private")
    if value.isdecimal() and len(value) == 12:
        return
    if re.fullmatch(r"arn:aws(?:-[a-z-]+)?:iam::[0-9]{12}:.+", value):
        return
    raise ValueError("bucket policy principal cannot be proven private")


def _principal_allows_public_access(principal: Any) -> bool:
    if isinstance(principal, str):
        if _contains_principal_wildcard(principal):
            return True
        _prove_private_aws_principal(principal)
        return False
    if not isinstance(principal, dict) or not principal:
        raise ValueError("bucket policy principal cannot be proven private")
    if set(principal) != {"AWS"}:
        if _contains_principal_wildcard(principal):
            return True
        raise ValueError("bucket policy principal cannot be proven private")
    values = principal["AWS"]
    if not isinstance(values, list):
        values = [values]
    if not values:
        raise ValueError("bucket policy principal cannot be proven private")
    for value in values:
        if _contains_principal_wildcard(value):
            return True
        _prove_private_aws_principal(value)
    return False


def _policy_allows_public_access(policy_document: Any) -> bool:
    """Conservatively recognize public resource-policy grants.

    ``GetBucketPolicyStatus`` is useful on AWS S3 but legacy S3-compatible
    services have returned a false negative for otherwise valid wildcard
    policies. The policy itself is therefore authoritative for the fail-closed
    decision. Only fixed, specific AWS principals are accepted in an ``Allow``
    statement; wildcard, federated, service, canonical-user, malformed, and
    otherwise unprovable principals are rejected.
    """

    if not isinstance(policy_document, dict):
        raise ValueError("bucket policy must be a JSON object")
    statements = policy_document.get("Statement")
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or not statements:
        raise ValueError("bucket policy must contain statements")
    for statement in statements:
        if not isinstance(statement, dict) or not isinstance(statement.get("Effect"), str):
            raise ValueError("bucket policy statement is malformed")
        if statement["Effect"].lower() != "allow":
            continue
        if "NotPrincipal" in statement:
            return True
        if "Principal" not in statement:
            raise ValueError("bucket policy statement lacks a principal")
        if _principal_allows_public_access(statement["Principal"]):
            return True
    return False


def _assert_private_acl_grants(acl: Any, *, unverifiable_code: str, public_code: str, label: str) -> None:
    if not isinstance(acl, dict):
        raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")
    grants = acl.get("Grants")
    if not isinstance(grants, list):
        raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")
    for grant in grants:
        if not isinstance(grant, dict):
            raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")
        permission = grant.get("Permission")
        grantee = grant.get("Grantee")
        if not isinstance(permission, str) or not permission or not isinstance(grantee, dict):
            raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")
        uri = grantee.get("URI")
        if uri is not None:
            if not isinstance(uri, str):
                raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")
            if uri in PUBLIC_GRANTEE_URIS:
                raise ObjectStoreError(public_code, f"configured S3 {label} has a public ACL grant")
            raise ObjectStoreError(unverifiable_code, f"{label} ACL has an unrecognized group grant")
        grantee_type = grantee.get("Type")
        if grantee_type is not None and grantee_type not in {"CanonicalUser", "AmazonCustomerByEmail"}:
            raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")
        # Legacy MinIO omits CanonicalUser IDs from the response even though
        # the grant is still a canonical-user (and therefore non-public)
        # full-control grant. A named public Group never reaches this branch.
        if grantee_type == "CanonicalUser":
            continue
        if not any(isinstance(grantee.get(field), str) and grantee[field] for field in ("ID", "EmailAddress")):
            raise ObjectStoreError(unverifiable_code, f"{label} ACL cannot be verified")


class S3ObjectStore:
    """Private, path-style S3 writer with mandatory strong content verification."""

    def __init__(self, config: ObjectStoreConfig, *, client: Any | None = None) -> None:
        config.validate()
        self.config = config
        self.client = client or boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"}),
        )

    def ensure_private_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.config.bucket)
        except ClientError as exc:
            if not _not_found(exc):
                raise ObjectStoreError("bucket_unavailable", "unable to reach configured private S3 bucket") from exc
            try:
                self.client.create_bucket(Bucket=self.config.bucket)
            except (ClientError, BotoCoreError) as create_exc:
                raise ObjectStoreError("bucket_create_failed", "unable to create configured private S3 bucket") from create_exc
        self._assert_private_bucket()

    def _assert_private_bucket(self) -> None:
        try:
            policy_response = self.client.get_bucket_policy(Bucket=self.config.bucket)
        except ClientError as exc:
            if not _policy_absent(exc):
                raise ObjectStoreError("bucket_policy_unverifiable", "private bucket policy cannot be verified") from exc
        except (BotoCoreError, AttributeError) as exc:
            raise ObjectStoreError("bucket_policy_unverifiable", "private bucket policy cannot be verified") from exc
        else:
            policy_text = policy_response.get("Policy") if isinstance(policy_response, dict) else None
            if not isinstance(policy_text, str):
                raise ObjectStoreError("bucket_policy_unverifiable", "private bucket policy cannot be verified")
            try:
                if _policy_allows_public_access(json.loads(policy_text)):
                    raise ObjectStoreError("bucket_policy_public", "configured S3 bucket policy permits public access")
            except json.JSONDecodeError as exc:
                raise ObjectStoreError("bucket_policy_unverifiable", "private bucket policy cannot be verified") from exc
            except ValueError as exc:
                raise ObjectStoreError("bucket_policy_unverifiable", "private bucket policy cannot be verified") from exc
        try:
            policy_status = self.client.get_bucket_policy_status(Bucket=self.config.bucket)
        except ClientError as exc:
            pass
        except (BotoCoreError, AttributeError):
            pass
        else:
            policy = policy_status.get("PolicyStatus") if isinstance(policy_status, dict) else None
            is_public = policy.get("IsPublic") if isinstance(policy, dict) else None
            if is_public is True:
                raise ObjectStoreError("bucket_policy_public", "configured S3 bucket policy permits public access")
        try:
            acl = self.client.get_bucket_acl(Bucket=self.config.bucket)
        except (ClientError, BotoCoreError) as exc:
            raise ObjectStoreError("bucket_acl_unverifiable", "private bucket ACL cannot be verified") from exc
        _assert_private_acl_grants(
            acl,
            unverifiable_code="bucket_acl_unverifiable",
            public_code="bucket_acl_public",
            label="bucket",
        )

    def _assert_private_object(self, key: str) -> None:
        try:
            acl = self.client.get_object_acl(Bucket=self.config.bucket, Key=key)
        except (ClientError, BotoCoreError, AttributeError) as exc:
            raise ObjectStoreError("object_acl_unverifiable", "private object ACL cannot be verified") from exc
        _assert_private_acl_grants(
            acl,
            unverifiable_code="object_acl_unverifiable",
            public_code="object_acl_public",
            label="object",
        )

    def _head(self, key: str) -> dict[str, Any] | None:
        try:
            response = self.client.head_object(Bucket=self.config.bucket, Key=key)
        except ClientError as exc:
            if _not_found(exc):
                return None
            raise ObjectStoreError("object_head_failed", "unable to verify configured object") from exc
        except BotoCoreError as exc:
            raise ObjectStoreError("object_head_failed", "unable to verify configured object") from exc
        return dict(response)

    @staticmethod
    def _validate_head(head: dict[str, Any], *, content_sha256: str, byte_size: int, media_type: str) -> None:
        metadata = head.get("Metadata")
        if not isinstance(metadata, dict) or metadata.get("sha256") != content_sha256:
            raise ObjectStoreError("object_conflict", "existing object SHA metadata differs from the content address")
        if head.get("ContentLength") != byte_size:
            raise ObjectStoreError("object_conflict", "existing object byte size differs from the content address")
        if head.get("ContentType") != media_type:
            raise ObjectStoreError("object_conflict", "existing object media type differs from the content address")

    def _download_and_verify(self, key: str, *, content_sha256: str, byte_size: int, media_type: str) -> None:
        self._assert_private_object(key)
        head = self._head(key)
        if head is None:
            raise ObjectStoreError("object_missing", "existing object disappeared during verification")
        self._validate_head(head, content_sha256=content_sha256, byte_size=byte_size, media_type=media_type)
        try:
            response = self.client.get_object(Bucket=self.config.bucket, Key=key)
            body = response["Body"]
            digest, observed_size = _stream_sha256(body)
            body.close()
        except (ClientError, BotoCoreError, KeyError) as exc:
            raise ObjectStoreError("object_download_failed", "unable to download object for content verification") from exc
        if digest != content_sha256 or observed_size != byte_size:
            raise ObjectStoreError("object_conflict", "existing object bytes differ from the content address")
        if response.get("ContentType") != media_type:
            raise ObjectStoreError("object_conflict", "downloaded object media type differs from the expected value")
        self._assert_private_object(key)

    def ensure_object(
        self,
        *,
        source_path: Path,
        content_sha256: str,
        byte_size: int,
        media_type: str,
    ) -> ObjectFact:
        key = object_key_for(content_sha256)
        self.ensure_private_bucket()
        existing = self._head(key)
        if existing is not None:
            self._download_and_verify(
                key,
                content_sha256=content_sha256,
                byte_size=byte_size,
                media_type=media_type,
            )
            return ObjectFact(content_sha256, key, self.config.bucket, byte_size, media_type, "content_verified")
        try:
            with source_path.open("rb") as stream:
                self.client.put_object(
                    Bucket=self.config.bucket,
                    Key=key,
                    Body=stream,
                    ContentType=media_type,
                    Metadata={"sha256": content_sha256},
                )
        except (OSError, ClientError, BotoCoreError) as exc:
            raise ObjectStoreError("object_upload_failed", "unable to store content-addressed original object") from exc
        head = self._head(key)
        if head is None:
            raise ObjectStoreError("object_upload_failed", "uploaded object could not be read back by HEAD")
        self._validate_head(head, content_sha256=content_sha256, byte_size=byte_size, media_type=media_type)
        self._assert_private_object(key)
        return ObjectFact(content_sha256, key, self.config.bucket, byte_size, media_type, "uploaded_verified")

    def download_hashes(self, expected: dict[str, ObjectFact]) -> dict[str, str]:
        """Download every expected object and return its verified digest by key."""
        observed: dict[str, str] = {}
        for content_sha256, fact in sorted(expected.items()):
            self._download_and_verify(
                fact.object_key,
                content_sha256=content_sha256,
                byte_size=fact.byte_size,
                media_type=fact.media_type,
            )
            observed[fact.object_key] = content_sha256
        return observed
