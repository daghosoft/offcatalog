FROM python:3.12-slim

ARG OFFCAT_UID=1000
ARG OFFCAT_GID=1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OFFCAT_WORK_DIR=/data/work \
    OFFCAT_OUTPUT_DIR=/data/output

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY offcatalog ./offcatalog

# utente non root; le cartelle dati vengono montate dall'host (devono essere scrivibili da questo utente)
RUN groupadd -g ${OFFCAT_GID} offcat && useradd -u ${OFFCAT_UID} -g offcat -M -s /usr/sbin/nologin offcat \
    && mkdir -p /data/work /data/output && chown offcat:offcat /data/work /data/output
USER offcat

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# un solo worker: la sync gira in un processo separato lanciato dal web
CMD ["uvicorn", "offcatalog.app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
