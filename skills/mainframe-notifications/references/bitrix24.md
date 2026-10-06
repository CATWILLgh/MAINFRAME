# Bitrix24 notification channel

Use the target portal's documented API revision. Chat Bots 2.0 is not the legacy
`imbot.*` contract: inspect Revision.get before relying on newer fields. Do not
add inbound event processing or token rotation merely to send notifications.

## Credentials and registration

An incoming REST webhook needs `imbot` scope. Its URL credential and a bot's
`botToken` are different secrets. Webhook registration requires the bot token;
OAuth has a different authentication contract. Keep a stable, cryptographically
random bot token within the documented length limit (40 characters); fail if
secure randomness fails, never substitute a timestamp. Save its protected
identity before registration so retries do not invent a new bot identity.

`Bot.register` with the same code and application returns the existing bot;
it does **not** update its profile. A webhook registration with the same code
and a different token can fail with `BOT_CODE_ALREADY_TAKEN`. Use `Bot.update`
for an existing bot. Use documented property casing, including `lastName` and
`workPosition`. Validate the returned bot/message ID; HTTP success with a missing
ID is not proof of a successful action.

Keep Save (local settings), Apply/register (external create/update), and Test
(one explicit destination) separate. Serialize concurrent registration and use
saved bot identity; after a timeout reconcile before attempting another create.
Never print webhook URLs, tokens, raw transport errors containing URLs, or
unbounded provider bodies.

## Delivery

`Chat.Message.send` uses a user ID string or `chat{chatId}` as `dialogId`.
The bot must have access to the target chat. Messages above 20,000 characters
are documented as truncated: enforce a deliberate formatting/splitting policy
before sending. Escape dynamic content for the supported message format.
The returned message ID proves acceptance, not reading or human receipt.
There is no documented send idempotency key; a lost response can mean the
message was accepted. Do not use forwarding IDs as a deduplication mechanism.

Inspect both HTTP status and the bounded JSON error envelope. Rate-limit
classification must consider provider codes: the dedicated limits page lists
503 `QUERY_LIMIT_EXCEEDED` and 429 `OPERATION_TIME_LIMIT` with
`operating_reset_at`; overview guidance also describes 429 for rate exhaustion.
Preserve that documentation discrepancy instead of hardcoding a single status.
Use the target plan's limits and coordinate workers sharing the portal/IP.
Permission, recipient and malformed-request failures need correction, not blind
retries. Do not upgrade a bot to supervisor solely to bypass permissions.

## Optional lifecycle operations

Rotation requires a compatible revision (documented from revision 35). Authenticate
with the old top-level token and put the new token in `fields.botToken`.
The old token becomes invalid immediately. The remote change and local storage
are not one transaction: serialize rotation, retain the protected candidate and
a durable pending operation, and reconcile an unknown outcome or failed local
save. Never blindly generate another token after a timeout.

For `eventMode=fetch`, Event.get's `offset` acknowledges events with smaller IDs.
Persist the complete fetched page durably before advancing to its `nextOffset`;
process idempotently. Do not acknowledge an unprocessed page by guessing last-ID
arithmetic. Fetch mode avoids a public callback but still needs a durable cursor
and access control. Do not borrow retention guarantees from a different event API.

## Primary sources

Reviewed 2026-10-03; verify target capability when applying:

- [Quick start and authentication](https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/quick-start.html)
- [Register](https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/imbot.v2/bots/bot-register.html)
- [Update and rotation](https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/imbot.v2/bots/bot-update.html)
- [Send](https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/imbot.v2/messages/chat-message-send.html)
- [Fetch and acknowledgement](https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/imbot.v2/events/event-get.html)
- [Revision](https://apidocs.bitrix24.com/api-reference/chat-bots/chat-bots-v2/imbot.v2/revision-get.html)
- [Limits](https://apidocs.bitrix24.com/limits.html)
