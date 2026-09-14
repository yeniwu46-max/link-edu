#!/usr/bin/env bash
set -euo pipefail
podman run --rm -v /etc/letsencrypt-link:/etc/letsencrypt:Z -v /var/lib/letsencrypt-link:/var/lib/letsencrypt:Z -v /www/wwwroot/letsencrypt:/webroot:z docker.io/certbot/certbot:latest renew --quiet
/usr/sbin/nginx -t
systemctl reload nginx
