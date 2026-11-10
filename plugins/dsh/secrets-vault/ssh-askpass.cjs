// Invoked only by the static ssh-askpass launcher. Never log prompts or replies.
'use strict';
const net = require('node:net');
const socket = net.createConnection({path: process.env.DSH_SSH_ASKPASS_SOCKET});
const chunks = [];
let size = 0;
const fail = () => { socket.destroy(); process.exitCode = 1; };
const timer = setTimeout(fail, 5000);
socket.on('data', chunk => {
  size += chunk.length;
  if (size > 65536) fail();
  else chunks.push(chunk);
});
socket.on('end', () => {
  clearTimeout(timer);
  if (process.exitCode) return;
  if (size === 0) return fail();
  const reply = Buffer.concat(chunks);
  if (reply[reply.length - 1] !== 10) return fail();
  process.stdout.write(reply, () => {
    reply.fill(0);
    for (const chunk of chunks) chunk.fill(0);
  });
});
socket.on('error', () => { clearTimeout(timer); fail(); });
socket.on('close', () => clearTimeout(timer));
process.stdout.on('error', fail);
