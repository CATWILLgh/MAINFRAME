---
name: mainframe-notifications
description: Implement or troubleshoot application notifications and their settings UI, event routing, templates and delivery through Bitrix24, Telegram, webhooks, email or Web Push. Not one-off message sending, chat UI toasts or messaging-server deployment alone.
---

# Application notifications

Deliver the working event-to-recipient flow and its administrative controls in
the receiving application's stack and design system. Use only the channels the
project needs; do not introduce a broker, new framework, chatbot agent or all
five channels just because this method describes them. A settings screenshot
or successful HTTP call is not end-to-end acceptance.

Inspect existing events, transactions, jobs, identities/tenants, settings,
authorization, session/CSRF controls, secrets, UI and tests. Establish which events
reach which recipients, content sensitivity, acceptable loss/duplication/delay,
and actual provider capability. Reuse established decisions; ask for unresolved
policy that changes access, external disclosure or delivery guarantees.
Development authority does not itself authorize messages to real recipients,
registration of external bots or production credential rotation.

## Load by current decision

- [Delivery](references/delivery.md): event contract, durability, retries,
  isolation, pause behavior, ordering and honest outcome states.
- [Settings and interface](references/interface.md): page outcome, master/channel
  switches, events, templates, recipients, secret updates and distinct actions.
- [Bitrix24](references/bitrix24.md): portal webhook versus bot-token auth,
  registration, messages, optional event consumption and recovery.
- [Telegram](references/telegram.md): Bot API delivery and channel constraints.
- [Webhook](references/webhook.md): an independent outbound integration channel,
  signed delivery, recipient contract and endpoint security.
- [Email](references/email.md): submission security, partial acceptance and retries.
- [Web Push](references/web-push.md): browser subscriptions, ownership and receipts.
- [Verification](references/verification.md): failure scenarios, rendered UI and
  authorized channel acceptance. Each channel reference links its primary sources.

Use the appropriate engineering method for code and `mainframe-testing` for test
boundaries. Use `mainframe-secrets` for actual credential delivery. Infrastructure
changes belong to `mainframe-infrastructure`, within the existing task authority.

## Complete the slice

Wire committed application events to the selected channels, persistence and
recipient authorization. Separate pure formatting from provider transport and
from administrative external actions. Keep important enqueue failures visible;
network delivery must not hold a business transaction open. Add the settings and
login-independent subscription UI only where appropriate to those roles.

Preserve source event identity across retries. Store bounded delivery evidence,
not unnecessary message bodies or credentials. Provide retry/recovery controls
that reflect the duplicate risk and prevent re-sending successful destinations.
Apply and invalidate versioned settings across replicas without wiping secrets
or silently moving queued messages to a newly configured recipient.

Exercise real controls, stored settings, worker failures and each enabled
channel's contract. Report mock, CI, provider acceptance and observed recipient
receipt separately. Leave exact operator steps for unperformed external actions;
do not label an untested channel ready or silently route it through another one.
