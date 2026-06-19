#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-./artifacts/redis-backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/redis-backup-${TIMESTAMP}.rdb"

mkdir -p "${BACKUP_DIR}"

echo "Triggering Redis background save..."
docker compose exec -T redis redis-cli BGSAVE

echo "Waiting for save to complete..."
until docker compose exec -T redis redis-cli LASTSAVE | grep -q '[0-9]'; do
  sleep 1
done
sleep 2

echo "Copying RDB snapshot to ${BACKUP_FILE}"
docker compose cp "redis:/data/dump.rdb" "${BACKUP_FILE}"

echo "Backup complete: ${BACKUP_FILE}"