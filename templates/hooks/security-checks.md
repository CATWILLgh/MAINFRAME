# Check security-sensitive changes

Source: [Python scan](scripts/python-security-scan.py), [Python completion check](scripts/python-security-stop-gate.py), [Node scan](scripts/nodejs-security-scan.py), [Node completion check](scripts/nodejs-security-stop-gate.py), [Semgrep advice](scripts/semgrep-informational.py).

Keep the [rules](rules/semgrep-informational.yml) and [fixtures](rules/semgrep-informational.js) for Semgrep. Adapt executable discovery, event deltas and failure reporting; do not install scanners as a side effect of an edit.

Purpose: surface high-confidence security regressions in edited Python and
JavaScript/TypeScript code, using the project's established tools when useful.

`{{HOOK_BINDING}}`: run the relevant bounded changed-file check after an edit
or before completion when the runtime supports that lifecycle. Inspect scanner
configuration before execution; avoid triggering repository-wide builds or
network installation on every edit. Prefer existing maintained tools to a new
home-grown scanner. Optional tools being absent must be visible as a check
limit, not a clean scan or an endless blocker.

Attribute findings to current changes and distinguish confirmed issues from
heuristic advice. Keep uncertain or broad Semgrep-style advice non-blocking.
Use a completion gate only for a concrete unresolved current violation with
the necessary source evidence. Report locations and remediation direction
without secrets or raw sensitive source snippets.

Check in isolation: a small synthetic risky change is detected; a safe change
passes; unrelated old findings remain quiet; a missing or failing scanner has
bounded feedback; a resolved finding clears; asynchronous results cannot be
misattributed to a newer file revision or another task.
