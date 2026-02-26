import io

import pytest

from myhespi import create_app
from myhespi.services.hespi_runner import (
    ProcessingDependencyError,
    ProcessingRuntimeError,
)


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    monkeypatch.setenv("MYHESPI_TEMP_ROOT", str(tmp_path / "jobs"))
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers():
    return {"Authorization": "Bearer secret-token"}


def _fake_payload(input_image, job_dir, job_id, dwc_occ="x"):
    """Return a minimal valid payload that process_image would produce."""
    csv_path = job_dir / "dwc.csv"
    csv_path.write_text(f"occurrenceID\n{dwc_occ}\n", encoding="utf-8")
    return {
        "job_id": job_id,
        "status": "completed",
        "input_image": input_image.name,
        "primary_row_index": 0,
        "all_rows": [{}],
        "dwc_per_row": [{"occurrenceID": dwc_occ}],
        "dwc": {"occurrenceID": dwc_occ},
        "segments": [],
    }


def test_api_requires_token(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 401


def test_api_accepts_valid_token(client, auth_headers):
    response = client.get("/api/v1/health", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_create_job_happy_path(monkeypatch, client, auth_headers):
    def fake(settings, input_image, job_dir, job_id):
        return _fake_payload(input_image, job_dir, job_id)

    monkeypatch.setattr("myhespi.services.hespi_runner.process_image", fake)

    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "completed"
    assert payload["exports"]["dwc_csv_url"].endswith("/export/dwc.csv")


def test_create_job_rejects_bad_mime(client, auth_headers):
    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"image": (io.BytesIO(b"fake-image"), "sample.gif", "image/gif")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 415


def test_create_job_accepts_jp2(monkeypatch, client, auth_headers):
    def fake(settings, input_image, job_dir, job_id):
        return _fake_payload(input_image, job_dir, job_id, dwc_occ="jp2")

    monkeypatch.setattr("myhespi.services.hespi_runner.process_image", fake)

    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"image": (io.BytesIO(b"fake-image"), "sample.jp2", "image/jp2")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200


def test_export_csv_after_create_job(monkeypatch, client, auth_headers):
    def fake(settings, input_image, job_dir, job_id):
        return _fake_payload(input_image, job_dir, job_id, dwc_occ="abc")

    monkeypatch.setattr("myhespi.services.hespi_runner.process_image", fake)

    create_resp = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert create_resp.status_code == 200
    job_id = create_resp.get_json()["job_id"]

    export_resp = client.get(
        f"/api/v1/jobs/{job_id}/export/dwc.csv",
        headers=auth_headers,
    )
    assert export_resp.status_code == 200
    assert b"occurrenceID" in export_resp.data


def test_create_job_missing_runtime_dependency(monkeypatch, client, auth_headers):
    def fake(settings, input_image, job_dir, job_id):
        raise ProcessingDependencyError("pandas")

    monkeypatch.setattr("myhespi.services.hespi_runner.process_image", fake)

    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"]["code"] == "missing_runtime_dependency"
    assert payload["error"]["details"]["module"] == "pandas"


def test_create_job_runtime_error(monkeypatch, client, auth_headers):
    def fake(settings, input_image, job_dir, job_id):
        raise ProcessingRuntimeError("missing OPENAI_API_KEY")

    monkeypatch.setattr("myhespi.services.hespi_runner.process_image", fake)

    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"]["code"] == "processing_runtime_error"
