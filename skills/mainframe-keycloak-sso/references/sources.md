# Primary sources

Reviewed 2026-10-03. These are protocol/implementation references, not evidence
that a receiving application's deployment passes acceptance. Check the installed
Keycloak and chosen OIDC library versions when a behavior or option matters.

- [OpenID Connect Core, errata set 2](https://openid.net/specs/openid-connect-core-1_0.html):
  ID-token validation §3.1.3.7, UserInfo subject validation §5.3.2 and stable
  identity §5.7. Use exact issuer/subject identity rather than profile names.
- [OAuth security BCP, RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html):
  redirect validation, PKCE, response/token leakage, replay and refresh-token
  protection. Removing a fragment later does not make token-in-URL handoff a
  safe default. The server-session preference here is an integration choice.
- [Keycloak OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers):
  discovery, authorization, token, UserInfo and logout endpoints and their roles.
- [Keycloak JavaScript adapter](https://www.keycloak.org/securing-apps/javascript-adapter):
  public browser clients, PKCE and browser token handling; do not give a SPA a
  confidential client secret.
- [Keycloak hostname configuration](https://www.keycloak.org/server/hostname):
  public issuer/frontchannel identity, proxy and backchannel configuration.
- [Keycloak server administration](https://www.keycloak.org/docs/latest/server_admin/index.html):
  client configuration, scopes, group mappers and account-linking policy. Follow
  the documentation for the deployed version rather than fixed console clicks.

The admin screen, explicit secret update operations, default-deny group mapping
and acceptance matrix are this skill's application contract. They are not claims
that OIDC mandates a particular UI, storage schema or application role model.
