#!/usr/bin/env bash
set -euo pipefail

# Full local install for hespi + myhespi.
# Usage:
#   bash scripts/install_full_stack.sh
# Optional:
#   PYTHON_BIN=python3.11 bash scripts/install_full_stack.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  elif command -v python3.10 >/dev/null 2>&1; then
    PYTHON_BIN="python3.10"
  else
    PYTHON_BIN="python3"
  fi
fi

echo "[1/4] Using Python interpreter: $PYTHON_BIN"
"$PYTHON_BIN" -V

echo "[2/4] Creating virtual environment (.venv)"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

echo "[3/4] Installing pip toolchain compatibility pins"
python -m pip install -U "pip<24.1" "setuptools<70" wheel

echo "[4/4] Installing full runtime dependencies"
pip install --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt

cat <<'EOF'

Installation completed.

Next steps:
  source .venv/bin/activate
  export MYHESPI_API_TOKENS="dev-token"
  python -m myhespi.app

Open:
  Web: http://localhost:5001/
  API: http://localhost:5001/api/v1/health

Note:
  Tesseract OCR must be installed on the host OS for full OCR functionality.
  macOS example: brew install tesseract
EOF
