"""MinIO storage adapter — implements IStoragePort."""
from __future__ import annotations

import io
import logging
import os

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

_MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "/media")


class MinioService:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        bucket: str = "rpg-media",
    ) -> None:
        self._bucket = bucket
        self._client = Minio(
            endpoint=endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=secure if secure is not None else os.getenv("MINIO_SECURE", "false").lower() == "true",
        )

    def ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("Bucket '%s' criado.", self._bucket)
        except S3Error as exc:
            logger.error("Erro ao verificar/criar bucket MinIO: %s", exc)
            raise

    async def upload(self, data: bytes, object_name: str) -> str:
        try:
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_name,
                data=io.BytesIO(data),
                length=len(data),
                content_type="image/png",
            )
        except S3Error as exc:
            logger.error("Erro ao fazer upload no MinIO: %s", exc)
            raise RuntimeError(f"Falha ao armazenar imagem: {exc}") from exc

        return f"{_MEDIA_BASE_URL}/{object_name}"

    async def upload_svg(self, svg_content: str, object_name: str) -> str:
        data = svg_content.encode("utf-8")
        try:
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_name,
                data=io.BytesIO(data),
                length=len(data),
                content_type="image/svg+xml",
            )
        except S3Error as exc:
            logger.error("Erro ao fazer upload SVG no MinIO: %s", exc)
            raise RuntimeError(f"Falha ao armazenar SVG: {exc}") from exc

        return f"{_MEDIA_BASE_URL}/{object_name}"
