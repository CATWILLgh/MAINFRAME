# Audit MAINFRAME traces in the current environment

Inspect the current agent environment for obsolete MAINFRAME files and
registrations. Keep configuration, installed files, and runtime state unchanged.

Establish [the current environment](support/environment.md), then follow
[the audit procedure](support/legacy-audit.md). Use the product's current official
loading documentation and inspect the applicable global, project, and package
locations. Include shared Desktop/CLI configuration where its contract applies.

Return a concise coverage table and findings with their paths, ownership
evidence, consumers, and proposed actions. Distinguish current MAINFRAME material,
obsolete owned objects, and uncertain ownership. Every conclusion must stay
within the evidence actually obtained.

If a source or location is unavailable, finish independent inspection and report
the precise gap as a partial audit. No proven cleanup candidates is a valid
result. Save the report in a native artifact if useful; cleanup requires a
separately agreed scope.
