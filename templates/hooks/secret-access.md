# Protect credential access

Purpose: keep protected credential values out of model context while allowing
the authorized consumer to authenticate.

`{{HOOK_BINDING}}`: inspect relevant file-read, search, and shell operations
before execution using the documented native payload. Resolve protected store
locations and the allowed non-secret catalog from the installed credential
mechanism, without reading store contents. Recognize path aliases and symlinks
when the runtime exposes enough information.

Reject direct reads, searches, dumps, copies, or standalone value printing from
the protected store. Allow reading the catalog and registered process-scoped
credential delivery. Do not block every authenticated command or echo the
rejected secret-bearing tool input. Provide one short reason and an allowed
route. A lexical shell check is not a complete sandbox: prefer a native access
boundary when available and state any enforcement gap.

Check in isolation: a synthetic protected-file read is denied; a catalog read
works; a fake registered value reaches only a test consumer and is absent from
tool output; path aliases and malformed payloads follow the declared boundary.
Use synthetic credentials only. Never probe with the operator's real store.
