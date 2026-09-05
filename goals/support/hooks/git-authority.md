# Preserve Git authority

Source: [_git_authority.py](../../../templates/hooks/scripts/_git_authority.py).

`authority_decision(command)` returns a classification, not proof of caller authorization. Bind `ask` to the target's actual authority context; there is no special subagent staging/commit ban.

Purpose: permit normal local work while respecting the caller's authority for
publication, history changes, and destructive Git operations.

`{{HOOK_BINDING}}`: use native permissions or a pre-action hook where documented.
Keep read-only Git inspection available. Local staging and commits follow the
assigned task's authority regardless of whether the executor is the main agent
or a subagent. Push, force push, branch or worktree changes, history rewriting,
stash removal, and destructive cleanup need the relevant authority; ordinary
push authority does not imply force push authority.

Do not encode a universal ban or infer authorization from a command string.
When native approval context is unavailable, preserve the instruction boundary
and report the enforcement limit. Recognize the actual executable, working
directory, options, and compound command boundary to the extent supported;
do not advertise regex matching as a complete shell parser.

Check in isolation: read-only inspection passes; authorized ordinary work is
not blocked; an unapproved destructive or remote action cannot silently run;
the runtime's denial remains a denial; malformed input does not grant access.
Use a temporary repository and no real remote mutation.
