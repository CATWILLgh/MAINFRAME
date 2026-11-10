# Secrets Vault

Profile-wide encrypted credential vault for DeepSeek Harness. Open **Secrets Vault** in the sidebar or the chat input's **+** menu. Create a unique master passphrase (at least 12 characters) and save the random 256-bit recovery key shown once in the private dialog separately, outside Harness. Losing both makes recovery impossible.

## Node.js core and storage

Version 2 uses only Node.js built-ins: asynchronous scrypt (N=32768, r=8, p=1, 64 MiB maximum memory) and AES-256-GCM with random salts/nonces and authenticated format headers. No Python, SQLCipher, native addon, installation script or bundled interpreter. Import the independent storage API through the `./core` package export; it has no DSH dependencies. The adapter owns profile resolution, recovery and private UI authorization.

The selected profile holds `secrets-vault/vault.v2.json` and `vault.v2.json.recovery.json`. Metadata and secrets are encrypted; directory permissions are 0700 and files 0600 on POSIX. Root selection is explicit `profileDirectory`, then `DSH_PROFILE_DIR`, then an outer native `node_modules/@mainframe/secrets-vault` alias resolving to this package (not pnpm's inner self-reference). Otherwise activation fails closed. Obsolete `python` overrides must be removed, not silently ignored.

The core serializes reads, writes, locking and rekeying. The Host also serializes entire recovery/UI/tool transactions for all sessions. Records carry revisions: stale UI edits, secret replacements and deletes fail rather than overwrite another session. Agents change allowed metadata against the current serialized revision. Each write creates a private exclusive random temporary file, syncs it, atomically renames it, then syncs the directory. Precommit failures retain old state; uncertain commits block further access until restart. This is a bounded whole-file store (32 MiB encrypted file, 4096 records), not an unbounded database. Physical power-loss testing has not been performed.

One Host owns the store for its lifetime, including when locked. A canonical-path in-process registry and atomically populated `.node-owner` directory reject a second owner; `.node-lock` also excludes older 2.0.x owners. After a crash, valid markers are recovered automatically **only when the recorded PID is confirmed absent**. Live/reused PIDs, ambiguous metadata and denied process probes remain blocked rather than risking concurrent writers. Empty legacy gates can be safely replaced atomically on POSIX. Never remove a marker while a Host might be running. Graceful disposal rejects new requests, drains admitted operations, wipes key buffers best effort and releases ownership, with no worker process to wait for. Interrupted preparation/cleanup may leave harmless token-named metadata directories; these are not credential data or backups.

The core is portable Node.js code, but POSIX permissions and directory fsync are currently tested on macOS. Windows filesystem durability/ACL behavior is not certified. Agent SSH operations still require local OpenSSH/Unix sockets; clipboard import still uses macOS `pbpaste`. Portable storage does not imply cross-platform support for every adapter operation.

## Upgrade to 2.0.7

Tool discovery now supports metadata-only `query`, `offset` and `limit` (1–100, default 100), returning `total` and `nextOffset` (`null` at the end). The catalog is bounded to 4096 records. Pages sort by updated descending, then id ascending; offsets describe the current catalog, not a snapshot. Changes may shift pages: restart at zero after a mutation. Per-record actions no longer clone the full catalog. One closed-schema tool retains eight actions; malformed or action-inapplicable fields now return static diagnostics instead of being silently ignored.

Queued cancellations are checked at admission and dequeue; clipboard import checks again before reading and saving. An initiated durable save is always awaited. Preparation attribution comes only from the trusted executing agent. Disposed/stale UI generations cannot retain a late recovery key. Owned teardown retries one transient EIO/EINTR/EBUSY release failure inside the original disposer; persistent failures propagate without deleting another owner's markers.

The DSH compatibility constraint is exactly `0.2.2-rc.1`, grounded in inspected runtime contracts and source/VM tests; neither older nor future runtime compatibility is claimed. This is not installed-profile or GUI acceptance.

### Historical 2.0.6 lifecycle repair

Host teardown became owned by an early Cordis effect: it closes admission synchronously, drains admitted transactions, then invokes owned store disposal (now with the bounded transient retry above). Ordinary `ctx.on('dispose')` listeners in previous versions were not lifecycle cleanup. After installing this repair, restart a Host that loaded an affected version: old leaked owners cannot safely be recovered by hot-reloading or publicly disposing another plugin's handle. Preserve all vault files and ownership markers; do not bypass ownership checks. Storage format and cryptography are unchanged.

## Lifetime and threat model

Unlock lasts until **Lock** or Host exit. Screen/browser lock, disconnect, closing a dialog and switching sessions do not lock it; there is no inactivity timer. Passwords go directly from the authenticated browser to the Host, never into configuration, chat, argv, environment or logs. Buffer keys are cleared best effort; managed strings and runtime copies cannot be reliably zeroized. The vault protects locked files, not malicious code with same-user filesystem/process access. No real credentials are used in tests.

React UI uses native slots, semantic `--dsw-alias-*` tokens, localized plugin metadata (English/Russian), an original SVG icon, focus-contained dialogs and native management-page layout contracts. UI copy follows the native DSH language live: Russian for `ru`, English for every other language. `locale/en.json` and `locale/ru.json` own the complete flat `ui` dictionaries and plugin metadata; run `node build-client.mjs` after editing them or `client.template.js` to regenerate the self-contained runtime `client.js`. The build-only shared locale helper embeds dictionaries and registers them through the native locale API, including English for other external languages regardless of their fallback chain. Stored UI errors retain translation keys so open dialogs and errors update without resending secrets. Tool descriptions/results and user-entered metadata are not translated. Source contracts do not establish pixel-level browser correctness.

## Upgrade from version 1

**SQLCipher files cannot be decrypted by this pure Node.js implementation. No automatic migrator is shipped.** Before upgrading an initialized v1 vault, retain the old plugin/runtime and backups. Any `vault.db` **or** `vault.db.recovery.json` beside the new format causes explicit refusal, including orphaned envelopes. They are never read, overwritten or deleted by v2. Use the previous plugin to access existing credentials; plan a separately reviewed private migration before changing an initialized deployment. Never erase an existing vault to get past this guard. An old advisory `vault.db.lock` alone is not vault data and is left untouched.

A deployment whose old Vault reports uninitialized can start v2 without migrating credentials. Version 2 uses a separate filename, so the previous runtime cannot mistake it for a SQLCipher database.

## Agent use

`secrets_vault` lists metadata/opaque IDs, prepares private forms, edits name/description/tags, imports explicitly requested clipboard contents, and performs scoped HTTPS/SSH operations. It cannot set/unlock a password, return/delete secrets, issue recovery keys or grant itself usage permission. Only the user enables **Allow agent use**; that grants access to any profile agent, not only one session.

- HTTPS: Bearer token or Basic password, exact configured HTTPS origin, no redirects/arbitrary headers; optional JSON body, bounded/redacted result, 30-second timeout. Requests may modify remote data.
- SSH: configured host/port/username, existing trusted `known_hosts`, no automatic host acceptance or forwarding. Keys pass over stdin to a private temporary ssh-agent (60-second lifetime), not a key file. Encrypted-key passphrases use a one-shot protected Unix socket askpass broker, never argv/environment/secret disk files. Commands may modify remote systems.
- Clipboard: explicit macOS import while unlocked; creates or replaces a record and always revokes agent-use permission. No background monitoring, secret tool argument, result or clipboard clearing.

Output redaction covers known raw, URL-encoded and base64 values **best effort**; malicious servers can encode or split secrets. Never authorize untrusted endpoints. Pending UI requests are checked every two seconds while connected; dismissing a request does not keep reopening it, but a new explicit access/prepare request opens it again.

## Backup and recovery

For a consistent backup, click **Lock**, then copy **both** `vault.v2.json` and `vault.v2.json.recovery.json` with no concurrent recovery/rotation. Ownership markers and temporary files are not backup data. The data file alone is insufficient even with the master password. Keep password/recovery credentials separately from the pair.

New setup issues a recovery key privately. **Recover vault** accepts it and a new master password; **Replace recovery key** requires fresh master-password authentication. Both rotate the data encryption password and recovery credential; existing agent permissions remain unchanged and should be reviewed after suspected compromise. Keys never enter tools/status/list/notifications/chat. The issuance dialog requires confirmation that the external copy was saved.

Independent password/recovery envelopes use AES-256-GCM and asynchronous scrypt, with purpose/version/generation-bound associated data. Rekey first durably stages the envelope and an authenticated encrypted previous-key bridge; unlock can resume either side of an interrupted data-file replacement, then removes the bridge. Invalid envelopes fail closed without password-only fallback. Recovery transactions are serialized by the Host. A standalone core user must likewise serialize multi-step envelope workflows.

Issuance is not exactly-once: after a lost response, unlock with the **new** master password, then replace the recovery key rather than retrying the consumed key. Setup interrupted after envelope creation but before data creation preserves the envelope and refuses overwrite. Old full backups remain recoverable with their old credentials; offline snapshots cannot be revoked.

## Performance and remaining limits

The CPU-only [discovery benchmark](./discovery-benchmark.mjs) uses synthetic metadata and disables filesystem/ownership work. In one 200-iteration local run, 4096-record full clone/sort took median 8.239 ms (p95 8.712), versus 0.280 ms (p95 0.290) for a 100-row page; a single-row lookup took 0.002 ms (p95 0.003). These are not end-to-end or cross-machine guarantees. Idle client polling is already status-only every two seconds; full UI catalog refresh remains explicit. The model-facing serialized tool schema/description/prompt grew from 2351 to 3313 UTF-8 bytes to expose paging and validation (not a measured token count).

Remote operations still occupy the shared Host transaction queue, delaying metadata and lock requests. Keeping that queue avoids changing secret/lock ordering; parallel remote execution needs a separate ownership design. HTTPS combines caller cancellation with a 30-second deadline, manual redirects and a 65536-byte response cap. SSH applies 30-second per-process limits, not one whole-transaction deadline; multiple process phases and cleanup can take longer. Cancellation cannot roll back remote side effects. Synthetic tests cover HTTPS deadline wiring/body cancellation and shared-queue release, not remote behavior.

## Verification

The full suite below launches local OpenSSH/key-generation integration: run it only when explicitly authorized. For source-only verification, select the other test files explicitly and exclude `operations.test.mjs` entirely; `http-synthetic.test.mjs` replaces fetch and never connects.

Run `node --test *.test.mjs core/*.test.mjs` from this package directory. No Python provisioning or optional silent integration skips. Tests use isolated synthetic stores only, covering encryption, restart/rekey, corruption, ownership, concurrent writes and revision conflicts, atomic-failure boundaries, symlinks, disposal, private recovery and UI/tool authorization. Operations tests additionally launch local OpenSSH helpers with synthetic keys. GUI rendering and Windows/Linux platform behavior require separate verification.
