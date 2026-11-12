# PrismUnfold collector: Mistral Vibe
# Build from the collectors/ directory: docker build -f vibe/Dockerfile -t prismunfold/collector-vibe .
FROM python:3.12-slim-bookworm

ARG VIBE_VERSION=
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "mistral-vibe${VIBE_VERSION:+==$VIBE_VERSION}" \
 && useradd --create-home --uid 1000 collector \
 && mkdir -p /work /out && chown collector:collector /work /out

COPY --chmod=755 common/collect.sh /opt/collector/collect.sh
COPY common/assignment.md common/report.schema.json /opt/collector/

ENV AGENT=vibe
USER collector
WORKDIR /work
ENTRYPOINT ["/opt/collector/collect.sh"]
