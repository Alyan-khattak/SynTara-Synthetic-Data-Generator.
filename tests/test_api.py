# ═══════════════════════════════════════════════════════════════════
# test_api.py — End-to-end FastAPI endpoint tests
# ═══════════════════════════════════════════════════════════════════
import io
import pytest
from fastapi.testclient import TestClient

from app import app
from hackdata.constants.spec import SPEC_VERSION

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /health returns 200 and version."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == SPEC_VERSION


def test_config_endpoint():
    """Verify GET /api/config returns preview_rows and max_rows."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "preview_rows" in data
    assert "max_rows" in data
    assert "generators" in data


def test_generate_endpoint_tabular():
    """Verify POST /api/generate returns generated run_id and preview."""
    payload = {
        "module": "tabular",
        "mode": "query",
        "query": "Generate 100 customer records",
        "n_rows": 50,
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] in ("generated", "failed")
    assert "preview" in data


def test_generate_endpoint_relational():
    """Verify POST /api/generate returns multi-table preview for relational module."""
    payload = {
        "module": "relational",
        "mode": "query",
        "query": "Generate customers and orders",
        "n_rows": 50,
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "table_names" in data
    assert len(data["table_names"]) >= 1


def test_runs_list_endpoint():
    """Verify GET /api/runs returns runs list."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data


def test_upload_invalid_extension():
    """Verify POST /api/upload rejects invalid file extensions."""
    file_data = io.BytesIO(b"some text content")
    files = {"file": ("test.txt", file_data, "text/plain")}
    response = client.post("/api/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_valid_csv():
    """Verify POST /api/upload accepts CSV file."""
    csv_content = b"id,name,amount\n" + b"".join([f"{i},Person{i},{100*i}\n".encode() for i in range(1, 16)])
    file_data = io.BytesIO(csv_content)
    files = {"file": ("data.csv", file_data, "text/csv")}
    response = client.post("/api/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "file_path" in data
    assert data["size_bytes"] == len(csv_content)

def test_export_endpoint():
    """Verify GET /api/runs/{run_id}/export."""
    # First generate a small run
    payload = {
        "module": "tabular",
        "mode": "query",
        "query": "3 users",
        "n_rows": 3,
        "seed": 42
    }
    gen_res = client.post("/api/generate", json=payload)
    assert gen_res.status_code == 200
    run_id = gen_res.json()["run_id"]

    # Now export it
    exp_res = client.get(f"/api/runs/{run_id}/export?format=csv")
    assert exp_res.status_code == 200
    assert exp_res.headers["content-type"] == "application/zip"

