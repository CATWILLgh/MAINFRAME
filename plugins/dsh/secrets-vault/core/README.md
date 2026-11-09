# Encrypted Node storage core

`index.js` exports the internal `VaultStore` (constructor `{ databasePath }`).
It uses only Node built-ins and owns no subprocesses, intervals or idle timers.
Do not expose `internalGet` over agent tools, RPC, or client services. Recovery
and legacy migration are intentionally outside this core.

## Format and limits

The `MAINFRAME-VAULT-2\n` prefix precedes a strictly validated JSON envelope.
AES-256-GCM encrypts the complete versioned record payload, including metadata.
Its authenticated header is the canonical JSON representation of `version`,
random vault `id`, fixed `kdf`, and random `salt`. Nonces are fresh 96-bit random
values for every write; salts are fresh 128-bit random values on setup/rekey.
Scrypt is asynchronous with N=32768, r=8, p=1, maxmem=64 MiB, producing 256 bits.
A successful rekey atomically replaces the entire envelope. Unknown/nonmatching
magic (including opaque SQLCipher ciphertext) yields `LEGACY_VAULT_FORMAT` and
is never rewritten by setup/unlock.

Encrypted files are bounded to 32 MiB before reading/decoding. The payload has
at most 4096 records; secret JSON is at most 1 MiB and metadata JSON at most
32 KiB (UTF-8 bytes, intentionally conservative for non-ASCII). Snapshotting
rejects executable/accessor properties, non-JSON values, class instances,
cycles, sparse arrays, nesting over 32 levels and individual values over
100000 nodes. Passwords match existing 1–4096-character unlock / at-least-12
setup and rekey rules, with NUL forbidden. JS lengths count UTF-16 code units.

List returns `{ id, metadata, created, updated, revision }`, newest first.
Mutations return the existing `{ id }` / `{ deleted: true }` shapes. Revisions
begin at 1 and increase for save/update. Optional `expectedRevision` implements
optimistic concurrency (`VAULT_CONFLICT`); callers should require it for edits
based on previously displayed records. New saves cannot specify a revision.
Inputs are captured synchronously before entering the serial async queue and
returned values are detached copies. Explicit undefined optional save `id` and
`expectedRevision` are treated as omitted; secret JSON cannot contain undefined.

## Ownership, atomicity, and failure behavior

The first operation takes a lifetime owner even while locked: a process-local
canonical-path registry plus `${databasePath}.node-owner`, a private directory
atomically published already populated with an immutable PID/256-bit-token
filename. Only a validated owner whose PID probe returns ESRCH is reclaimed;
live processes, reused PIDs, permission-denied probes and malformed metadata
fail closed (`VAULT_BUSY`). Token-specific unlink prevents a delayed reclaimer
from deleting a successor. Directory identity, permissions and token are
verified before commits and release. Empty modern gates can be replaced safely.

A populated `${databasePath}.node-lock/owner.json` is retained for compatibility
with 2.0.x owners. Modern ownership serializes recovery of dead legacy owners.
An empty legacy directory is replaced atomically on POSIX: a paused old owner
then fails its exclusive owner-file write. Malformed legacy metadata is not
removed. Legacy release renames the directory out of its public name before
metadata cleanup; failed garbage cleanup does not strand ownership. Failed
release I/O can be retried with dispose(), but new operations remain rejected.
If initialization and its cleanup both fail, verified ownership is retained so
explicit disposal can retry safely rather than abandon a live PID marker.
Interrupted preparation/retirement may leave harmless token-named metadata
directories; they contain no credential data and are not swept automatically.
Historical `${databasePath}.lock` files are untouched. Never manually delete a
public marker while any Host could be running.

The storage directory must already be private or be created private; the core
never silently fixes unsafe permissions. Symlink final directory/file, hard
linked files, non-owner files and POSIX group/other permissions are rejected.
Ancestor symlinks are resolved to a canonical parent (needed for e.g. macOS
`/var` aliases). The canonical parent inode must not change during ownership.
The encrypted file's last authenticated/committed SHA-256 fingerprint is
checked before overwrites to avoid silently replacing externally modified data.

Writes create a random exclusive 0600 temp in that directory, fsync and close
it, revalidate ownership/target, rename, then fsync the directory. Pre-rename
failures retain old records/key; a rename attempt or postrename durability
failure wipes the key and blocks further work until dispose/reopen. Setup will
not overwrite any existing target. Dispose immediately rejects new operations,
drains already admitted work, wipes Buffer keys, then releases only its verified
owner. Locks remain held after crypto lock() until disposal.

## Security boundaries and portability

This prevents accidental multi-owner access; it is not a sandbox against code
already running as the same OS user, a malicious root, filesystem rollback or
an uncooperative legacy writer. Node has no portable dirfd-relative rename or
secure-memory primitive: checked path operations retain a same-user TOCTOU
window. Use a trusted local filesystem and private, stable ancestor directories.
JavaScript strings/object secrets and password strings cannot be reliably
zeroized; Buffer key/plaintext wiping is best effort, not a memory-forensics
guarantee. Whole-vault encryption reveals approximate total payload size and
rewrites the full file per mutation; it does not prevent rollback to an old
valid envelope. Keep backups according to the integrating application's policy.

On Windows, POSIX modes/uid and no-follow flags do not establish ACL safety;
the integrator must provision a private user ACL. Directory fsync is skipped
there because opening/fsyncing directories is not portable, so power-loss
rename durability is weaker. Windows and network-filesystem semantics have
not been acceptance-tested. The atomic durability guarantee described above
is verified on local POSIX filesystems only.

## Tests

Run `node --test plugins/dsh/secrets-vault/core/*.test.mjs` from the repository
root. Every fixture uses temporary synthetic data. The optional *internal*
second constructor argument `{ filesystem }` supports deterministic I/O faults;
it is a trusted implementation/test seam, never user-supplied configuration.
