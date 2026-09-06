# Keep hook failures visible and bounded

Source: [_hooklib.py](../../../templates/hooks/scripts/_hooklib.py), [_notice_state.py](../../../templates/hooks/scripts/_notice_state.py).

The reference runner exits nonzero on execution failure and prints only the error class. The native binding must map that signal to bounded feedback or guard refusal; the helper alone is not a complete failure lifecycle.

Purpose: a broken hook produces actionable feedback once instead of silent
loss of protection, transcript spam, or an endless completion loop.

`{{HOOK_BINDING}}`: use the native hook error and timeout mechanism. Distinguish
successful silence, a reported finding, an execution failure, and unavailable
protection. Keep ordinary successful checks silent. Report component, short
error class, consequence, and the allowed next step without raw tool input.

Apply these behavior requirements to every installed hook rather than adding
another hook when the runtime already handles failures correctly. Use only the
small temporary state needed to deduplicate a task's active failure and avoid
cross-task races.

An advisory hook failure must not loop forever at completion. A required guard
failure must not silently permit the protected action. Report concrete harness
faults through the global feedback instruction, preserving the recipient's
role and authority instead of telling a delegate to impersonate the operator.

Check success, malformed input, exceptions, timeout, repeated identical events,
two concurrent tasks, and recovery after correction. Verify one bounded
diagnostic and that the recovered hook can run normally again.
