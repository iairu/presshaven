# Backups

`backup_service` takes nightly dumps into `ids/backups/{db,wp}/*.gz`. They can be
labeled, deleted, exported to a local file and re-imported — from the dashboard's
Backups page **or** the command line.

## Lifecycle from the CLI

```bash
./backups/manage_backups.sh list
./backups/manage_backups.sh label <file> "<label>"
./backups/manage_backups.sh delete <file>
./backups/manage_backups.sh export <file> <dest>
./backups/manage_backups.sh import <src>
```

`manage_backups.sh` reads and writes the **same** `labels.json` manifest inside
`backup_service` (via `docker compose exec`) that the dashboard does, so a label set
in one shows up in the other immediately. See the script's header for exact usage.

## Git-LFS plumbing

`ids/backups/.gitattributes` routes `db/*.sql.gz` / `wp/*.tar.gz` through git-lfs, but
the root `.gitignore`'s blanket `*.sql.gz` / `*.tar.gz` rules were silently shadowing
it — every real backup file was ignored regardless. Fixed with narrow negation
exceptions (`!ids/backups/db/*.sql.gz`, `!ids/backups/wp/*.tar.gz`).

!!! note "This does not auto-commit backups"
    Nothing changed about what `git add` includes by default. It means a backup you've
    **deliberately chosen to keep** (labeled, then `git add`ed) actually can be,
    instead of being invisibly dropped.

## The five bugs that made backups silently non-functional

`backup_service` had run for hours logging normal operation while producing **zero**
real backups. Five independent bugs, each masking the next — all fixed and verified:

1. `chmod +x /backup.sh` failed every run (`Read-only file system` — the script is
   bind-mounted `:ro`) and was dead code anyway. Removed.
2. `mkdir` of the backup dirs failed `Permission denied`: `./backups/` is a host bind
   mount and `backup_service` runs with `cap_drop: ALL`, which strips
   `CAP_DAC_OVERRIDE`. Fixed with a scoped `cap_add: [DAC_OVERRIDE]` (the one
   capability actually needed).
3. `mktemp /tmp/mysql-backup-XXXXXX.cnf` failed `Invalid argument`: BusyBox `mktemp`
   requires the template to end in `XXXXXX`. Fixed by dropping the `.cnf` suffix.
4. `mysqldump | gzip > file` silently "succeeded" even when `mysqldump` failed — the
   `if cmd1 | cmd2` check reflects only gzip's exit status without `set -o pipefail`,
   and gzip happily compresses zero bytes. Fixed with `set -o pipefail`.
5. That masked the real failure: `mysqldump` was failing on **every** run with a
   TLS/SSL `Certificate verification failure` (MySQL 8+ enables TLS by default with an
   untrusted self-signed cert) — so every "successful" backup was an empty 4 KB
   `.sql.gz`. Fixed with `--skip-ssl` (a private container-to-container connection,
   not internet-exposed) plus `--no-tablespaces` to silence a benign `PROCESS`
   privilege warning.

Verified end-to-end: `docker compose exec backup_service /backup.sh` now produces a
genuine 231.6 MB WordPress file archive and a 564–576 KB database dump (126
`CREATE TABLE` statements, confirmed by decompressing and grepping).

## Charset note

When restoring, dumps are pinned to `--default-character-set=binary` on both ends of
every `mysqldump | mysql` pipe. Without it, PHP-serialized postmeta like
`_product_attributes` gets double-encoded by charset-naive pipes, breaking
`unserialize()` and the product-options selector on the shop. See
[Troubleshooting](../operations/runbooks.md).
