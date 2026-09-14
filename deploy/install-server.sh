#!/usr/bin/env bash
# Run as root from an extracted release. Existing websites are not modified.
set -euo pipefail
release=$(pwd -P)
case "$release" in /opt/link-demo/releases/*) ;; *) echo 'Use /opt/link-demo/releases/VERSION'; exit 1;; esac
test -s /opt/link-demo/shared/runtime.env
test -s /opt/link-demo/shared/mysql.env
mkdir -p /opt/link-demo/shared/instance /opt/link-demo/backups
chmod 700 /opt/link-demo/shared
chmod 600 /opt/link-demo/shared/*.env
chown 10001:10001 /opt/link-demo/shared/instance
podman network exists link-demo || podman network create link-demo
podman volume exists link-demo-db || podman volume create link-demo-db
podman build --pull=never --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.org/simple}" -t localhost/link-demo:competition-20260914 -f deploy/Containerfile .
cat > /etc/systemd/system/link-demo-db.service <<'UNIT'
[Unit]
Description=LINK isolated MySQL
After=network-online.target
Wants=network-online.target
[Service]
Restart=on-failure
RestartSec=5
TimeoutStartSec=180
ExecStartPre=-/usr/bin/podman rm link-demo-db
ExecStart=/usr/bin/podman run --name link-demo-db --network link-demo --network-alias db --memory 512m --env-file /opt/link-demo/shared/mysql.env -v link-demo-db:/var/lib/mysql:Z docker.io/library/mysql:8.4 --innodb-buffer-pool-size=128M --max-connections=40 --performance-schema=OFF
ExecStop=/usr/bin/podman stop -t 30 link-demo-db
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now link-demo-db
ready=false
for i in $(seq 1 90); do
 if podman exec link-demo-db mysqladmin ping --silent >/dev/null 2>&1; then ready=true; break; fi
 sleep 2
done
$ready || { echo 'Database not ready'; exit 1; }
podman run --rm --network link-demo --env-file /opt/link-demo/shared/runtime.env -v /opt/link-demo/shared/instance:/app/backend/instance:Z localhost/link-demo:competition-20260914 python release_admin.py init
cat > /etc/systemd/system/link-demo.service <<'UNIT'
[Unit]
Description=LINK classroom API (one worker, sixteen threads, five classrooms)
After=network-online.target link-demo-db.service
Requires=link-demo-db.service
[Service]
Restart=on-failure
RestartSec=5
TimeoutStartSec=180
ExecStartPre=-/usr/bin/podman rm link-demo-api
ExecStartPre=/usr/bin/podman run --rm --network link-demo --env-file /opt/link-demo/shared/runtime.env -v /opt/link-demo/shared/instance:/app/backend/instance:Z localhost/link-demo:competition-20260914 python release_admin.py recover
ExecStart=/usr/bin/podman run --name link-demo-api --network link-demo --memory 640m --env-file /opt/link-demo/shared/runtime.env -v /opt/link-demo/shared/instance:/app/backend/instance:Z -p 127.0.0.1:5012:5001 localhost/link-demo:competition-20260914
ExecStop=/usr/bin/podman stop -t 45 link-demo-api
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now link-demo
ln -sfn "$release" /opt/link-demo/current
echo 'LINK API installed; configure trusted HTTPS separately.'
