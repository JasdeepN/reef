#!/usr/bin/env bash
set -euo pipefail

# Sync MySQL database data from one environment to another using mysqldump
# Usage: sync_db.sh <source_env> <target_env>
# Environments: prod, dev, test

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <source_env> <target_env>"
  echo "  Envs: prod, dev, test"
  exit 1
fi

source_env=$1
target_env=$2

# Configuration maps
declare -A HOST_MAP=( [prod]="127.0.0.1" [dev]="127.0.0.1" [test]="127.0.0.1" )
declare -A PORT_MAP=( [prod]=3142 [dev]=3306 [test]=3310 )
declare -A PASS_MAP=( [prod]="${MYSQL_ROOT_PASSWORD:-prodroot2025!}" [dev]="${MYSQL_ROOT_PASSWORD:-devroot2025!}" [test]="${MYSQL_ROOT_PASSWORD:-testroot2025!}" )
DB_NAME="${DB_NAME:-reef}"

# Dump source database
echo "Dumping database from '$source_env' (host=${HOST_MAP[$source_env]}:${PORT_MAP[$source_env]})..."
mysqldump -h "${HOST_MAP[$source_env]}" -P "${PORT_MAP[$source_env]}" \
  -u root -p"${PASS_MAP[$source_env]}" \
  "$DB_NAME" > /tmp/reefdb_dump.sql

# Restore into target database
echo "Restoring dump to '$target_env' (host=${HOST_MAP[$target_env]}:${PORT_MAP[$target_env]})..."
mysql -h "${HOST_MAP[$target_env]}" -P "${PORT_MAP[$target_env]}" \
  -u root -p"${PASS_MAP[$target_env]}" \
  "$DB_NAME" < /tmp/reefdb_dump.sql

# Cleanup
echo "Sync complete. Removing temporary dump."
rm /tmp/reefdb_dump.sql
