"""Integration tests for pdf_ingestion service."""
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

FAKE_PDF = b"%PDF-1.4 1 0 obj<</Type/Catalog>>endobj"


async def _upload(client, filename="rulebook.pdf", content=None):
    return await client.post(
        "/upload",
        files={"file": (filename, content or FAKE_PDF, "application/pdf")},
    )


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


# ── POST /upload ──────────────────────────────────────────────────────────────

class TestUpload:
    async def test_upload_pdf_success(self, client):
        r = await _upload(client)
        assert r.status_code in (200, 202)
        data = r.json()
        assert "source_id" in data
        assert data["status"] in ("pending", "enqueued", "processing")

    async def test_upload_derives_title_from_filename(self, client):
        r = await _upload(client, filename="dungeon_master_guide.pdf")
        assert r.status_code in (200, 202)
        assert r.json()["title"] == "dungeon master guide"

    async def test_upload_with_spaces_in_filename(self, client):
        r = await _upload(client, filename="Players Handbook.pdf")
        assert r.status_code in (200, 202)
        assert "source_id" in r.json()

    async def test_upload_non_pdf_rejected(self, client):
        r = await client.post(
            "/upload",
            files={"file": ("document.txt", b"not a pdf", "text/plain")},
        )
        assert r.status_code == 400

    async def test_upload_returns_source_id_immediately(self, client):
        """Upload must return immediately — processing is async."""
        r = await _upload(client)
        assert r.status_code in (200, 202)
        assert "source_id" in r.json()

    async def test_upload_filename_stored(self, client):
        r = await _upload(client, filename="phb_5e.pdf")
        assert r.status_code in (200, 202)
        assert r.json()["filename"] == "phb_5e.pdf"


# ── GET /sources ──────────────────────────────────────────────────────────────

class TestListSources:
    async def test_list_empty(self, client):
        r = await client.get("/sources")
        assert r.status_code == 200
        data = r.json()
        sources = data if isinstance(data, list) else data.get("sources", [])
        assert isinstance(sources, list)
        assert len(sources) == 0

    async def test_list_returns_uploaded(self, client):
        await _upload(client, "book1.pdf")
        await _upload(client, "book2.pdf")
        r = await client.get("/sources")
        assert r.status_code == 200
        data = r.json()
        sources = data if isinstance(data, list) else data.get("sources", [])
        assert len(sources) == 2


# ── GET /sources/{id}/status ──────────────────────────────────────────────────

class TestSourceStatus:
    async def test_status_pending_after_upload(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        r = await client.get(f"/sources/{sid}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("pending", "enqueued", "processing", "completed", "error")

    async def test_status_not_found(self, client):
        r = await client.get("/sources/00000000-0000-0000-0000-000000000000/status")
        assert r.status_code == 404


# ── DELETE /sources/{id} ──────────────────────────────────────────────────────

class TestDeleteSource:
    async def test_delete_source(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        r = await client.delete(f"/sources/{sid}")
        assert r.status_code in (200, 204)

    async def test_delete_not_found(self, client):
        r = await client.delete("/sources/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    async def test_deleted_source_no_longer_listed(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        await client.delete(f"/sources/{sid}")
        r = await client.get("/sources")
        data = r.json()
        sources = data if isinstance(data, list) else data.get("sources", [])
        ids = [s["id"] for s in sources]
        assert sid not in ids


# ── POST /sources/{id}/retry ──────────────────────────────────────────────────

class TestRetrySource:
    async def test_retry_pending_source(self, client):
        upload = await _upload(client)
        sid = upload.json()["source_id"]
        r = await client.post(f"/sources/{sid}/retry")
        assert r.status_code in (200, 202)

    async def test_retry_not_found(self, client):
        r = await client.post("/sources/00000000-0000-0000-0000-000000000000/retry")
        assert r.status_code == 404


# ── GET /knowledge/stats ──────────────────────────────────────────────────────

class TestKnowledgeStats:
    async def test_stats_returns_200(self, client):
        r = await client.get("/knowledge/stats")
        assert r.status_code == 200

    async def test_stats_has_required_fields(self, client):
        r = await client.get("/knowledge/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_chunks" in data
        assert "gm_is_ready" in data

    async def test_stats_empty_db_not_ready(self, client):
        r = await client.get("/knowledge/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_chunks"] == 0
        assert data["gm_is_ready"] is False
