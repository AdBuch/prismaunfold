# PrismUnfold collector: goose (open-source agent, provider chosen at run time)
# Build from the collectors/ directory: docker build -f goose/Dockerfile -t prismunfold/collector-goose .
# Based on the project's published image; pin GOOSE_TAG to a release for reproducible builds.
ARG GOOSE_TAG=latest
FROM ghcr.io/aaif-goose/goose:${GOOSE_TAG}

USER root
RUN mkdir -p /work /out && chown goose /work /out

COPY --chmod=755 common/collect.sh common/worker.sh /opt/collector/
COPY common/assignment.md common/report.schema.json /opt/collector/

ENV AGENT=goose
USER goose
WORKDIR /work
ENTRYPOINT ["/opt/collector/collect.sh"]
