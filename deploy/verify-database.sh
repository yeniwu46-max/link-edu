#!/usr/bin/env bash
# Non-destructive: new validation schemas only; never drops or truncates databases.
set -euo pipefail
umask 077
stamp=$(date -u +%Y%m%d%H%M%S)
fresh="link_verify_${stamp}"
restore="link_restore_${stamp}"
case "$fresh:$restore" in link_verify_[0-9]*:link_restore_[0-9]*) ;; *) exit 1;; esac
podman exec link-demo-db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "$1"' sh "CREATE DATABASE $fresh CHARACTER SET utf8mb4; CREATE DATABASE $restore CHARACTER SET utf8mb4; GRANT ALL ON $fresh.* TO 'link'@'%'; GRANT ALL ON $restore.* TO 'link'@'%';"
# The application container receives the existing private environment; only schema is changed.
podman run --rm --network link-demo --env-file /opt/link-demo/shared/runtime.env -e VERIFY_SCHEMA="$fresh" localhost/link-demo:competition-20260914 python -c '
import os
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("/link?", "/"+os.environ["VERIFY_SCHEMA"]+"?")
from release_admin import initialize, recover
initialize(); initialize()
from app import app
from models import User,Course,Resource
from extensions import db
from sqlalchemy import inspect
with app.app_context():
 assert User.query.count()==0 and Course.query.count()>0 and Resource.query.count()>0
 print("Fresh schema counts:",len(inspect(db.engine).get_table_names()),Course.query.count(),Resource.query.count())
recover()
'
mkdir -p /opt/link-demo/validation
dump="/opt/link-demo/validation/$fresh.sql"
podman exec link-demo-db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction "$1"' sh "$fresh" > "$dump"
podman exec -i link-demo-db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$1"' sh "$restore" < "$dump"
podman run --rm --network link-demo --env-file /opt/link-demo/shared/runtime.env -e VERIFY_SCHEMA="$restore" localhost/link-demo:competition-20260914 python -c '
import os
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("/link?", "/"+os.environ["VERIFY_SCHEMA"]+"?")
from app import app
from models import User,Course,Resource
from extensions import db
from sqlalchemy import inspect
with app.app_context():
 assert User.query.count()==0 and Course.query.count()>0 and Resource.query.count()>0
 print("Restored schema counts:",len(inspect(db.engine).get_table_names()),Course.query.count(),Resource.query.count())
'
sha256sum "$dump"
echo "Validated fresh install, idempotent catalog, migration entrypoint and SQL restore: $fresh / $restore"
