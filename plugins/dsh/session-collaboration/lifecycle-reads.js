// Read-only pre-admission work may outlive a tool without holding plugin teardown.
// Never use this helper to abandon an admitted mutation or Agent activation.
export function readBeforeAdmission(operation, signal) {
  signal?.throwIfAborted();
  if (!signal) return Promise.resolve().then(operation);
  return new Promise((resolve, reject) => {
    const cleanup = () => signal.removeEventListener('abort', aborted);
    const aborted = () => { cleanup(); reject(signal.reason); };
    signal.addEventListener('abort', aborted, { once: true });
    Promise.resolve().then(() => {
      signal.throwIfAborted();
      return operation();
    }).then(value => { cleanup(); resolve(value); }, error => { cleanup(); reject(error); });
  });
}
