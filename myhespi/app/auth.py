from functools import wraps

from flask import current_app, jsonify, request


def api_error(status: int, code: str, message: str, details: dict | None = None):
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    return jsonify(payload), status


def require_api_token(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        tokens = current_app.config["MYHESPI_API_TOKENS"]
        if not tokens:
            return api_error(500, "server_not_configured", "API token list is empty.")

        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return api_error(401, "missing_token", "Authorization token is required.")

        token = auth_header[len(prefix):].strip()
        if token not in tokens:
            return api_error(401, "invalid_token", "Provided API token is invalid.")

        return view(*args, **kwargs)

    return wrapped
