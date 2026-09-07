# Dokploy managed databases

Identify the exact engine, version, environment, database resource, storage,
network consumers, backup configuration, and generated internal endpoint.
Engine lifecycle and required credential fields differ; retrieve the current
schema instead of copying another engine's payload.

For creation or configuration, pass registered values directly through the
approved secret-delivery mechanism. Never put passwords, connection strings
with passwords, or environment payloads into chat, patches, traces, or
temporary ordinary files.

Prefer the platform's internal network identity for colocated applications.
Expose a database publicly only when the task requires it and the access,
firewall, TLS, and authentication consequences are understood.

Provisioning, reload, rebuild, stop, and removal can be asynchronous or
disruptive. Verify the current endpoint semantics, follow terminal state,
inspect bounded logs, and test the intended connection without displaying its
credentials.

Before destructive changes, establish a completed and restorable backup for
the correct database. Removing a managed resource, storage, or parent
environment may have different consequences across versions; never infer them
from the action name.
