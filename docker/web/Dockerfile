# PrismUnfold web: serves the exported JSON read-only from the shared /site volume.
# Build from the repository root: docker build -f docker/web/Dockerfile -t prismunfold/web .
FROM nginxinc/nginx-unprivileged:stable-alpine
COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
