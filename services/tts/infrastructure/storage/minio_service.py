"""MinIO audio storage adapter."""
from __future__ import annotations

import io
import os

from minio import Minio
from minio.error import S3Error

MINIO_BUCKET = "rpg-audio"


class MinioAudioService:
    """Sync MinIO wrapper — audio files are small enough that blocking I/O is acceptable."""

    def __init__(self) -> None:
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self._bucket = MINIO_BUCKET
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    async def ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error as exc:
            import logging
            logging.getLogger(__name__).error("Erro MinIO no startup: %s", exc)

    async def upload(self, object_name: str, data: bytes) -> str:
        try:
            self._client.put_object(
                self._bucket,
                object_name,
                io.BytesIO(data),
                len(data),
                content_type="audio/mpeg",
            )
        except S3Error as exc:
            raise RuntimeError(f"Falha ao armazenar áudio no MinIO: {exc}") from exc
        return f"/media/{self._bucket}/{object_name}"
