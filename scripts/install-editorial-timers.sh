#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ $EUID == 0 ]] || { echo "Run with sudo" >&2; exit 2; }
[[ $(pwd -P) == /opt/unfold ]] || { echo "Expected /opt/unfold" >&2; exit 2; }
id adrian >/dev/null
systemd-analyze verify deploy/systemd/unfold-editorial-{generate,publish}.{service,timer}
install -m 644 deploy/systemd/unfold-editorial-{generate,publish}.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now unfold-editorial-generate.timer unfold-editorial-publish.timer
systemctl list-timers 'unfold-editorial-*' --all --no-pager
