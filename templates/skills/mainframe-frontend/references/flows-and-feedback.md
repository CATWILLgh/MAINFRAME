# Flows and feedback

For the changed journey, identify only states that a real user can reach:

- entry and prerequisite state;
- loading or pending state;
- useful empty state;
- validation and recoverable error;
- unavailable, forbidden, or offline state when applicable;
- success and what changes afterward;
- cancellation, retry, undo, or destructive confirmation when the action needs it.

Keep feedback close to the action and specific enough to guide the next step. Preserve entered data after a recoverable failure. Do not show success before the authoritative operation succeeds. Do not use a toast as the only evidence for a durable state change when the changed page can show that state directly.

Test the risky transition, not every textual variation. Business outcomes belong in focused component or integration tests; browser tests are for browser wiring, focus, navigation, responsive behavior, and complete critical journeys.
