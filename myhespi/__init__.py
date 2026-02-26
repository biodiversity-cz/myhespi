from flask import Flask
from werkzeug.exceptions import RequestEntityTooLarge

from .auth import api_error
from .config import load_settings
from .routes_api import api_bp
from .routes_web import web_bp
from .services.storage import ensure_temp_root, maybe_cleanup


def create_app() -> Flask:
    settings = load_settings()
    ensure_temp_root(settings.temp_root)

    app = Flask(__name__, template_folder="templates")
    app.config.update(
        MYHESPI_API_TOKENS=settings.api_tokens,
        MYHESPI_MAX_UPLOAD_MB=settings.max_upload_mb,
        MYHESPI_MAX_UPLOAD_BYTES=settings.max_upload_bytes,
        MYHESPI_PROCESS_TIMEOUT_SECONDS=settings.process_timeout_seconds,
        MYHESPI_RETENTION_DAYS=settings.retention_days,
        MYHESPI_TEMP_ROOT=settings.temp_root,
        MYHESPI_SETTINGS=settings,
        MAX_CONTENT_LENGTH=settings.max_upload_bytes,
    )

    @app.before_request
    def _periodic_cleanup():
        maybe_cleanup(
            temp_root=app.config["MYHESPI_TEMP_ROOT"],
            retention_days=app.config["MYHESPI_RETENTION_DAYS"],
        )

    @app.errorhandler(RequestEntityTooLarge)
    def _file_too_large(_error):
        if _is_api_request():
            return api_error(413, "file_too_large", "File exceeds upload limit.")
        return "Nahraný soubor je příliš velký.", 413

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    return app


def _is_api_request() -> bool:
    from flask import request

    return request.path.startswith("/api/")
