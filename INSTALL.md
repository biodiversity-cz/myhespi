# INSTALL.md

Kompletní návod pro instalaci a spuštění `hespi` + `myhespi` v tomto repozitáři.

## 0) Rychlá instalace (doporučeno)

Z kořenového adresáře repozitáře spusťte:

```bash
bash scripts/install_full_stack.sh
```

Skript:
- vytvoří `.venv`,
- nastaví kompatibilní nástroje pro balíčkování,
- nainstaluje plné runtime závislosti pro `hespi` + `myhespi`.

## 1) Předpoklady

- OS: macOS (ověřeno na Apple Silicon)
- Python: `3.11.x` (doporučeno)
- kořen repozitáře: `/Users/pokorny/PyEnv/hespi`

> Poznámka: `hespi` deklaruje `>=3.10,<3.12`. Python `3.11` je v tomto setupu nejbezpečnější volba.

## 2) Ruční vytvoření virtuálního prostředí

Z kořenového adresáře repozitáře:

```bash
cd /Users/pokorny/PyEnv/hespi
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

Pokud je `.venv` po změně interpreteru rozbité, vytvořte ho znovu:

```bash
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
```

## 3) Ruční instalační profily

### A) Pouze myHESPI (web/API + testy)

```bash
pip install -r myhespi/requirements-dev.txt
```

Tento profil stačí pro:
- spuštění aplikace,
- web/API routy,
- testy s mockovaným zpracováním HESPI.

### B) Plný runtime (myHESPI + lokální HESPI processing)

Kvůli starším metadata u některých tranzitivních balíčků používejte `pip<24.1`:

```bash
pip install -U "pip<24.1"
pip install --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt
```

Pro méně stabilní síť můžete přidat:

```bash
pip install --progress-bar off --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt
```

## 4) Spuštění testů

```bash
pytest myhespi/tests -q
```

## 5) Spuštění aplikace

Z kořenového adresáře repozitáře s aktivovaným `.venv`:

```bash
export MYHESPI_API_TOKENS="dev-token"
python -m myhespi.app
```

LLM je ve výchozím stavu vypnuté (`HESPI_LLM_MODEL=none`).
Pokud chcete zapnout LLM korekce, nastavte obě proměnné:

```bash
export HESPI_LLM_MODEL="gpt-4o"
export OPENAI_API_KEY="..."
```

URL aplikace:
- Web: `http://localhost:5001/`
- API: `http://localhost:5001/api/v1/`

## 6) Rychlý smoke test

Health endpoint:

```bash
curl -s -X GET "http://localhost:5001/api/v1/health" \
  -H "Authorization: Bearer dev-token"
```

Zpracování obrázku + export CSV:

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

## 7) Konfigurace běhu v PyCharm

Vytvořte Python Run Configuration:

- Module name: `myhespi.app`
- Working directory: `/Users/pokorny/PyEnv/hespi`
- Interpreter: `/Users/pokorny/PyEnv/hespi/.venv/bin/python`
- Environment variables: `MYHESPI_API_TOKENS=dev-token`

## 8) Řešení běžných problémů

### `ModuleNotFoundError: No module named 'flask'`

Používáte jiný interpreter než ten, kde jsou nainstalované závislosti.

Postup:
- aktivujte `.venv`,
- spusťte aplikaci přes `python -m myhespi.app`,
- v PyCharm vyberte interpreter `.venv/bin/python`.

### `bad interpreter .../.venv/bin/python3: no such file or directory`

Virtuální prostředí ukazuje na starý interpreter.
Vytvořte `.venv` znovu (viz sekce 2).

### `missing_runtime_dependency` (např. `rich`, `pandas`)

V aktuálním prostředí není nainstalovaný plný HESPI runtime.

```bash
pip install -r myhespi/requirements-hespi.txt
```

### Pip warningy o nevalidních metadata (`uvicorn`, `click>=7.*`)

Použijte:

```bash
pip install -U "pip<24.1"
```

### `ReadTimeoutError` při stahování velkých balíčků (např. torch wheel)

Použijte delší timeout a retry:

```bash
pip install --default-timeout=600 --retries=10 -r myhespi/requirements-hespi.txt
```

