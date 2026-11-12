# PrismUnfold collector: Claude Code
# Build from the collectors/ directory: docker build -f claude/Dockerfile -t prismunfold/collector-claude .
FROM node:22-bookworm-slim

ARG CLAUDE_CODE_VERSION=latest
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
 && mkdir -p /work /out && chown node:node /work /out

COPY --chmod=755 common/collect.sh common/worker.sh /opt/collector/
COPY common/assignment.md common/report.schema.json /opt/collector/

ENV AGENT=claude DISABLE_AUTOUPDATER=1
USER node
WORKDIR /work
ENTRYPOINT ["/opt/collector/collect.sh"]
