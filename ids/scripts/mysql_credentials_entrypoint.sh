#!/bin/bash
# Entrypoint wrapper for every MySQL container (production, honeypot pools,
# pool_manager's runtime pools): makes the accounts follow the environment on
# EVERY start, not only on the first one.
#
# The stock entrypoint applies MYSQL_ROOT_PASSWORD / MYSQL_USER /
# MYSQL_PASSWORD only when it initialises an empty data dir. Pool data dirs
# are copied from production's, so without this they would keep production's
# users, root password and root@'%' -- and rotating a password in .env would
# never reach an existing database. Here, on an initialised data dir, mysqld
# runs an --init-file before it accepts connections that:
#   * sets root@localhost to MYSQL_ROOT_PASSWORD,
#   * drops root@'%' (root logs in from inside the container only; with
#     MYSQL_ROOT_HOST=localhost a fresh init never creates it either),
#   * sets MYSQL_USER@'%' to MYSQL_PASSWORD.
# An empty data dir is left to the stock entrypoint: it initialises with an
# empty root password over the socket, which an early --init-file would break.
#
# Usage (compose `command:`):
#   bash /mysql_credentials_entrypoint.sh mysqld --some-option ...
set -euo pipefail

DATADIR=/var/lib/mysql
rm -f "$DATADIR/placeholder"   # left by init_setup so the volume isn't empty

if [ -d "$DATADIR/mysql" ]; then
  : "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"
  sql_quote() {   # a single-quoted SQL string literal (default sql_mode)
    local s=${1//\\/\\\\}
    printf "'%s'" "${s//\'/\'\'}"
  }
  init_file=$(mktemp /tmp/credentials.XXXXXX.sql)
  {
    echo "SET SESSION sql_log_bin = 0;"
    echo "ALTER USER IF EXISTS 'root'@'localhost' IDENTIFIED BY $(sql_quote "$MYSQL_ROOT_PASSWORD");"
    echo "DROP USER IF EXISTS 'root'@'%';"
    if [ -n "${MYSQL_USER:-}" ] && [ -n "${MYSQL_PASSWORD:-}" ]; then
      echo "ALTER USER IF EXISTS $(sql_quote "$MYSQL_USER")@'%' IDENTIFIED BY $(sql_quote "$MYSQL_PASSWORD");"
    fi
    echo "FLUSH PRIVILEGES;"
  } > "$init_file"
  chown mysql:mysql "$init_file"
  chmod 0600 "$init_file"
  set -- "$@" "--init-file=$init_file"
fi

exec docker-entrypoint.sh "$@"
