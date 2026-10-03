# Settings page and user outcome

Implement the controls in the receiving application's visual language, with
its localization and native components. The core hierarchy is a master switch,
channel tabs/cards and an Events tab. Show only implemented channels, plus clear
unsupported/not-configured states when they help an operator choose an action.

## Visible controls

- **Master switch**: saved enabled/disabled state; concise explanation of pending
  work and in-flight limits. Distinguish draft changes from active configuration.
- **Channel card**: independent enable switch, destination and credentials,
  field validation, configuration status and last bounded test result. Do not
  expose saved secrets or token suffixes. Changing fields invalidates old test
  results; failed saves preserve drafts and show the actual saved state.
- **Bitrix24 card**: webhook credential, bot name/code/profile position,
  user/dialog destination, provider bot ID/status, supported visibility controls.
  Keep **Apply and register/update**, **Test**, and **Save** distinct. Save persists
  local settings; register/update mutates the portal; Test sends a labeled message
  to an explicit test recipient. Disable unsupported bot controls rather than
  claiming the portal accepted them. Repeat clicks must not create duplicate bots.
- **Telegram card**: token-present/replace controls, chat and optional topic
  destination, permissions/reachability feedback; no claim that a valid token
  establishes chat access.
- **Webhook card**: independent HTTPS endpoint, selected event/schema contract,
  authentication/signing scheme and protected rotation controls. This is not the
  Bitrix24 portal's incoming REST webhook field.
- **Email card**: verified sender, SMTP host/port and explicit TLS mode, protected
  authentication, authorized recipients. Separate envelope and displayed fields
  where the project needs them; do not disclose other recipients accidentally.
- **Web Push**: admin channel configuration/public key status, and separate
  authenticated-user/browser opt-in, permission/unsupported/subscribed states,
  unsubscribe and targeted test. Never ask for browser permission on page load.
- **Events tab**: actual application event catalog with plain descriptions,
  per-event enable/routing/recipient policy, severity/conditions where supported,
  and templates with allowed variables and synthetic preview. No copied project
  event names or imaginary handlers. Show unavailable event integrations explicitly.

## Content and actions

Templates are bounded data transformations, not shell/code or arbitrary object
access. Escape for each channel's syntax, reject invalid variables and validate
length/encoding after rendering. Offer a useful fallback only when it cannot
hide a broken critical template. Build message content for its reader: what
happened, affected object, when, severity and safe next action. Include tenant
context when needed; link to a trusted app origin, with authorization checked on
open. Do not put confidential detail into public chats, email subjects or lock-
screen notifications. Keep IDs/timestamps useful without flooding routine alerts.

A preview has no external effect. A test uses the explicitly shown draft/saved
configuration and a selected recipient; never silently test all subscribers.
Show partial recipient results, provider accepted versus unknown/failed, and
confirmation of receipt only when observed. Tests must not register bots, rotate
credentials or persist drafts implicitly. Disabling a button while busy is not
server-side idempotency or permission enforcement.

Implement loading, retry, empty/not-configured, dirty/unsaved, validation, saving,
revision conflict, testing, partial failure, disabled and unavailable states.
Label controls, support keyboard focus and announce results. Stack fields on
small screens and check contrast in supported themes. Keep sensitive settings
admin-only on server and UI; personal subscriptions are owned by the current user,
not a globally editable admin-only substitute.

## Acceptance

Render the actual page using synthetic credentials and recipients. Exercise
master/channel switches, event selection, template errors/preview, secret
preservation/replacement/clear, save/reload and conflict, bot registration/update,
explicit test targeting and failure statuses. Verify backend state and outgoing
requests as well as appearance. Browser screenshots should capture safe states
without live tokens, endpoint capabilities or personal data. A mock-up alone
cannot prove queue behavior, portal mutation or provider delivery.
