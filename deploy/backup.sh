#!/usr/bin/env bash
set -euo pipefail
umask 077
dest="/opt/link-demo/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$dest"
podman exec link-demo-db sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers link' > "$dest/link.sql"
tar -czf "$dest/instance.tar.gz" -C /opt/link-demo/shared instance
# instance/ includes RAG originals under instance/rag/files/ (vectors remain in MySQL kb_chunks)
cp /opt/link-demo/shared/runtime.env /opt/link-demo/shared/mysql.env "$dest/"
readlink -f /opt/link-demo/current > "$dest/release.txt"
sha256sum "$dest"/* > "$dest/SHA256SUMS"
echo "Private backup created: $dest"
