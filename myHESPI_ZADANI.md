# Zadání: integrační modul myHESPI (segmentace fotografií herbářových etiket)

## Účel

Samostatná webová aplikace **myHESPI**, která:
1. Umožní uživateli nahrát fotografii herbářové etikety (nebo celého listu).
2. Spustí na ní pipeline **HESPI** (https://github.com/rbturnbull/hespi) pro segmentaci a rozpoznání textu.
3. Zobrazí výsledek: náhled fotky, rozpoznané segmenty s textem a náhled atributů ve formátu Darwin Core (DwC).
4. Poskytne export do formátu Darwin Core (CSV, popř. DwCA ZIP).
5. Bude běžet **odděleně** od stávajícího webu tools.biodiversity.cz (tools na něj pouze odkazuje).

Reference k diskuzi a rozhodnutím: projekt tools.biodiversity.cz, konverzace o integraci HESPI a DwC.

---

## Technologický stack

- **Backend:** Python, Flask.
- **Šablony:** Jinja2.
- **Frontend / vzhled:** čistý **Bootstrap 5** (žádná vlastní designová knihovna).
- **Databáze:** **nepoužívat** – stav se neukládá mezi requesty, vše v rámci jednoho synchronního zpracování a temp souborů.

---

## Funkční požadavky

### 1. HESPI integrace

- Zjistit, zda HESPI nabízí **Python API** (např. třída `Hespi`, metoda `detect()`). Pokud ano, použít ho; pokud ne, volat HESPI přes **CLI** (subprocess).
- HESPI nainstalovat v prostředí aplikace (pip/poetry). Požadavky HESPI (Tesseract, první stažení vah modelů) zdokumentovat v README.
- Konfigurace HESPI přes **proměnné prostředí** (ne hardcodovat): např. `OPENAI_API_KEY`, volitelně `HESPI_USE_GPU`, `HESPI_LLM_MODEL`. API klíč doplní provozovatel do prostředí.

### 2. Vrstva HESPI CSV → Darwin Core

- HESPI produkuje CSV (`hespi-results.csv`) s poli: family, genus, species, infrasp_taxon, authority, collector_number, collector, locality, geolocation, year, month, day (a další).
- Implementovat v aplikaci **překlad** z tohoto CSV (nebo z DataFrame vráceného z HESPI API) na **Darwin Core Occurrence**:
  - Mapování polí podle dohodnuté tabulky (family → family, genus → genus, species → specificEpithet, collector → recordedBy, locality → locality, year/month/day → eventDate, geolocation → decimalLatitude/decimalLongitude po rozparsování, atd.).
  - Doplnit povinné/doporučené DwC termy: např. basisOfRecord = "PreservedSpecimen", occurrenceID (vygenerovat), scientificName (složit z genus + species + infrasp + authority).
- Výstup této vrstvy: DwC CSV (s hlavičkou podle DwC termů), případně podpora pro DwCA ZIP (např. přes knihovnu typu dwcahandler), pokud je to v rozsahu projektu.

### 3. Průběh použití (synchronní režim)

- Jedna stránka s **formulářem**: upload souboru (fotografie), tlačítko pro odeslání.
- Po odeslání proběhne **synchronně** v rámci téhož HTTP požadavku: uložení souboru do temp složky → spuštění HESPI → načtení výstupu (CSV + vygenerované obrázky segmentů) → převod na DwC → vygenerování výsledkové stránky.
- **Timeout:** pro endpoint zpracování nastavit timeout **60 sekund** (web i API konzistentně).
- Hodnota timeoutu musí být konfigurovatelná přes env (např. `MYHESPI_PROCESS_TIMEOUT_SECONDS`), výchozí hodnota 60.
- Omezení uploadu: maximální velikost souboru **50 MB** a povolené typy (image/jpeg, image/png, image/tiff, image/jp2). Při překročení nebo neplatném typu vrátit srozumitelnou chybu.

### 4. Výsledková stránka

Po úspěšném zpracování zobrazit stránku s:

- **Náhled uploadované fotky** (nebo výstupu HESPI s vykreslenými segmenty – dle dostupnosti z HESPI).
- **Sloupec / sekce s rozpoznanými segmenty:** pro každý segment (např. genus, species, locality, …) zobrazení náhledu oříznutého obrázku (pokud HESPI takové soubory vyprodukuje) a **textového přepisu** pro kontrolu.
- **Náhled atributů ve formátu Darwin Core** (tabulka nebo přehled DwC polí a hodnot).
- **Tlačítko (tlačítka) pro export:** stáhnout DwC CSV; případně DwCA ZIP, pokud je implementováno.

Vzhled: čistě Bootstrap 5 (konzistentní komponenty, responzivita).

### 5. Chybové stavy

- Neplatný nebo příliš velký soubor: zobrazit chybovou hlášku, nic neukládat.
- Pád nebo chyba HESPI (např. neplatný obrázek, OOM): zobrazit uživatelsky srozumitelnou chybu; **vždy** vyčistit temp soubory dané úlohy (vstup i výstupy).

### 6. Úklid temp souborů

- Všechny uploady a výstupy HESPI (vstupní obrázek, výstupní CSV, obrázky segmentů, DwC soubory) ukládat do **dočasného adresáře** – jeden adresář na úlohu (např. s časovým razítkem nebo náhodným identifikátorem v názvu).
- **Periodický úklid při každém requestu:** při obsluze libovolného požadavku (např. na úvodní stránce nebo před zpracováním nového uploadu) projít kořenový temp adresář a **smazat všechny složky starší než 30 dní**. Vstupní i výstupní soubory se mažou **společně** – celá složka úlohy se smaže najednou (žádné oddělování vstupu a výstupu). Uživatel má 30 dní na stažení výsledků z výsledkové stránky; po této lhůtě je celá složka odstraněna.

### 7. API parita s webovou funkcionalitou

- Veškerá funkcionalita dostupná přes webové rozhraní myHESPI musí být dostupná také přes **HTTP API**.
- API musí umožnit stejný průběh jako web: upload vstupního obrázku, spuštění zpracování HESPI, získání strukturovaného výsledku (včetně hodnot pro DwC) a exportních výstupů (DwC CSV, případně DwCA ZIP).
- API musí být **verzované** (např. `/api/v1/...`).
- Přístup do API musí být chráněn pomocí **API tokenů** (komunikace server-server); token se předává v HTTP hlavičce `Authorization: Bearer <token>`.
- API tokeny musí být načítané z konfigurace/env (bez hardcodování), aby bylo možné jejich správu a rotaci bez změny kódu.
- Návrh endpointů a formátů odpovědí má být určen tak, aby bylo možné službu využívat nejen z webu, ale i přímo z externích repozitářů/aplikací voláním API.
- Chybové stavy, limity (typ/velikost souboru, timeout) a pravidla úklidu temp dat musí být konzistentní mezi webem a API.

#### 7.1 Návrh API endpointů (v1)

Autentizace pro všechny `/api/v1/*` endpointy:

- `Authorization: Bearer <token>`
- `Accept: application/json` (u download endpointů odpověď binární soubor)

Endpointy:

1. **Health check**
   - `GET /api/v1/health`
   - Účel: ověření dostupnosti služby.
   - Response `200`:
     - `{ "status": "ok" }`

2. **Spuštění zpracování (synchronně)**
   - `POST /api/v1/jobs`
   - `Content-Type: multipart/form-data`
   - Form field: `image` (povinný; JPEG/PNG/TIFF; max 50 MB)
   - Chování: v rámci jednoho requestu proběhne celý pipeline běh (stejně jako ve webu).
   - Response `200` (`application/json`):
     - `job_id` (ID dočasné úlohy)
     - `status` (`"completed"`)
     - `input_image_url`
     - `segments` (pole segmentů: `label`, `text`, volitelně `image_url`)
     - `dwc` (objekt DwC polí a hodnot)
     - `exports`:
       - `dwc_csv_url` (povinné)
       - `dwca_zip_url` (volitelné; `null`, pokud není implementováno)

3. **Detail výsledku úlohy**
   - `GET /api/v1/jobs/{job_id}`
   - Účel: znovunačtení výsledku během retenční doby (30 dní).
   - Response `200`: stejná struktura jako u `POST /api/v1/jobs`.
   - Response `404`: úloha neexistuje nebo už byla smazána.

4. **Stažení DwC CSV**
   - `GET /api/v1/jobs/{job_id}/export/dwc.csv`
   - Response `200`: `text/csv`, příloha ke stažení.

5. **Stažení DwCA ZIP (volitelné)**
   - `GET /api/v1/jobs/{job_id}/export/dwca.zip`
   - Pokud DwCA není implementováno, vracet `404` s chybovým payloadem.

6. **Stažení vstupního obrázku / segmentů**
   - `GET /api/v1/jobs/{job_id}/files/{filename}`
   - Účel: přístup k obrázkům, na které odkazují `input_image_url` a `segments[].image_url`.
   - Implementace musí bezpečně omezit přístup pouze do adresáře dané úlohy (bez path traversal).

#### 7.2 Jednotný formát chyb API

- Pro chyby API vracet JSON ve formátu:
  - `{ "error": { "code": "<string>", "message": "<human-readable>", "details": { ... } } }`
- Doporučené status kódy:
  - `400` nevalidní request (chybějící field, nevalidní parametry)
  - `401` chybějící nebo neplatný token
  - `403` token bez oprávnění
  - `404` neexistující resource (`job_id`, soubor)
  - `413` soubor větší než 50 MB
  - `415` nepodporovaný media type
  - `422` vstup zpracovatelný, ale semanticky nevalidní
  - `500` neočekávaná interní chyba
  - `504` timeout při běhu HESPI (60 s)

#### 7.3 Konfigurační minimum (env)

- `MYHESPI_API_TOKENS` - seznam povolených API tokenů (např. oddělený čárkou); bez tokenu API neobsluhovat.
- `MYHESPI_MAX_UPLOAD_MB` - výchozí `50`.
- `MYHESPI_PROCESS_TIMEOUT_SECONDS` - výchozí `60`.
- `MYHESPI_RETENTION_DAYS` - výchozí `30`.

---

## Nefunkční požadavky

- Aplikace musí být spustitelná lokálně (pro vývoj a testování) i na serveru (např. gunicorn za reverzní proxy). HESPI (a jeho závislosti včetně Tesseract) běží na **stejném stroji** jako myHESPI.
- Konfigurace (API klíče, volba GPU, atd.) pouze přes env nebo konfigurační soubor, ne v kódu.
- README: popis instalace (včetně Tesseract a prvního stažení vah HESPI), spuštění, konfigurace a stručný popis toho, co aplikace dělá a jak ji propojit s odkazem z tools.biodiversity.cz.

---

## Rozsah a vymezení

- **V rámci zadání:** Flask aplikace myHESPI, integrace HESPI (API nebo CLI), vrstva HESPI CSV → DwC, formulář, synchronní zpracování, výsledková stránka (náhled fotky, segmenty s textem, náhled DwC, export), verzované API s tokeny, úklid po 30 dnech, Bootstrap 5, bez DB.
- **Mimo zadání (není nutné v první verzi):** uživatelské účty, historie úloh, fronta úloh, asynchronní režim s pollingem, vizuální sjednocení s tools.biodiversity.cz (stačí odkaz z tools na URL myHESPI).

---

## Očekávaný výstup projektu

- Repozitář (nebo složka) s fungující Flask aplikací myHESPI.
- Možnost nahrát obrázek, zobrazit výsledek segmentace a textu, zobrazit náhled DwC a stáhnout **DwC CSV** (prioritní výstup; DwCA ZIP volitelně).
- README s návodem na instalaci, konfiguraci a propojení s tools.biodiversity.cz (odkaz na URL myHESPI).
- Zadání je určeno k použití v **jiném repozitáři** než tools.biodiversity.cz; myHESPI je samostatná aplikace.
