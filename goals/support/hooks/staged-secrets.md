# Check the exact staged content

Source: [_secret_commit.py](../../../templates/hooks/scripts/_secret_commit.py).

Preserve exact-index inspection, command parsing, redacted findings and failure behavior. Adapt the shell payload and permission output, not the staged-content guarantee.

Known source limitation: conservative shell parsing can refuse compound/heredoc
requests, including diagnostic prose mentioning a commit. Test actual commands
and harmless quoted examples before adopting the binding; a parser refusal is
not evidence that the staged content contains a secret.

Purpose: prevent a commit from including likely credential values introduced
by the staged change, without scanning protected stores or unrelated history.

`{{HOOK_BINDING}}`: use a documented pre-commit action boundary or an equivalent
native guard. Examine the exact staged blob and relevant staged changes, not
only the working file. Handle partial staging, renamed files, binary files,
deleted paths, unusual filenames, and an alternate repository directory.

Use an available maintained scanner when it can preserve this boundary.
Report path, location, and finding class without printing the value. Do not
stage files, edit the index, or commit as a side effect of the check. A scanner
failure is not a successful scan; disclose the missing protection with a
bounded diagnostic and follow the documented blocking contract.

Check in isolation: a synthetic staged credential blocks; a clean staged file
passes; a dirty unstaged copy does not change the staged verdict; a failed
scanner is distinguishable from a clean result; repeated attempts do not leak
values or create unbounded duplicate feedback.
