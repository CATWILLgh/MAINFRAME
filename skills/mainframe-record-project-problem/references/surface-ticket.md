# Surface an unresolved project problem

The trigger is a decision to leave an evidenced problem unresolved after the current result, not the act of noticing something suspicious.

Surface each of these when it will remain:

- debt introduced by the work, such as a deliberate workaround, partial correction, weakened check, or postponed refactor;
- a concrete adjacent problem encountered in the code or behavior being examined;
- a pre-existing failure that the work directly observes but does not own.

Do not surface a separate ticket when the problem is still part of the assigned result, prevents that result from being achieved, or prevents its required verification. Return it to the active work instead. Do not use a TODO, suppression marker, vague handoff note, or ticket as a substitute for completing in-scope work.

Use the receiving project's configured issue route, identity, schema, lifecycle, and duplicate policy. When no route exists, use the skill's new-queue setup within local write authority. That fallback uses `mainframe-tickets-v1`; an existing project route retains its own contract.

Keep the record proportional to the evidence already produced. Group one clearly related failure cluster when separate records would only repeat the same mechanism and next investigation. Keep distinct mechanisms separate. If the route or write authority is unavailable, return one ticket-ready record through the current execution path and state exactly why it was not persisted.
