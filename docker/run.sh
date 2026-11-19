#!/usr/bin/env bash
# Avvia offcatalog con docker compose usando docker/.env.local, poi attende /health.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=".env.local"
if [ ! -f "$ENV_FILE" ]; then
  echo "Manca docker/$ENV_FILE: copiare .env.example e adattarlo." >&2
  exit 1
fi

get() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }

missing=0
for var in OFFCAT_WORK_HOST_DIR OFFCAT_OUTPUT_HOST_DIR; do
  if [ -z "$(get "$var")" ]; then echo "Variabile obbligatoria mancante: $var" >&2; missing=1; fi
done
if [ "$(get OFFCAT_NO_AUTH)" != "1" ]; then
  for var in OFFCAT_PANEL_USER OFFCAT_PANEL_PASSWORD; do
    if [ -z "$(get "$var")" ]; then echo "Variabile obbligatoria mancante: $var (o OFFCAT_NO_AUTH=1)" >&2; missing=1; fi
  done
fi
[ "$missing" -eq 0 ] || exit 1

mkdir -p "$(get OFFCAT_WORK_HOST_DIR)" "$(get OFFCAT_OUTPUT_HOST_DIR)"

docker compose --env-file "$ENV_FILE" -f docker-compose.yml up -d --build

PORT="$(get OFFCAT_PORT)"; PORT="${PORT:-8080}"
BIND="$(get OFFCAT_BIND)"; BIND="${BIND:-127.0.0.1}"
echo "Attendo /health su ${BIND}:${PORT} ..."
for _ in $(seq 1 60); do
  if curl -fsS "http://${BIND}:${PORT}/health" >/dev/null 2>&1; then
    echo "offcatalog attivo."
    exit 0
  fi
  sleep 1
done
echo "offcatalog non risponde su /health entro 60 secondi." >&2
docker compose --env-file "$ENV_FILE" -f docker-compose.yml logs --tail=50 >&2 || true
exit 1
