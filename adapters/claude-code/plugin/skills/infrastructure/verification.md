# Infrastructure verification

Select the cheapest observation that proves the changed infrastructure
contract. Do not require a local container stack when static validation or an
already available environment is faithful to the risk.

Use the applicable layers:

- parse or validate edited configuration with the provider's native tool;
- build an image or artifact when buildability is the changed guarantee;
- use plan, diff, dry-run, or config rendering before a remote mutation when
  the platform supports it;
- observe the exact remote resource after an authorized apply;
- check health, logs, metrics, routing, TLS, or database state according to the
  guarantee, not merely the command exit code;
- exercise rollback before relying on it when the cost and environment allow;
- run a deployed product check when deployment behaviour, networking, identity,
  or managed-service integration cannot be established locally.

For CI/CD changes, validate syntax and changed expressions locally when the
provider offers a faithful tool. A successful YAML parse does not prove secret
availability, runner permissions, protected-branch behaviour, or the deployed
effect; keep those as separate external checks.

Do not install a new validator, start infrastructure, update snapshots, deploy,
or contact production solely to satisfy a ritual. If required evidence is not
available within the authorized scope, report the exact unverified guarantee.

After a successful topology change, re-read the affected resource. When
repository edits are within the active task, update its entry in
`.agents/infrastructure.json` and verify every newly added runbook path exists;
otherwise return the exact required map update without editing it. Do not
update unrelated environments' `lastVerified` dates.
