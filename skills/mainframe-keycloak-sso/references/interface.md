# Admin and login interface contract

Aim for a complete native settings page, usable in light or dark themes. Reuse
the app's form components, navigation, spacing, typography and translations.
Do not impose a framework or copy another application's names, presets or CSS.
The outcome is a working screen and login flow, not a mock screenshot.

## Screen hierarchy

1. **SSO / Keycloak header** with visible saved enabled/disabled state and a
   clearly labeled toggle. Explain whether changes are a draft awaiting Save;
   do not imply that an unsaved toggle already changed authentication.
2. **Connection card**:
   - Provider display name, with a preview of the login button label.
   - Realm URL with a neutral `https://auth.example.com/realms/example` hint.
   - Client ID; confidential-client secret input with a saved-secret indicator,
     explicit replace/clear behavior and no existing value revealed.
   - Read-only **Redirect URI**, computed by the server, with Copy and short
     instructions to register it under the client's valid redirect URIs.
3. **Roles card**:
   - Configured groups claim, normally `groups`.
   - Ordered rows: exact IAM group/path, application role selector, remove.
   - Add mapping; keyboard-accessible priority controls when first-match wins.
   - Role without mapping, default **No access (deny)**. Explain the actual
     matching policy and precedence concisely beside the editor.
   - Empty-state warning: enabling with no mappings and default deny means no
     mapped user can log in. Do not silently add admin or weaken the default.
4. **Actions**: Test draft connection, Save, and discard/reload when consistent
   with the application. Keep pending and saved states visibly distinct.

Show server-authorized roles only; still validate the submitted role on the
server. Presets are optional project-owned data, not hard-coded organization
policy. Explain exact matching with a neutral example; never silently present
leaf-name/case-insensitive matching as equivalent to full group paths.

## Interaction and error states

Implement initial loading, load failure/retry, field validation, dirty state,
unsaved navigation, saving success/failure, revision conflict, testing progress,
partial/not-tested diagnostics, enabled/disabled and no-mapping states. Preserve
draft input on recoverable errors. A test does not save or activate changes.
Disable duplicate submissions without trapping keyboard focus. Associate labels
and errors with controls, announce result changes, and make Copy success/failure
accessible. Stack fields and mapping rows at narrow widths; verify both supported
themes, focus visibility and contrast. Use the existing admin access boundary on
both page and endpoints; hiding navigation alone is insufficient.

## Login integration

Show a full-browser-navigation button such as “Sign in with {displayName}” when
the saved provider is enabled. Render the display name as text, not HTML. Preserve
existing local login and its intended post-login destination. Do not copy a PIN
mode exclusion from an unrelated product. Handle cancelled login, unavailable
provider, expired transaction and denied access with localized actionable errors
and a safe retry; keep detailed protocol failures out of the page and URL.

Show claims about parallel local login or automatic account creation only when
those features and policies actually exist. A successful callback uses the app's
normal authenticated state and session lifecycle; decoding JWT claims in the UI
is not server authorization.

## Visual acceptance

Render the actual app with synthetic connection values and mappings. Inspect a
saved configuration, empty fail-closed configuration, test failure/partial result,
secret replacement, narrow viewport and supported themes. Exercise add/remove,
ordering, copy, test and save. Record screenshots without secrets or personal
data. Verify network responses and persistence behind the controls; a static
form, screenshot or mocked successful test alone does not satisfy this contract.
