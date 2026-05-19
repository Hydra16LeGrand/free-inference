#!/usr/bin/env bash
# Backup PostgreSQL (LiteLLM metadata : users, keys, spend logs).
# Usage: source .env && ./scripts/backup_db.sh [output_dir]
# Recommended cron: daily at 2AM: 0 2 * * * cd /path/to/repo && ./scripts/backup_db.sh /backups/litellm

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="$OUTPUT_DIR/litellm_backup_${TIMESTAMP}.sql"

# Load env if available
if [ -f "$PROJECT_DIR/.env" ]; then
    # shellcheck source=/dev/null
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

if [ -z "${POSTGRES_PASSWORD:-}" ] || [ -z "${POSTGRES_DB:-}" ]; then
    echo "ERROR: POSTGRES_PASSWORD and POSTGRES_DB must be set (via .env or env)." >&2
    exit 1
fi

HOST="${POSTGRES_HOST:-127.0.0.1}"
PORT="${POSTGRES_PORT:-5433}"
USER="${POSTGRES_USER:-litellm}"
DB="$POSTGRES_DB"

mkdir -p "$OUTPUT_DIR"

echo "[backup] Dumping $DB from $HOST:$PORT..."
docker exec inference-postgres pg_dump \
    -h localhost \
    -p 5432 \
    -U "$USER" \
    -d "$DB" \
    -F p \
    > "$DUMP_FILE"

echo "[backup] Compressed to $DUMP_FILE.gz"
gzip "$DUMP_FILE"

# Keep last 14 backups, delete older ones
find "$OUTPUT_DIR" -name 'litellm_backup_*.sql.gz' -type f | sort | head -n -14 | xargs -r rm -f

echo "[backup] Done. Retained last 14 backups."
