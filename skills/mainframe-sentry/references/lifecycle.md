# Self-hosted lifecycle

Verified against official sources on **2026-10-29**. Requirements, hard stops,
storage layout, and helper behavior change with releases. Re-read the linked
pages and the source for the selected release before proposing commands for a
real instance; this reference does not identify an installed version.

## Install and size

The maintained baseline is the `getsentry/self-hosted` Docker Compose stack with
its Bash installer, intended for simple use cases. It has no guarantees or
dedicated support; custom larger installations remain the operator's work.
Select an explicit release tag, inspect its configuration and prerequisites,
then use that tag's installer. The documented startup is `docker compose up
--wait`; installation completion alone does not prove ingest or the public URL
works. [Self-hosted overview](https://develop.sentry.dev/self-hosted/)

The overview currently requires Docker 19.03.6+, Compose 2.32.2+, four CPU cores,
16 GB RAM plus 16 GB swap, and 20 GB free disk, and recommends 32 GB RAM.
These are installation minima, not event-rate or retention capacity promises.
Disk I/O matters because databases and brokers share the machine. Size using the
actual event mix, retention, free-space trend, and I/O behavior; do not extrapolate
an HA design or throughput guarantee from the minimum. Debian/Ubuntu are the
preferred documented distributions; Alpine is unsupported and disabling SELinux
to make another distribution work is discouraged.
[Requirements and production boundary](https://develop.sentry.dev/self-hosted/)

The support page describes the baseline as geared toward less than roughly one
million submitted events per month; this is a support/use-case boundary, not a
measured capacity guarantee. Only Docker Compose is maintained by this project.
The community Helm chart is unaffiliated and outside its support scope.
[Support boundary](https://develop.sentry.dev/self-hosted/support/)

For the verified `26.10.0` tag, the installer additionally requires Bash 4.4+.
Its default-profile hard check is 14,000 MB available to the container engine
(allowing host overhead within a 16 GB machine), not a replacement for the
documented host RAM and swap recommendation. Errors-only has different checks;
do not silently select that profile to make a full-featured installation fit.
[Tagged requirements](https://github.com/getsentry/self-hosted/blob/26.10.0/install/_min-requirements.sh)

## Upgrade

Obtain current release, target release, local changes, configuration overrides,
and recoverable state before building a path. Sentry uses monthly CalVer releases
and does not patch old versions; point releases are snapshots of current
components. Read every required intermediate release's notes and compare the
target's example configuration with the retained local configuration. The
installer performs migrations and normally shuts down services: budget downtime.
The `--minimize-downtime` option is experimental, not a zero-downtime guarantee.
[Releases and upgrading](https://develop.sentry.dev/self-hosted/releases/)

Build an explicit sequence through every hard stop between current and target.
At retrieval, the documented stops were `9.1.2`, `21.5.0`, `21.6.3`, `23.6.2`,
`23.11.0`, `24.8.0`, `25.5.1`, `26.5.0`, and `26.7.0`. This list is a dated
research snapshot, not a permanent upgrade matrix. The same page lists versions
to avoid and additional version-specific problems; consult it live rather than
assuming the newest numeric tag is safe. It also contains a legacy Compose
project-name cleanup instruction for crossing `21.12.0`; inspect that instruction
and the instance's actual project before any removal command.
[Hard stops and known issues](https://develop.sentry.dev/self-hosted/releases/)

Run the selected release's `./install.sh`, then its documented Compose startup.
Preserve `.env.custom` loading when used: the current guide specifies both `.env`
and `.env.custom` for startup. Verify the selected images, migration result,
service readiness and the user's relevant ingest/query workflow. Keep rollback
distinct from checking out older code: migrations may require restoring compatible
data. Nightly builds carry no guarantee of later clean upgrades without data loss.
[Upgrade procedure and nightly boundary](https://develop.sentry.dev/self-hosted/releases/)

Example of why release notes remain necessary after the hard-stop check: the
latest release found during this research was `26.10.0`, published 2026-10-16.
It upgrades PostgreSQL 14 to 18, changes the PostgreSQL data layout and warns to
take a server snapshot before upgrading. Its installer replaces the old database
volume after migration; a code checkout cannot undo that. The same release notes
call out a `SENTRY_BUCKET_PROFILES` change for external Vroom storage. Apply these
checks when crossing this release, without assuming `26.10.0` remains latest.
[26.10.0 release](https://github.com/getsentry/self-hosted/releases/tag/26.10.0),
[tagged PostgreSQL migration](https://github.com/getsentry/self-hosted/blob/26.10.0/install/upgrade-postgres.sh)

## Backup and recovery

First name the recovery objective. The official export/import flow is a **partial
backup** of supported low-volume data. It excludes events, issues and anything
referencing external files. Its helper/CLI differs by release: the docs introduce
`scripts/backup.sh` and `scripts/restore.sh` at 23.3.1, scoped helper arguments at
24.1.0, and the more granular `sentry-admin.sh` import/export flow at 23.11.1.
Inspect the selected release's implementation before forming the command.
[Backup and restore](https://develop.sentry.dev/self-hosted/backup/)

There is a concrete documentation/source conflict at `26.10.0`: the wrappers
consume every argument in a loop, then construct the backup/restore command from
the emptied `$1`; the shared functions default to `global`. Static inspection
therefore does not support relying on the documented scope argument. For scoped
work, inspect explicit `sentry-admin.sh export`/`import` commands and verify the
resulting scope on an authorized isolated target before use. This was a source
finding, not a live execution of the wrapper.
[Backup wrapper](https://github.com/getsentry/self-hosted/blob/26.10.0/scripts/backup.sh),
[restore wrapper](https://github.com/getsentry/self-hosted/blob/26.10.0/scripts/restore.sh),
[shared functions](https://github.com/getsentry/self-hosted/blob/26.10.0/scripts/_lib.sh)

`sentry-admin.sh` paths are container paths. At `26.10.0`, host file I/O is mounted
at `/sentry-admin` from `SENTRY_DOCKER_IO_DIR` (default `~/.sentry/sentry-admin`).
Even `--help` invokes a function that starts PostgreSQL, PgBouncer and Redis;
source inspection is the read-only way to discover this wrapper. Do not run it
against a live deployment under read-only diagnostic authority.
[Tagged admin wrapper](https://github.com/getsentry/self-hosted/blob/26.10.0/sentry-admin.sh)

Treat exports as sensitive: user scope includes login credentials, and config
scope includes administrative credentials. The admin CLI supports encrypted
exports. Verify the artifact and restore procedure without exposing its contents.
The docs warn that partial restore deletes existing data in affected tables and
strongly recommend restoring on a fresh, migrated empty database at the same
Sentry version. Confirm the target and replace/delete effects before restore.
[Export scopes, encryption and restore warning](https://develop.sentry.dev/self-hosted/backup/)

The docs describe volume backup as an **unsupported** full-backup approach. They
name persistent `sentry-` volumes and separately mention Compose-created volumes
for in-flight data. Inventory the selected deployment's actual volumes, external
stores, local configuration and secret dependencies; do not turn the prose list
into an exhaustive current storage inventory. Plan consistent capture and prove
recovery in an isolated compatible target before calling a backup recoverable.
Documentation of a method does not prove this instance's recovery point or time.
[Full-backup coverage and limits](https://develop.sentry.dev/self-hosted/backup/)

The prose inventory already differs from tagged source: the backup page omits
`sentry-seaweedfs`, while `26.10.0` Compose declares it an external persistent
volume. Compose also describes profile persistence and in-flight taskbroker data
in project volumes. Include actual configured object stores and mounts in the
recovery design; do not assume backing up only PostgreSQL or only the listed
global volumes preserves attachments, profiles and queued work.
[Tagged volume declarations](https://github.com/getsentry/self-hosted/blob/26.10.0/docker-compose.yml)
