const child_process = require("child_process");
const https = require("https");

function unsafe(value) {
  // ruleid: mainframe.javascript.dynamic-child-process-exec
  child_process.exec(`echo ${value}`);
  // ruleid: mainframe.javascript.tls-verification-disabled
  return new https.Agent({ rejectUnauthorized: false });
}

function safe(value) {
  // ok: mainframe.javascript.dynamic-child-process-exec
  child_process.execFile("echo", [value]);
  // ok: mainframe.javascript.tls-verification-disabled
  return new https.Agent({ rejectUnauthorized: true });
}
