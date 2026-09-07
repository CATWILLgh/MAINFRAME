# Infrastructure verification

Select the smallest observation that proves the changed infrastructure
contract. Do not start infrastructure, install validators, deploy, contact
production, update snapshots, or widen scope solely to satisfy a ritual.

Use the applicable layers:

- parse or validate edited configuration with the provider's native tool;
- render configuration, plan, diff, or dry-run before mutation when faithful;
- build an image or artifact when buildability is the changed guarantee;
- observe the exact live resource after an authorized apply;
- inspect health, logs, metrics, routing, certificates, storage, or database
  state according to the guarantee;
- exercise the user-facing route when networking, identity, or managed-service
  integration is part of the change;
- verify rollback or recovery when the change depends on it and the authorized
  environment permits a safe test.

Treat syntax, command exit status, API acceptance, asynchronous completion,
resource health, and user-facing behavior as distinct evidence. One does not
substitute for the others.

CI/CD parsing does not prove runner permissions, secrets, protected-branch
behavior, artifact publication, or deployment. A health endpoint does not by
itself prove the product workflow. A deployment rollback does not restore
deleted data.

If required evidence is unavailable within scope, report the exact unverified
guarantee. After verified topology changes, update only checked map facts and
validate every newly referenced runbook path. Preserve `lastVerified` when the
environment entry was only partially checked.
