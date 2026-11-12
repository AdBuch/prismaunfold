# PrismUnfold collector: OpenAI Codex CLI
# Build from the collectors/ directory: docker build -f codex/Dockerfile -t prismunfold/collector-codex .
FROM node:22-bookworm-slim

ARG CODEX_VERSION=latest
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @openai/codex@${CODEX_VERSION} \
 && mkdir -p /work /out && chown node:node /work /out

COPY --chmod=755 common/collect.sh /opt/collector/collect.sh
COPY common/assignment.md common/report.schema.json /opt/collector/

ENV AGENT=codex
USER node
WORKDIR /work
ENTRYPOINT ["/opt/collector/collect.sh"]
