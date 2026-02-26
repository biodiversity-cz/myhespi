# myHESPI

Flask aplikace, která obaluje knihovnu
[HESPI](https://github.com/rbturnbull/hespi) a poskytuje:

- webové rozhraní pro upload herbářového listu a zobrazení výsledků,
- verzované REST API (`/api/v1/*`) s tokenovou autentizací,
- editovatelný náhled a export Darwin Core (DwC) CSV.

## Rychlý start (vývoj)

```bash
cd /cesta/k/repozitáři
pip install -e ".[dev]"
# Pro plný HESPI runtime (Tesseract, modely, torch…):
# pip install hespi>=0.6.1
export MYHESPI_API_TOKENS="dev-token"
python -m myhespi
```

Aplikace poběží na `http://localhost:5001`.

## Konfigurace (proměnné prostředí)

| Proměnná | Výchozí | Popis |
|---|---|---|
| `MYHESPI_API_TOKENS` | *(prázdné)* | Čárkou oddělené API tokeny |
| `MYHESPI_MAX_UPLOAD_MB` | `50` | Maximální velikost uploadu v MB |
| `MYHESPI_PROCESS_TIMEOUT_SECONDS` | `60` | Timeout zpracování HESPI |
| `MYHESPI_RETENTION_DAYS` | `30` | Retence dočasných souborů |
| `MYHESPI_TEMP_ROOT` | `myhespi-temp` | Kořenový adresář pro dočasné soubory |
| `HESPI_USE_GPU` | `1` | Použít GPU (1/true/yes) |
| `HESPI_LLM_MODEL` | `none` | LLM model (např. `gpt-4o`); `none` = vypnuto |
| `OPENAI_API_KEY` | *(prázdné)* | API klíč pro OpenAI (vyžadováno jen s LLM) |

## Testy

```bash
pip install -e ".[dev]"
pytest -q
```

## Produkční nasazení

```bash
pip install gunicorn
gunicorn myhespi.wsgi:app -b 0.0.0.0:8000
```

## API – rychlý příklad

```bash
# Health check
curl -s http://localhost:5001/api/v1/health \
  -H "Authorization: Bearer dev-token"

# Zpracování obrázku
curl -s -X POST http://localhost:5001/api/v1/jobs \
  -H "Authorization: Bearer dev-token" \
  -F "image=@herbarium_sheet.jpg"

# OpenAPI specifikace
curl -s http://localhost:5001/api/v1/openapi.yaml
```

## Aktualizace HESPI

Modul `hespi/` v kořeni repozitáře pochází z
[rbturnbull/hespi](https://github.com/rbturnbull/hespi).
Pro aktualizaci na novější verzi stáhněte novou kopii adresáře `hespi/`
z upstream repozitáře, nebo nainstalujte z PyPI:

```bash
pip install --upgrade hespi
```
