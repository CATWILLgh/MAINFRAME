# Backups & data protection

Three distinct mechanisms — do not confuse them:

| Need | Endpoints |
|---|---|
| Database dumps (scheduled or manual) | `backup.*` |
| Docker volume snapshots | `volumeBackups.*` |
| Revert a deployment (not data) | `rollback.*` |

Database/volume backups are written to a **destination** (remote storage, S3-compatible), so configure that first.

Verify the destination and backup endpoint schemas against the target instance;
storage providers and required fields vary by version.

## 1. Destination (one-time)

```bash
secret get REGISTERED_STORAGE_SECRET | jq -Rs --arg accessKey "<id>" '{
  name:"s3", provider:"s3", bucket:"backups", endpoint:"<url>", region:"auto",
  accessKey:$accessKey, secretAccessKey:rtrimstr("\n"), additionalFlags:[]
}' | curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 \
  -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" \
  --data-binary @- "$DOKPLOY_URL/api/destination.create"
```

Never inline the secret access key in a command shown to the user. Use the
registered helper-to-stdin flow defined by
[`secrets-handling`](../../../mainframe-secrets/SKILL.md).

## 2. Database backups

- **Scheduled:** `backup.create` — required `database`, `databaseType` (`postgres`/`mysql`/`mariadb`/`mongo`/`libsql`/`web-server`), `destinationId`, `schedule` (cron), `prefix`; manage with `backup.update`, `backup.one`, `backup.remove`.
- **Run now:** the current official reference exposes
  `backup.manualBackupPostgres` and variants for MySQL, MongoDB, MariaDB,
  Compose, and web-server backups. Inspect the target instance before assuming
  another engine-specific action exists.
- **List stored files:** `backup.listBackupFiles`.

```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 \
  -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" \
  -d '{"backupId":"<id>"}' \
  "$DOKPLOY_URL/api/backup.manualBackupPostgres"
```

## 3. Volume backups

`volumeBackups.create` (schedule), `volumeBackups.runManually`, `volumeBackups.list`, `volumeBackups.one`, `volumeBackups.update`, `volumeBackups.delete`. Use for stateful data held in Docker volumes rather than a managed DB.

## 4. Rollback (deployments, not data)

`rollback.*` reverts an application/compose to a previous deployment — it does **not** restore database contents. For data recovery, restore from a `backup.*` dump.

## Discipline

- **Back up before destructive DB ops.** Verify that the backup can actually be
  restored before removing managed data ([safety.md](safety.md)).
- Before `backup.remove` or `volumeBackups.delete`, inspect the current endpoint
  semantics and stored copies; never assume a name reveals whether it removes a
  schedule, metadata, stored data, or more than one of those.
- `schedule.*` manages generic scheduled jobs (e.g. cron tasks); list before editing.
