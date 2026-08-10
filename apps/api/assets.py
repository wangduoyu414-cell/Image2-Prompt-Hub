"""Private S3 delivery after repository authorization and before HTTP output."""

from __future__ import annotations

import hashlib
import ipaddress
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from .repository import AssetLocator


class AssetStoreError(RuntimeError):
    """A stable public-asset delivery failure."""


class AssetStoreUnavailable(AssetStoreError):
    """The private object store cannot currently be used."""


class AssetIntegrityFailure(AssetStoreError):
    """The object received from storage differs from its immutable snapshot."""


@dataclass(frozen=True)
class AssetDelivery:
    content: bytes
    media_type: str
    content_sha256: str


class AssetStore(Protocol):
    def read(self, locator: AssetLocator) -> AssetDelivery: ...


@dataclass(frozen=True)
class AssetStoreSettings:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region_name: str = "us-east-1"

    def validate(self) -> None:
        endpoint = urlparse(self.endpoint_url)
        if endpoint.scheme not in {"http", "https"} or not endpoint.hostname:
            raise AssetStoreUnavailable("asset endpoint configuration is unavailable")
        if endpoint.username or endpoint.password or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment:
            raise AssetStoreUnavailable("asset endpoint configuration is unavailable")
        if endpoint.scheme == "http" and not _is_loopback(endpoint.hostname):
            raise AssetStoreUnavailable("asset endpoint configuration is unavailable")
        if not self.access_key_id or not self.secret_access_key:
            raise AssetStoreUnavailable("asset credentials are unavailable")

    @classmethod
    def from_environment(cls) -> "AssetStoreSettings":
        return cls(
            endpoint_url=os.environ.get("PUBLIC_API_S3_ENDPOINT_URL", ""),
            access_key_id=os.environ.get("PUBLIC_API_S3_ACCESS_KEY_ID", ""),
            secret_access_key=os.environ.get("PUBLIC_API_S3_SECRET_ACCESS_KEY", ""),
            region_name=os.environ.get("PUBLIC_API_S3_REGION", "us-east-1"),
        )


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class S3AssetStore:
    """A read-only S3 client; it never creates buckets or changes object state."""

    def __init__(self, settings: AssetStoreSettings) -> None:
        settings.validate()
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            region_name=settings.region_name,
            config=Config(
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 2, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )

    @classmethod
    def from_environment(cls) -> "S3AssetStore":
        return cls(AssetStoreSettings.from_environment())

    def read(self, locator: AssetLocator) -> AssetDelivery:
        try:
            response = self._client.get_object(Bucket=locator.bucket, Key=locator.object_key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "NoSuchBucket", "404"}:
                raise AssetIntegrityFailure("current asset is absent from private storage") from exc
            raise AssetStoreUnavailable("private asset storage is unavailable") from exc
        except BotoCoreError as exc:
            raise AssetStoreUnavailable("private asset storage is unavailable") from exc

        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise AssetIntegrityFailure("private asset response is incomplete")
        try:
            declared_length = response.get("ContentLength")
            content_type = response.get("ContentType")
            if not isinstance(declared_length, int) or declared_length != locator.byte_size:
                raise AssetIntegrityFailure("private asset length differs from the immutable snapshot")
            if not isinstance(content_type, str) or content_type.split(";", 1)[0].strip().lower() != locator.media_type:
                raise AssetIntegrityFailure("private asset media type differs from the immutable snapshot")
            content = body.read()
        except AssetStoreError:
            raise
        except (BotoCoreError, OSError) as exc:
            raise AssetStoreUnavailable("private asset storage is unavailable") from exc
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

        if not isinstance(content, bytes) or len(content) != locator.byte_size:
            raise AssetIntegrityFailure("private asset bytes differ from the immutable snapshot")
        if hashlib.sha256(content).hexdigest() != locator.content_sha256:
            raise AssetIntegrityFailure("private asset hash differs from the immutable snapshot")
        return AssetDelivery(content=content, media_type=locator.media_type, content_sha256=locator.content_sha256)
