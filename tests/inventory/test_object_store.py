from __future__ import annotations

import io
import json

import pytest
from botocore.exceptions import ClientError

from inventory.object_store import ObjectStoreConfig, ObjectStoreError, S3ObjectStore, object_key_for


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "test")


class FakeS3:
    def __init__(self) -> None:
        self.bucket_exists = False
        self.objects: dict[str, tuple[bytes, str, dict[str, str]]] = {}
        self.put_count = 0
        self.bucket_acl_public = False
        self.bucket_policy_public = False
        self.bucket_policy_status_public: bool | None = None
        self.bucket_policy_document: str | None = None
        self.bucket_acl_response: dict[str, object] | None = None
        self.object_acl_public: set[str] = set()
        self.new_objects_public = False

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_exists:
            raise client_error("NoSuchBucket")

    def create_bucket(self, *, Bucket: str) -> None:
        self.bucket_exists = True

    def get_bucket_acl(self, *, Bucket: str):
        if self.bucket_acl_response is not None:
            return self.bucket_acl_response
        grants = []
        if self.bucket_acl_public:
            grants.append({"Grantee": {"URI": "http://acs.amazonaws.com/groups/global/AllUsers"}, "Permission": "READ"})
        return {"Grants": grants}

    def get_bucket_policy_status(self, *, Bucket: str):
        public = self.bucket_policy_public if self.bucket_policy_status_public is None else self.bucket_policy_status_public
        return {"PolicyStatus": {"IsPublic": public}}

    def get_bucket_policy(self, *, Bucket: str):
        if self.bucket_policy_document is not None:
            return {"Policy": self.bucket_policy_document}
        if not self.bucket_policy_public:
            raise client_error("NoSuchBucketPolicy")
        return {
            "Policy": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": f"arn:aws:s3:::{Bucket}/*",
                        }
                    ],
                }
            )
        }

    def head_object(self, *, Bucket: str, Key: str):
        if Key not in self.objects:
            raise client_error("NoSuchKey")
        body, content_type, metadata = self.objects[Key]
        return {"ContentLength": len(body), "ContentType": content_type, "Metadata": metadata}

    def put_object(self, *, Bucket: str, Key: str, Body, ContentType: str, Metadata: dict[str, str]) -> None:
        self.put_count += 1
        self.objects[Key] = (Body.read(), ContentType, dict(Metadata))
        if self.new_objects_public:
            self.object_acl_public.add(Key)

    def get_object(self, *, Bucket: str, Key: str):
        if Key not in self.objects:
            raise client_error("NoSuchKey")
        body, content_type, metadata = self.objects[Key]
        return {"Body": io.BytesIO(body), "ContentType": content_type, "Metadata": metadata}

    def get_object_acl(self, *, Bucket: str, Key: str):
        if Key not in self.objects:
            raise client_error("NoSuchKey")
        grants = []
        if Key in self.object_acl_public:
            grants.append({"Grantee": {"URI": "http://acs.amazonaws.com/groups/global/AllUsers"}, "Permission": "READ"})
        return {"Grants": grants}


def config() -> ObjectStoreConfig:
    return ObjectStoreConfig(
        endpoint_url="http://127.0.0.1:9000",
        bucket="inventory-private-test",
        access_key="random-access-key",
        secret_key="random-secret-key",
    )


def source_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"x" * 600


def test_content_addressed_upload_then_existing_download_verification(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    digest = hashlib.sha256(payload).hexdigest()
    client = FakeS3()
    store = S3ObjectStore(config(), client=client)
    first = store.ensure_object(source_path=path, content_sha256=digest, byte_size=len(payload), media_type="image/png")
    second = store.ensure_object(source_path=path, content_sha256=digest, byte_size=len(payload), media_type="image/png")
    assert first.state == "uploaded_verified"
    assert second.state == "content_verified"
    assert first.object_key == object_key_for(digest)
    assert client.put_count == 1
    assert store.download_hashes({digest: first}) == {first.object_key: digest}


def test_existing_conflict_never_overwrites(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    digest = hashlib.sha256(payload).hexdigest()
    client = FakeS3()
    client.bucket_exists = True
    key = object_key_for(digest)
    client.objects[key] = (b"wrong" * 200, "image/png", {"sha256": digest})
    store = S3ObjectStore(config(), client=client)
    with pytest.raises(ObjectStoreError) as failure:
        store.ensure_object(source_path=path, content_sha256=digest, byte_size=len(payload), media_type="image/png")
    assert failure.value.error_code == "object_conflict"
    assert client.put_count == 0
    assert client.objects[key][0] != payload


def test_public_bucket_acl_is_rejected_before_object_write(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    client = FakeS3()
    client.bucket_exists = True
    client.bucket_acl_public = True
    with pytest.raises(ObjectStoreError) as failure:
        S3ObjectStore(config(), client=client).ensure_object(
            source_path=path,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),
            media_type="image/png",
        )
    assert failure.value.error_code == "bucket_acl_public"
    assert client.put_count == 0


def test_unverifiable_bucket_acl_is_rejected_before_object_write(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    client = FakeS3()
    client.bucket_exists = True
    client.bucket_acl_response = {"Grants": [{"Grantee": {"Type": "Group"}, "Permission": "READ"}]}
    with pytest.raises(ObjectStoreError) as failure:
        S3ObjectStore(config(), client=client).ensure_object(
            source_path=path,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),
            media_type="image/png",
        )
    assert failure.value.error_code == "bucket_acl_unverifiable"
    assert client.put_count == 0


def test_redacted_canonical_user_acl_is_nonpublic(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    client = FakeS3()
    client.bucket_exists = True
    client.bucket_acl_response = {"Grants": [{"Grantee": {"Type": "CanonicalUser"}, "Permission": "FULL_CONTROL"}]}
    result = S3ObjectStore(config(), client=client).ensure_object(
        source_path=path,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        media_type="image/png",
    )
    assert result.state == "uploaded_verified"


def test_public_bucket_policy_is_rejected_before_object_write(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    client = FakeS3()
    client.bucket_exists = True
    client.bucket_policy_public = True
    client.bucket_policy_status_public = False
    with pytest.raises(ObjectStoreError) as failure:
        S3ObjectStore(config(), client=client).ensure_object(
            source_path=path,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),
            media_type="image/png",
        )
    assert failure.value.error_code == "bucket_policy_public"
    assert client.put_count == 0


def test_unprovable_allow_principal_is_rejected_before_object_write(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    client = FakeS3()
    client.bucket_exists = True
    client.bucket_policy_status_public = False
    client.bucket_policy_document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/example.invalid"},
                    "Action": ["s3:GetObject"],
                    "Resource": "arn:aws:s3:::inventory-private-test/*",
                }
            ],
        }
    )
    with pytest.raises(ObjectStoreError) as failure:
        S3ObjectStore(config(), client=client).ensure_object(
            source_path=path,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),
            media_type="image/png",
        )
    assert failure.value.error_code == "bucket_policy_unverifiable"
    assert client.put_count == 0


def test_wildcard_nested_aws_principal_is_rejected_before_object_write(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    client = FakeS3()
    client.bucket_exists = True
    client.bucket_policy_status_public = False
    client.bucket_policy_document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:role/*"},
                    "Action": ["s3:GetObject"],
                    "Resource": "arn:aws:s3:::inventory-private-test/*",
                }
            ],
        }
    )
    with pytest.raises(ObjectStoreError) as failure:
        S3ObjectStore(config(), client=client).ensure_object(
            source_path=path,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=len(payload),
            media_type="image/png",
        )
    assert failure.value.error_code == "bucket_policy_public"
    assert client.put_count == 0


def test_public_existing_or_new_object_acl_is_rejected(tmp_path) -> None:
    path = tmp_path / "image.png"
    payload = source_bytes()
    path.write_bytes(payload)
    import hashlib

    digest = hashlib.sha256(payload).hexdigest()
    key = object_key_for(digest)
    existing = FakeS3()
    existing.bucket_exists = True
    existing.objects[key] = (payload, "image/png", {"sha256": digest})
    existing.object_acl_public.add(key)
    with pytest.raises(ObjectStoreError) as existing_failure:
        S3ObjectStore(config(), client=existing).ensure_object(
            source_path=path,
            content_sha256=digest,
            byte_size=len(payload),
            media_type="image/png",
        )
    assert existing_failure.value.error_code == "object_acl_public"
    assert existing.put_count == 0

    created = FakeS3()
    created.new_objects_public = True
    with pytest.raises(ObjectStoreError) as new_failure:
        S3ObjectStore(config(), client=created).ensure_object(
            source_path=path,
            content_sha256=digest,
            byte_size=len(payload),
            media_type="image/png",
        )
    assert new_failure.value.error_code == "object_acl_public"
    assert created.put_count == 1


@pytest.mark.parametrize("endpoint", ["http://localhost:9000", "http://198.51.100.9:9000"])
def test_plain_http_non_loopback_endpoint_is_rejected(endpoint: str) -> None:
    with pytest.raises(ObjectStoreError) as failure:
        ObjectStoreConfig(endpoint, "inventory-private-test", "key", "secret").validate()
    assert failure.value.error_code == "object_endpoint_insecure"
