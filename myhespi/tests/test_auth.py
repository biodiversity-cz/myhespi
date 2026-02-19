import io

from myhespi.app import create_app
from myhespi.app.services.hespi_runner import ProcessingDependencyError, ProcessingRuntimeError


def _app():
    app = create_app()
    app.config.update(TESTING=True)
    return app


def test_api_requires_token(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()

    response = client.get("/api/v1/health")
    assert response.status_code == 401


def test_api_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_create_job_happy_path(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()

    def fake_process_image(settings, input_image, job_dir, job_id):
        csv_path = job_dir / "dwc.csv"
        csv_path.write_text("occurrenceID\nx\n", encoding="utf-8")
        return {
            "job_id": job_id,
            "status": "completed",
            "input_image_url": f"/api/v1/jobs/{job_id}/files/{input_image.name}",
            "segments": [],
            "dwc": {"occurrenceID": "x"},
            "exports": {"dwc_csv_url": f"/api/v1/jobs/{job_id}/export/dwc.csv", "dwca_zip_url": None},
        }

    monkeypatch.setattr("myhespi.app.routes_api.process_image", fake_process_image)

    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret-token"},
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "completed"
    assert payload["exports"]["dwc_csv_url"].endswith("/export/dwc.csv")


def test_create_job_rejects_bad_mime(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()
    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret-token"},
        data={"image": (io.BytesIO(b"fake-image"), "sample.gif", "image/gif")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 415


def test_create_job_accepts_jp2(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()

    def fake_process_image(settings, input_image, job_dir, job_id):
        csv_path = job_dir / "dwc.csv"
        csv_path.write_text("occurrenceID\njp2\n", encoding="utf-8")
        return {
            "job_id": job_id,
            "status": "completed",
            "input_image_url": f"/api/v1/jobs/{job_id}/files/{input_image.name}",
            "segments": [],
            "dwc": {"occurrenceID": "jp2"},
            "exports": {"dwc_csv_url": f"/api/v1/jobs/{job_id}/export/dwc.csv", "dwca_zip_url": None},
        }

    monkeypatch.setattr("myhespi.app.routes_api.process_image", fake_process_image)
    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret-token"},
        data={"image": (io.BytesIO(b"fake-image"), "sample.jp2", "image/jp2")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200


def test_export_csv_after_create_job(monkeypatch, tmp_path):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    monkeypatch.setenv("MYHESPI_TEMP_ROOT", str(tmp_path / "temp-root"))
    app = _app()
    client = app.test_client()

    def fake_process_image(settings, input_image, job_dir, job_id):
        csv_path = job_dir / "dwc.csv"
        csv_path.write_text("occurrenceID\nabc\n", encoding="utf-8")
        return {
            "job_id": job_id,
            "status": "completed",
            "input_image_url": f"/api/v1/jobs/{job_id}/files/{input_image.name}",
            "segments": [],
            "dwc": {"occurrenceID": "abc"},
            "exports": {"dwc_csv_url": f"/api/v1/jobs/{job_id}/export/dwc.csv", "dwca_zip_url": None},
        }

    monkeypatch.setattr("myhespi.app.routes_api.process_image", fake_process_image)
    create_response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret-token"},
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert create_response.status_code == 200
    job_id = create_response.get_json()["job_id"]

    export_response = client.get(
        f"/api/v1/jobs/{job_id}/export/dwc.csv",
        headers={"Authorization": "Bearer secret-token"},
    )
    assert export_response.status_code == 200
    assert b"occurrenceID" in export_response.data


def test_create_job_missing_runtime_dependency(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()

    def fake_process_image(settings, input_image, job_dir, job_id):
        raise ProcessingDependencyError("pandas")

    monkeypatch.setattr("myhespi.app.routes_api.process_image", fake_process_image)
    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret-token"},
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"]["code"] == "missing_runtime_dependency"
    assert payload["error"]["details"]["module"] == "pandas"


def test_create_job_runtime_error(monkeypatch):
    monkeypatch.setenv("MYHESPI_API_TOKENS", "secret-token")
    app = _app()
    client = app.test_client()

    def fake_process_image(settings, input_image, job_dir, job_id):
        raise ProcessingRuntimeError("missing OPENAI_API_KEY")

    monkeypatch.setattr("myhespi.app.routes_api.process_image", fake_process_image)
    response = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer secret-token"},
        data={"image": (io.BytesIO(b"fake-image"), "sample.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"]["code"] == "processing_runtime_error"
