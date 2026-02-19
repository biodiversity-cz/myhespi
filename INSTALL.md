# INSTALL.md

Complete installation and run guide for `hespi` + `myhespi` in this repository.

## 0) Quick install (recommended)

From repository root:

```bash
bash scripts/install_full_stack.sh
```

This script:
- creates `.venv`,
- pins compatible packaging tools,
- installs full runtime dependencies for `hespi` + `myhespi`.

## 1) Prerequisites

- OS: macOS (tested on Apple Silicon)
- Python: `3.11.x` (recommended for current setup)
- Git repository root: `/Users/pokorny/PyEnv/hespi`

> Note: `hespi` declares `>=3.10,<3.12`. Python `3.11` is the safest default here.

## 2) Manual create virtual environment

From repository root:

```bash
cd /Users/pokorny/PyEnv/hespi
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

If `.venv` is broken after interpreter changes, recreate it:

```bash
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
```

## 3) Manual install profiles

### A) myHESPI only (web/API + tests)

```bash
pip install -r myhespi/requirements-dev.txt
```

This is enough for:
- app startup,
- API/web routes,
- tests with mocked HESPI processing.

### B) Full runtime (myHESPI + local HESPI processing)

Because of old metadata in some transitive packages, keep pip below `24.1`:

```bash
pip install -U "pip<24.1"
pip install --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt
```

Optional for unstable network:

```bash
pip install --progress-bar off --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt
```

## 4) Run tests

```bash
pytest myhespi/tests -q
```

## 5) Run application

From repository root with activated `.venv`:

```bash
export MYHESPI_API_TOKENS="dev-token"
python -m myhespi.app
```

LLM is disabled by default (`HESPI_LLM_MODEL=none`).
If you want LLM correction, set both:

```bash
export HESPI_LLM_MODEL="gpt-4o"
export OPENAI_API_KEY="..."
```

App URL:
- Web: `http://localhost:5001/`
- API: `http://localhost:5001/api/v1/`

## 6) Quick smoke test

Health:

```bash
curl -s -X GET "http://localhost:5001/api/v1/health" \
  -H "Authorization: Bearer dev-token"
```

Process one image + export CSV:

```bash
curl -s -X POST "http://localhost:5001/api/v1/jobs" \
  -H "Authorization: Bearer dev-token" \
  -F "image=@/absolute/path/to/sample.jpg" > /tmp/myhespi-job.json

JOB_ID=$(python - <<'PY'
import json
print(json.load(open('/tmp/myhespi-job.json'))['job_id'])
PY
)

curl -L -X GET "http://localhost:5001/api/v1/jobs/${JOB_ID}/export/dwc.csv" \
  -H "Authorization: Bearer dev-token" \
  -o /tmp/dwc.csv
```

## 7) PyCharm run configuration

Create Python Run Configuration:

- Module name: `myhespi.app`
- Working directory: `/Users/pokorny/PyEnv/hespi`
- Interpreter: `/Users/pokorny/PyEnv/hespi/.venv/bin/python`
- Environment variables: `MYHESPI_API_TOKENS=dev-token`

## 8) Troubleshooting

### `ModuleNotFoundError: No module named 'flask'`

You are using a different interpreter than the one with dependencies.

Fix:
- activate `.venv`,
- run with `python -m myhespi.app`,
- in PyCharm select `.venv/bin/python`.

### `bad interpreter .../.venv/bin/python3: no such file or directory`

Virtualenv points to an old interpreter.
Recreate `.venv` (see section 2).

### `missing_runtime_dependency` (e.g. `rich`, `pandas`)

Full HESPI runtime is not installed in current env.
Install:

```bash
pip install -r myhespi/requirements-hespi.txt
```

### pip warnings about invalid metadata (`uvicorn`, `click>=7.*`)

Use:

```bash
pip install -U "pip<24.1"
```

### `ReadTimeoutError` during large downloads (e.g. torch wheel)

Use longer timeout and retries:

```bash
pip install --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt
```

