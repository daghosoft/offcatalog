# offcatalog

Builds a clean, searchable SQLite catalog from the [Open Food Facts](https://world.openfoodfacts.org) export,
with a small web panel to start, monitor, pause and resume the sync, and an HTTP endpoint for an external cron.

Genera un catalogo SQLite pulito e ricercabile dall'export di Open Food Facts, con un piccolo pannello web per
avviare, monitorare, interrompere e riprendere la sincronizzazione, e un endpoint HTTP per un cron esterno.

## Stato
In sviluppo: prima versione in preparazione.

## Come funziona (in breve)
1. Scarica l'export CSV di Open Food Facts (ripresa del download se si interrompe).
2. Filtra i prodotti (paese, barcode valido, nome, kcal plausibili, coerenza kcal/macro, doppioni).
3. Costruisce un nuovo DB SQLite accanto a quello pubblicato, a blocchi riprendibili, con indice di testo FTS5.
4. Se il nuovo DB supera i controlli, sostituisce quello pubblicato in modo atomico.

## Licenze
1. Codice: MIT (vedi `LICENSE`).
2. Dati: il catalogo generato contiene dati di Open Food Facts ed e' un database derivato distribuito sotto
   [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Chi lo usa deve citare
   Open Food Facts (openfoodfacts.org). Il metodo completo di costruzione e' questo repository.
3. Il repository non contiene dati di Open Food Facts: li scarica l'applicazione.

## Configurazione
Solo tramite variabili d'ambiente (esempio in `.env.example`, quando ci sara'). Nessun segreto nel repository.
