# Correct a concrete shell invocation mistake

Purpose: prevent a known ambiguous tool option from silently producing the
wrong evidence, without policing every shell command.

`{{HOOK_BINDING}}`: where documented payloads expose a shell invocation, detect
an actual `rg -r` use that appears to mean recursive search even though `-r`
selects replacement. Consult the installed ripgrep help before implementing the
diagnostic. Preserve explicit replacement uses and values belonging to other
options. Explain the correction once; use advisory feedback when intent is
uncertain, not a universal command denial.

Check a mistaken recursive-search use, explicit replacement, a quoted string
containing similar text, and repeated attempts. Match the executable and parsed
arguments rather than every occurrence of the characters in a shell string.
