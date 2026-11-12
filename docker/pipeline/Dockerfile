# PrismUnfold pipeline: plans editions, checks agent reports, keeps the archive, exports JSON.
# Build from the repository root: docker build -f docker/pipeline/Dockerfile -t prismunfold/pipeline .
FROM python:3.12-slim-bookworm

# psycopg is the only dependency outside the standard library (PostgreSQL driver).
RUN pip install --no-cache-dir "psycopg[binary]>=3.2,<4" \
 && useradd --create-home --uid 1000 pipeline \
 && mkdir -p /app /data /site /out /shared && chown pipeline:pipeline /app /data /site /out /shared

WORKDIR /app
COPY src/ /app/src/
COPY config/ /app/config/
COPY catalog/ /app/catalog/
COPY --chmod=755 docker/pipeline/scheduler.sh /app/scheduler.sh

ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER pipeline
ENTRYPOINT ["/app/scheduler.sh"]
