# Protect critical directory roots

Purpose: stop recursive deletion of the filesystem root, the user's home root,
or the active project root while preserving authorized narrower cleanup.

`{{HOOK_BINDING}}`: prefer a native filesystem restriction where it expresses
the boundary faithfully. If a hook is needed, resolve the command's actual
working directory, normalized operands, option terminators, and symlink targets
before deciding. Do not run the destructive command to discover its targets.

Do not generalize this guard into blocking every absolute path or every
out-of-project action. Explain the exact protected target without revealing
unrelated filesystem content. If the native event cannot establish the target,
report that ambiguity rather than claiming full protection.

Check with a fake command runner and temporary fixtures: protected roots are
denied; a specifically authorized child directory can be removed; aliases and
relative operands resolve correctly; malformed payloads do not bypass the
guard. Never execute a destructive-root probe against the real filesystem.
