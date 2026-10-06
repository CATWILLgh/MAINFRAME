---
name: mainframe-keycloak-sso
description: Implement, adapt, or troubleshoot Keycloak OIDC login in a web application, including an admin connection screen, group-to-role mapping, account linking, and session lifecycle. Not Keycloak server deployment or login-page theming alone.
---

# Keycloak SSO integration

Deliver working corporate login and its administration flow in the receiving
application's conventions. A settings form alone is not a completed integration.
Keep the application's established framework, session architecture, design system,
roles and localization. This method does not authorize production IAM changes,
account linking, deployment or access-policy changes outside the assigned task.

## Establish the integration boundary

Inspect existing login/session, users, authorization middleware, settings storage,
admin navigation, public origin/proxy configuration and relevant tests. Identify
which part already exists before adding a second authentication system. Determine
whether the app has a trusted backend/BFF or is a public browser-only client;
a browser-only client cannot hold a client secret. Reuse a maintained OIDC library
appropriate to that architecture, not hand-written JWT cryptography.

Reuse established policy for JIT provisioning, linking, role precedence, local
login and session revocation. Ask only for unresolved access decisions. For new
integrations default to disabled SSO, exact group matching and denial when no
mapping grants access. Never silently grant a default role or merge accounts.

Read only the references needed for the current part:

- [Protocol and identities](references/protocol.md): callbacks, tokens, account
  linking, authorization, multi-instance operation and lifecycle.
- [Settings and API](references/settings.md): storage, secret updates, safe
  connection diagnostics and configuration transitions.
- [Admin and login UX](references/interface.md): the required screen, visible
  states, mapping editor and functional acceptance, in the app's own style.
- [Verification](references/verification.md): negative cases, browser acceptance
  and the boundary between mock evidence and an actual Keycloak login.
- [Primary sources](references/sources.md): current contracts to consult when
  selecting a library or resolving version-sensitive behavior.

Use the relevant backend/frontend method for implementation and
`mainframe-testing` for its local/CI boundaries. Use `mainframe-infrastructure`
for an authorized deployment or proxy change and `mainframe-secrets` for actual
credential delivery; public documentation work needs no credentials.

## Produce a complete vertical slice

Connect provider discovery, login start/callback, identity resolution and existing
app sessions to the admin settings and role editor. Add migrations in the
project's migration system, with uniqueness/race handling and a rollback plan
that does not delete existing users. Keep local recovery login if it exists;
SSO failure must not silently disable it or grant SSO users its privileges.

Persist and apply validated configuration consistently across instances. Make
save, test and enable distinct actions. A test of draft settings must not
activate them. Keep an in-flight login bound to its starting configuration or
reject it explicitly after a configuration revision; never mix realms/secrets.

Verify the security boundaries and render the actual admin/login states with
synthetic values. Compare the resulting functionality and hierarchy to the
interface contract, not only to a source-code checklist. On completion report
what works, what was tested, any unresolved access decisions and exact remaining
operator steps. A fake IdP or green connection test is not a live SSO acceptance.
