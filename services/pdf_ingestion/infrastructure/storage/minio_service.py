"""MinIO storage adapter (sync) — used by both FastAPI upload and Celery worker."""
from __future__ import annotations

import io
import os

from minio import Minio
from minio.error import S3Error


class MinioService:
    """
    Sync MinIO adapter.

    Used synchronously in the FastAPI upload endpoint (blocking I/O accepted)
    and in the Celery worker for PDF download.
    """

    def __init__(self) -> None:
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "")
        secret_key = os.getenv("MINIO_SECRET_KEY", "")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self._bucket = os.getenv("MINIO_BUCKET", "rpg-pdfs")
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    def ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error as exc:
            print(f"[MinIO] Aviso ao verificar bucket: {exc}")

    def upload(self, data: bytes, object_name: str) -> str:
        try:
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_name,
                data=io.BytesIO(data),
                length=len(data),
                content_type="application/pdf",
            )
        except S3Error as exc:
            raise RuntimeError(f"Falha ao salvar arquivo no MinIO: {exc}") from exc
        return object_name

    def download(self, object_name: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, object_name)
            data = response.read()
        except S3Error as exc:
            raise RuntimeError(f"Falha ao baixar PDF do MinIO: {exc}") from exc
        finally:
            try:
                response.close()
                response.release_conn()
            except Exception:
                pass
        return data
