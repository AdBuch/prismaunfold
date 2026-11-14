# PrismUnfold web: builds the newspaper frontend and serves it together with the
# pipeline's JSON API, which is mounted read-only at /site.
# Build from the repository root: docker build -f docker/web/Dockerfile -t prismunfold/web .
FROM node:22-bookworm-slim AS build
WORKDIR /frontend
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY frontend/package.json ./
# No lockfile is committed yet, so versions float within the ranges in package.json.
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run typecheck && npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist/ /usr/share/nginx/html/
EXPOSE 8080
