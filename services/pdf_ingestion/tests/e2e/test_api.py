"""E2E tests — full HTTP stack with MinIO and Celery mocked."""
import pytest

FAKE_PDF = b"%PDF-1.4 1 0 obj<</Type/Catalog>>endobj"


async def _upload(client, filename="rulebook.pdf", content=None):
    return await client.post(
        "/upload",
        files={"file": (filename, content or FAKE_PDF, "application/pdf")},
    )


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_returns_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["service"] == "pdf_ingestion"


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------


class TestUpload:
    async def test_success_returns_202(self, client):
        r = await _upload(client)
        assert r.status_code == 202
        data = r.json()
        assert "source_id" in data
        assert data["status"] == "enqueued"

    async def test_title_derived_from_filename(self, client):
        r = await _upload(client, filename="dungeon_master_guide.pdf")
        assert r.status_code == 202
        assert r.json()["title"] == "dungeon master guide"

    async def test_filename_with_spaces(self, client):
        r = await _upload(client, filename="Players Handbook.pdf")
        assert r.status_code == 202
        assert "source_id" in r.json()

    async def test_non_pdf_rejected(self, client):
        r = await client.post(
            "/upload",
            files={"file": ("doc.txt", b"not a pdf", "text/plain")},
        )
        assert r.status_code == 400

    async def test_empty_file_rejected(self, client):
        r = await _upload(client, content=b"")
        assert r.status_code == 400

    async def test_filename_stored(self, client):
        r = await _upload(client, filename="phb_5e.pdf")
        assert r.status_code == 202
        assert r.json()["filename"] == "phb_5e.pdf"


# ---------------------------------------------------------------------------
# GET /sources
# ---------------------------------------------------------------------------


class TestListSources:
    async def test_list_empty(self, client):
        r = await client.get("/sources")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["sources"] == []

    async def test_list_after_uploads(self, client):
        await _upload(client, "a.pdf")
        await _upload(client, "b.pdf")
        r = await client.get("/sources")
        assert r.status_code == 200
        assert r.json()["total"] == 2


# ---------------------------------------------------------------------------
# GET /sources/{id}/status
# ---------------------------------------------------------------------------


class TestSourceStatus:
    async def test_status_pending_after_upload(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        r = await client.get(f"/sources/{sid}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    async def test_status_not_found(self, client):
        r = await client.get("/sources/00000000-0000-0000-0000-000000000000/status")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /sources/{id}
# ---------------------------------------------------------------------------


class TestDeleteSource:
    async def test_delete_returns_204(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        r = await client.delete(f"/sources/{sid}")
        assert r.status_code == 204

    async def test_delete_not_found(self, client):
        r = await client.delete("/sources/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    async def test_deleted_source_not_listed(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        await client.delete(f"/sources/{sid}")
        r = await client.get("/sources")
        ids = [s["id"] for s in r.json()["sources"]]
        assert sid not in ids


# ---------------------------------------------------------------------------
# POST /sources/{id}/retry
# ---------------------------------------------------------------------------


class TestRetrySource:
    async def test_retry_returns_202(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        r = await client.post(f"/sources/{sid}/retry")
        assert r.status_code == 202
        assert r.json()["status"] == "enqueued"

    async def test_retry_not_found(self, client):
        r = await client.post("/sources/00000000-0000-0000-0000-000000000000/retry")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /knowledge/stats
# ---------------------------------------------------------------------------


class TestKnowledgeStats:
    async def test_stats_200(self, client):
        r = await client.get("/knowledge/stats")
        assert r.status_code == 200

    async def test_stats_has_required_fields(self, client):
        r = await client.get("/knowledge/stats")
        data = r.json()
        assert "total_chunks" in data
        assert "gm_is_ready" in data
        assert "total_sources" in data
        assert "systems_covered" in data

    async def test_stats_empty_db_not_ready(self, client):
        r = await client.get("/knowledge/stats")
        data = r.json()
        assert data["total_chunks"] == 0
        assert data["gm_is_ready"] is False
