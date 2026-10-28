from pathlib import Path

from fastapi.testclient import TestClient

from api import app

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_legacy_app"
client = TestClient(app)


def test_analyze_returns_findings_and_plan() -> None:
    files = {path.name: path.read_text(encoding="utf-8") for path in SAMPLE_DIR.glob("*.cs")}
    response = client.post("/analyze", json={"files": files})
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "high"
    assert body["plan"]["phases"][0]["name"] == "Security remediation"


def test_analyze_rejects_non_csharp_file_names() -> None:
    response = client.post("/analyze", json={"files": {"notes.txt": "public class Notes { }"}})
    assert response.status_code == 422


def test_analyze_rejects_empty_request() -> None:
    response = client.post("/analyze", json={"files": {}})
    assert response.status_code == 422
