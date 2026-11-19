# offcatalog

Builds a clean, searchable SQLite catalog from the [Open Food Facts](https://world.openfoodfacts.org) export,
with a small web panel to start, monitor, pause and resume the sync, and an HTTP endpoint for an external cron.

Genera un catalogo SQLite pulito e ricercabile dall'export di Open Food Facts, con un piccolo pannello web per
avviare, monitorare, interrompere e riprendere la sincronizzazione, e un endpoint HTTP per un cron esterno.

## Avvio

### Con Docker
```
cd docker
cp .env.example .env.local     # poi adattare cartelle, password, porta
./run.sh
```
Il pannello e' su `http://127.0.0.1:<OFFCAT_PORT>/` (HTTP Basic). La prima sincronizzazione parte solo a mano
(pulsante Avvia) o da `POST /api/sync`: mai da sola. Servono circa 12 GB liberi nella cartella di lavoro.

### In locale (sviluppo)
```
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
OFFCAT_NO_AUTH=1 OFFCAT_WORK_DIR=./work OFFCAT_OUTPUT_DIR=./output \
  .venv/bin/uvicorn offcatalog.app:app_factory --factory --port 8080
.venv/bin/python -m pytest
```

## Come funziona
1. Controllo della sorgente (HEAD: ETag, Last-Modified, dimensione): se l'export non e' cambiato, nessuna novita'.
2. Download con ripresa (HTTP Range) e decompressione.
3. Filtro a blocchi di 5.000 righe: paese, barcode valido, nome, kcal plausibili (kJ convertiti), coerenza
   kcal/macro, doppioni. Ogni blocco salva righe e segnaposto nello stesso commit: la sync si interrompe e riprende
   senza perdere ne' duplicare righe.
4. Indice FTS5 (`unicode61 remove_diacritics 2`, prefissi), controlli di plausibilita', pubblicazione atomica
   (`os.replace` di un `.tmp` nella cartella di uscita). Se i controlli falliscono il catalogo pubblicato resta quello vecchio.
5. La sync gira in un processo separato a priorita' bassa (`nice`), uno alla volta (file di lock).

## API (per un cron sulla stessa macchina)
Senza credenziali, ma solo dagli indirizzi di `OFFCAT_API_ALLOW`; da ogni altro indirizzo `403`.
1. `POST /api/sync` (facoltativo `?force=1`): `202` avviata, `200` nessuna novita', `409` gia' in corso o interrotta
   in attesa di ripresa. Risponde subito con `run_id` e il link per seguire l'esecuzione.
2. `GET /api/runs/<run_id>`: stato, fase, percentuale, contatori, scarti per motivo, controlli, errore.
3. `GET /api/status`: stato corrente e catalogo pubblicato.
4. `GET /health`: senza autenticazione.

Esempio: `curl -fsS -X POST http://127.0.0.1:8080/api/sync`, poi interrogare `/api/runs/<run_id>` ogni 30-60 s.

## Schema del catalogo (`off_catalog.db`)
1. `products`: `code` (PK), `name`, `brand`, `kcal_100g`, `fat_100g`, `saturated_fat_100g`, `carbs_100g`,
   `sugars_100g`, `fiber_100g`, `proteins_100g`, `salt_100g`, `serving_size`, `serving_g`, `nutriscore_grade`,
   `nova_group`, `last_modified_t`.
2. `products_fts`: FTS5 (tabella con contenuto esterno) su `name` e `brand`; si unisce a `products` con
   `products_fts.rowid = products.rowid`. Aprire il file in sola lettura e non eseguire `VACUUM`, che puo'
   rinumerare i rowid.
3. `meta`: `schema_version`, `built_at`, `source_url`, `source_etag`, `source_last_modified`, `rows_read`,
   `products`, `scarti_*`, `countries`, `setting_*` (impostazioni di filtro e controllo usate), `offcatalog_version`, `attribution`. Chi legge controlla `schema_version`.

## Configurazione
Solo variabili d'ambiente; l'elenco commentato e' in `docker/.env.example`. Nessun segreto nel repository.
1. `OFFCAT_WORK_DIR`, `OFFCAT_OUTPUT_DIR`: cartelle di lavoro e di uscita.
2. `OFFCAT_PANEL_USER`, `OFFCAT_PANEL_PASSWORD`: obbligatorie, altrimenti l'app non parte (salvo `OFFCAT_NO_AUTH=1`).
3. `OFFCAT_API_ALLOW`: indirizzi ammessi alle API (default `127.0.0.1` e `172.16.0.0/12`).
4. `OFFCAT_COUNTRIES` (default `en:italy`), `OFFCAT_MIN_PRODUCTS` (default 100000), `OFFCAT_SOURCE_URL`,
   `OFFCAT_KEEP_WORK`, `OFFCAT_PORT`, `OFFCAT_BIND`, `COMPOSE_PROJECT_NAME`, `OFFCAT_CONTAINER_NAME`, `TZ`.
5. `OFFCAT_SUBNET` (default `172.31.250.0/24`) e `OFFCAT_IP` (default `172.31.250.5`): rete Docker dedicata
   (`offcatalog_net`) e IP fisso del container, utile per regole firewall verso il container. L'IP deve essere
   dentro la subnet. Cambiare rete a un container esistente richiede di ricrearlo (`docker compose down`, poi `up`).
   Le chiamate dall'host alla porta pubblicata arrivano dal gateway della rete dedicata: con una subnet dentro
   `172.16.0.0/12` sono coperte dal default di `OFFCAT_API_ALLOW`. Con una subnet fuori da quel range, aggiungerla
   a `OFFCAT_API_ALLOW`.

6. Dalla pagina `/settings` del pannello (link "Impostazioni") si cambiano anche `countries`, `kcal_min`, `kcal_max`, `coherence_pct`,
   `coherence_abs`, `min_products`, `min_ratio`, `keep_work`. Precedenza: valore salvato dal pannello, poi variabile
   d'ambiente, poi default del codice; "Ripristina" cancella la modifica di un campo. Le modifiche sono bloccate
   solo mentre una sync e' in esecuzione (la pagina mostra un avviso, il salvataggio risponde 409). Le impostazioni usate
   da ogni sync sono nel campo `settings` di `GET /api/runs/<id>` e nella tabella `meta` del catalogo
   (`setting_*`; i paesi restano in `countries`). Tutti gli altri parametri restano solo da variabili d'ambiente.

Il pannello e le API sono in HTTP semplice: la password Basic viaggia in chiaro. Non esporre la porta al mondo:
limitarla con il firewall agli indirizzi di chi gestisce il servizio.

## Licenze
1. Codice: MIT (vedi `LICENSE`).
2. Dati: il catalogo generato contiene dati di Open Food Facts ed e' un database derivato distribuito sotto
   [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Chi lo usa deve citare
   Open Food Facts (openfoodfacts.org). Il metodo completo di costruzione e' questo repository.
3. Il repository non contiene dati di Open Food Facts: li scarica l'applicazione.
