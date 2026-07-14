# Backups & data protection

Three distinct mechanisms — do not confuse them:

| Need | Endpoints |
|---|---|
| Database dumps (scheduled or manual) | `backup.*` |
| Docker volume snapshots | `volumeBackups.*` |
| Revert a deployment (not data) | `rollback.*` |

Database/volume backups are written to a **destination** (remote storage, S3-compatible), so configure that first.

```bash
H=(-H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json")
```

## 1. Destination (one-time)

```bash
curl -sS --fail-with-body "${H[@]}" -d '{
  "name":"s3","provider":"s3","bucket":"backups","endpoint":"<url>","region":"auto",
  "accessKey":"<id>","secretAccessKey":"<secret>","additionalFlags":[]}' \
  "$DOKPLOY_URL/api/destination.create"
```

Never inline the secret access key in a command shown to the user — substitute from env (see [`secrets-handling`](../secrets-handling/SKILL.md)).

## 2. Database backups

- **Scheduled:** `backup.create` — required `database`, `databaseType` (`postgres`/`mysql`/`mariadb`/`mongo`/`libsql`/`web-server`), `destinationId`, `schedule` (cron), `prefix`; manage with `backup.update`, `backup.one`, `backup.remove`.
- **Run now:** `backup.manualBackupPostgres` (and `...MySql` / `...Mongo` / `...Mariadb` / `...Libsql` / `...Compose` / `...WebServer`).
- **List stored files:** `backup.listBackupFiles`.

```bash
curl -sS --fail-with-body "${H[@]}" -d '{"backupId":"<id>"}' \
  "$DOKPLOY_URL/api/backup.manualBackupPostgres"
```

## 3. Volume backups

`volumeBackups.create` (schedule), `volumeBackups.runManually`, `volumeBackups.list`, `volumeBackups.one`, `volumeBackups.update`, `volumeBackups.delete`. Use for stateful data held in Docker volumes rather than a managed DB.

## 4. Rollback (deployments, not data)

`rollback.*` reverts an application/compose to a previous deployment — it does **not** restore database contents. For data recovery, restore from a `backup.*` dump.

## Discipline

- **Back up before destructive DB ops.** `postgres.remove` etc. destroy the volume with no undo ([safety.md](safety.md)).
- `backup.remove` / `volumeBackups.delete` delete backup *configs/files* — verify you are not deleting the only copy.
- `schedule.*` manages generic scheduled jobs (e.g. cron tasks); list before editing.
