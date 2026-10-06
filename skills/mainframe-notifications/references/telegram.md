# Telegram notification channel

Use Bot API credentials on the server. Token-bearing URL errors must be redacted;
never return the bot token in settings reads. Bind destinations to authorized
users/tenants and distinguish private chats, groups and topic/thread IDs. A bot
cannot initiate a private conversation with an arbitrary user: establish contact
or group membership through the supported onboarding flow.

`sendMessage` accepts 1–4096 characters after entity parsing. Prefer plain text
unless formatting is needed; otherwise escape dynamic content for the selected
HTML/Markdown mode and split without breaking entities. Persist stable part IDs
so a failed later part does not resend earlier successful ones.

Inspect HTTP and JSON `ok`, `result`, `error_code` and `parameters`. Store the
returned Message identity as provider acceptance, not a read receipt. There is
no documented `sendMessage` idempotency parameter: timeouts after dispatch can
have an unknown outcome, and retries can duplicate messages. Resolve policy for
that risk rather than promise exactly-once delivery.

Honor `retry_after`, coordinate per-chat and overall rate budgets, and handle
`migrate_to_chat_id` using a signed 64-bit-safe representation. Validate destination
ownership before applying migration. Do not loop on forbidden or invalid-chat
responses. Published guidance includes about one message/second per chat,
20/minute in groups and about 30/second bulk; use current provider responses and
limits rather than assuming these are guaranteed quotas. Paid broadcasts require
an explicit cost decision; never enable them automatically.

Test exact draft/saved configuration against one selected destination only when
sending is authorized. A Telegram failure must not silently fall back to another
channel or block all unrelated deliveries.

## Primary sources

Reviewed 2026-10-03; refresh changing limits when implementing:

- [sendMessage](https://core.telegram.org/bots/api#sendmessage)
- [Response parameters](https://core.telegram.org/bots/api#responseparameters)
- [Limits](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this)
- [Bot onboarding constraints](https://core.telegram.org/bots#how-are-bots-different-from-users)
