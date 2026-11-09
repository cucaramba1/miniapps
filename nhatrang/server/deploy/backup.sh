#!/bin/sh
# Ночной бэкап на VPS (cron: 20 3 * * * /opt/nhatrang/server/deploy/backup.sh). Хранит 14 копий БД + зеркало фото.
set -eu
D=/opt/nhatrang/data; B=/opt/nhatrang/backups
mkdir -p "$B"
sqlite3 "$D/app.db" ".backup '$B/app-$(date +%F).db'"
gzip -f "$B/app-$(date +%F).db"
ls -1t "$B"/app-*.db.gz | tail -n +15 | xargs -r rm --
rsync -a --delete "$D/photos/" "$B/photos/"
