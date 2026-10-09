from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir

from ai_dating.config import Settings
from ai_dating.errors import AppError
from ai_dating.media.tokens import read_token, sign_token


@dataclass(frozen=True)
class StoredObject:
    exists: bool
    size: int | None
    sha256: str | None
    body: bytes | None = None


class ObjectStore:
    def put(self, key: str, body: bytes, content_type: str) -> None:
        raise NotImplementedError

    def head(self, key: str) -> StoredObject:
        raise NotImplementedError

    def get(self, key: str) -> StoredObject:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def upload_url(self, key: str, content_type: str, expires_at: int) -> str:
        raise NotImplementedError

    def download_url(self, key: str, expires_at: int) -> str:
        raise NotImplementedError


class LocalStore(ObjectStore):
    def __init__(self, root: Path, secret: str) -> None:
        self.root = root
        self.secret = secret
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if ".." in Path(key).parts:
            raise AppError(404, "not_found", "Not found.")
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise AppError(404, "not_found", "Not found.")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, body: bytes, content_type: str) -> None:
        del content_type
        self._path(key).write_bytes(body)

    def head(self, key: str) -> StoredObject:
        path = self._path(key)
        if not path.is_file():
            return StoredObject(exists=False, size=None, sha256=None)
        return StoredObject(exists=True, size=path.stat().st_size, sha256=None)

    def get(self, key: str) -> StoredObject:
        path = self._path(key)
        if not path.is_file():
            return StoredObject(exists=False, size=None, sha256=None)
        body = path.read_bytes()
        return StoredObject(exists=True, size=len(body), sha256=None, body=body)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def upload_url(self, key: str, content_type: str, expires_at: int) -> str:
        del content_type
        token = sign_token(self.secret, "put", key, expires_at)
        return f"/v1/media/uploads/{token}"

    def download_url(self, key: str, expires_at: int) -> str:
        token = sign_token(self.secret, "get", key, expires_at)
        return f"/v1/media/objects/{token}"


class S3Store(ObjectStore):
    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket = settings.object_storage_bucket or ""
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
        )
        self.ttl = settings.media_url_ttl_seconds

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=body, ContentType=content_type
        )

    def head(self, key: str) -> StoredObject:
        try:
            info = self.client.head_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.ClientError:
            return StoredObject(exists=False, size=None, sha256=None)
        return StoredObject(
            exists=True, size=int(info.get("ContentLength") or 0), sha256=None
        )

    def get(self, key: str) -> StoredObject:
        try:
            info = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.ClientError:
            return StoredObject(exists=False, size=None, sha256=None)
        body = info["Body"].read()
        return StoredObject(exists=True, size=len(body), sha256=None, body=body)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def upload_url(self, key: str, content_type: str, expires_at: int) -> str:
        del expires_at
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=self.ttl,
        )

    def download_url(self, key: str, expires_at: int) -> str:
        del expires_at
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.ttl,
        )


def open_store(settings: Settings) -> ObjectStore:
    if settings.object_storage_backend == "s3":
        return S3Store(settings)
    root = settings.object_storage_path or str(Path(gettempdir()) / "ai-matchmaker-media")
    return LocalStore(Path(root), settings.media_signing_secret)


def local_key_from_upload_token(settings: Settings, token: str) -> str:
    return read_token(settings.media_signing_secret, token, "put")


def local_key_from_download_token(settings: Settings, token: str) -> str:
    return read_token(settings.media_signing_secret, token, "get")
