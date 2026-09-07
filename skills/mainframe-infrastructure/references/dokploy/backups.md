# Dokploy backups, restore, and rollback

Distinguish four different mechanisms:

- managed-database backup;
- Docker volume backup;
- full Dokploy platform backup;
- deployment rollback.

They protect different state and cannot substitute for one another. Resolve the
exact source, destination, schedule, retention, encryption, resource ownership,
and target-version semantics.

Before relying on a backup, verify that it completed, exists at the intended
destination, contains the expected scope, and has a documented restore path.
Where risk and authority permit, prove restoration in an isolated target. A
successful schedule or upload does not prove restorability.

Treat destination credentials through `mainframe-secrets`; never show storage
keys or authenticated URLs. Retrieve the current API schema before creating or
changing a destination, backup, schedule, or retention rule.

Restore can replace current filesystem, database, deployment, or configuration
state and may invalidate sessions or routing. Establish downtime, backups of
the current state, target identity, and a recovery path before execution.
Deleting a schedule may differ from deleting stored backup objects; verify the
exact version's behavior.

Deployment rollback does not restore database or volume contents.
