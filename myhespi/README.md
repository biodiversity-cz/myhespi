# myHESPI

Flask aplikace, která obaluje `hespi` a poskytuje:

- jednoduché webové rozhraní pro upload a zobrazení výsledků,
- verzované API (`/api/v1/*`) s tokenovou autentizací,
- export Darwin Core CSV.

Poznámka: `hespi` interně používá `pandas`, proto je uvedený i v `myhespi` závislostech.
Kompatibilita je laděná pro Python 3.10/3.11 a Flask 2.2.x (kvůli závislostem HESPI stacku).

Pro instalaci celého stacku (hespi + myhespi) doporučujeme:

```bash
bash scripts/install_full_stack.sh
```

## Spuštění (vývoj)

```bash
cd /path/to/hespi-repo
python3 -m pip install -r myhespi/requirements.txt
python3 -m myhespi.app
```

`requirements.txt` instaluje pouze závislosti `myhespi` vrstvy (web/API + testy).
Pro plný runtime včetně lokální instalace `hespi` použijte:

```bash
python3 -m pip install -U "pip<24.1"
python3 -m pip install -r myhespi/requirements-hespi.txt
```

`requirements-hespi.txt` obsahuje kompatibilní piny (`fastai>=2.7,<2.8`, `spacy>=3.8,<4`), aby pip nebacktrackoval na staré nekompatibilní kombinace.
Upozornění: kvůli starším metadata závislostí v HESPI stacku je pro tuto instalaci potřeba `pip<24.1`.

Pro testy:

```bash
python3 -m pip install -r myhespi/requirements-dev.txt
pytest myhespi/tests -q
```

## Základní konfigurace

- `MYHESPI_API_TOKENS`
- `MYHESPI_MAX_UPLOAD_MB` (default `50`)
- `MYHESPI_PROCESS_TIMEOUT_SECONDS` (default `60`)
- `MYHESPI_RETENTION_DAYS` (default `30`)
- `MYHESPI_TEMP_ROOT` (default `myhespi-temp`)
- `HESPI_LLM_MODEL` (default `none`; set e.g. `gpt-4o` only if API key is configured)
- `OPENAI_API_KEY` (required only when LLM model is enabled)

Povolené vstupní obrázky: JPEG, PNG, TIFF, JP2.

## API rychlý příklad

```bash
curl -X GET "http://localhost:5001/api/v1/health" \
  -H "Authorization: Bearer <token>"
```

OpenAPI specifikace:

- `GET /api/v1/openapi.yaml`

## Smoke test checklist

1. Nastavte token a spusťte aplikaci:

```bash
export MYHESPI_API_TOKENS="dev-token"
python3 -m myhespi.app
```

2. Otestujte health endpoint:

```bash
curl -s -X GET "http://localhost:5001/api/v1/health" \
  -H "Authorization: Bearer dev-token"
```

3. Otestujte synchronní zpracování a export CSV:

```bash
curl -s -X POST "http://localhost:5001/api/v1/jobs" \
  -H "Authorization: Bearer dev-token" \
  -F "image=@/absolute/path/to/sample.jpg" > /tmp/myhespi-job.json
JOB_ID=$(python3 - <<'PY'
import json
print(json.load(open('/tmp/myhespi-job.json'))['job_id'])
PY
)
curl -L -X GET "http://localhost:5001/api/v1/jobs/${JOB_ID}/export/dwc.csv" \
  -H "Authorization: Bearer dev-token" -o /tmp/dwc.csv
```
