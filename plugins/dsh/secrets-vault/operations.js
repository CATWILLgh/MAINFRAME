import { spawn } from 'node:child_process';
import { mkdtemp, chmod, rm } from 'node:fs/promises';
import { createServer } from 'node:net';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const askpassHelper = fileURLToPath(new URL('./ssh-askpass', import.meta.url));

export function redact(value, secret) {
  const parts = Object.values(secret || {}).filter(v => typeof v === 'string' && v.length > 0);
  const variants = new Set(parts.flatMap(v => [v, encodeURIComponent(v), Buffer.from(v).toString('base64'), ...v.split('\n').filter(s => s.length > 20)]));
  let text = String(value);
  for (const v of [...variants].sort((a,b) => b.length-a.length)) text = text.split(v).join('[REDACTED]');
  return text;
}
export function approvedOrigin(metadata, target) {
  if (metadata.allowAgentUse !== true) throw new Error('Enable agent use in the vault first.');
  const allowed = new URL(metadata.url);
  const url = new URL(target);
  if (allowed.protocol !== 'https:' || url.protocol !== 'https:' || allowed.username || allowed.password || url.username || url.password || allowed.origin !== url.origin) throw new Error('Only the user-approved HTTPS origin is allowed.');
  return url;
}
export async function httpOperation(metadata, secret, args, signal) {
  const url = approvedOrigin(metadata, args.url);
  if (!['GET','HEAD','POST','PUT','PATCH','DELETE'].includes(args.method || 'GET')) throw new Error('Unsupported HTTP method.');
  let authorization;
  if (metadata.kind === 'token' && typeof secret.token === 'string') authorization = `Bearer ${secret.token}`;
  else if (metadata.kind === 'password' && typeof secret.password === 'string') authorization = `Basic ${Buffer.from(`${metadata.username || ''}:${secret.password}`).toString('base64')}`;
  else throw new Error('This credential cannot authenticate an HTTP request.');
  const response = await fetch(url, {method:args.method || 'GET', headers:{authorization,'content-type':'application/json'}, body:args.body, redirect:'manual', signal:AbortSignal.any([AbortSignal.timeout(30000), ...(signal ? [signal] : [])])});
  // Never return headers (Set-Cookie and Location can carry credentials).
  const reader = response.body?.getReader();
  let bytes = 0, chunks = [], truncated = false;
  if (reader) try { while (true) { const {done,value} = await reader.read(); if (done) break; bytes += value.length; if (bytes > 65536) { truncated = true; break; } chunks.push(value); } } finally { await reader.cancel().catch(()=>{}); }
  const text = Buffer.concat(chunks).toString('utf8');
  const secrets = {...secret, authorization, basic:Buffer.from(`${metadata.username || ''}:${secret.password || ''}`).toString('base64')};
  return {status:response.status, body:redact(text,secrets), truncated};
}
export function runProcess(command, args, {env, input, signal, limit=65536, detached=false}={}) {
  return new Promise((resolve,reject)=>{
    const child=spawn(command,args,{env,stdio:['pipe','pipe','pipe'],signal,detached});
    let output='',bytes=0,error;
    const timer=setTimeout(()=>child.kill('SIGKILL'),30000);
    const collect=chunk=>{bytes+=chunk.length; if(bytes<=limit) output+=chunk.toString('utf8'); else child.kill('SIGKILL');};
    child.stdout.on('data',collect); child.stderr.on('data',collect);
    // Wait for close after cancellation as well, so agent/socket cleanup cannot
    // race a still-running ssh-add. Spawn failures also emit close.
    child.on('error',()=>{error=new Error('Credential operation could not start.');});
    child.on('close',code=>{clearTimeout(timer);if(error) reject(error); else resolve({exitCode:code,output,truncated:bytes>limit});});
    child.stdin.on('error',()=>{}); child.stdin.end(input);
  });
}
// Internal SSH primitive, exported for local integration tests. Never accepts an
// existing agent socket. Only the fresh agent's environment reaches the callback.
export async function withSshAgent(secret, signal, operation) {
  if (typeof secret.privateKey !== 'string' || !secret.privateKey) throw new Error('Set an SSH private key in the vault.');
  if (secret.passphrase != null && typeof secret.passphrase !== 'string') throw new Error('Invalid SSH key passphrase.');
  const passphrase = secret.passphrase || '';
  // OpenSSH askpass is a single-line protocol, not an arbitrary binary channel.
  if (/[\r\n\0]/.test(passphrase) || Buffer.byteLength(passphrase) > 65535) throw new Error('SSH key passphrase must be a single line of at most 65535 UTF-8 bytes.');
  signal?.throwIfAborted();
  // Use a short, fixed system temp root (Unix socket paths have a small limit).
  // Neither the private key nor passphrase is ever written to this directory.
  const directory = await mkdtemp('/tmp/dsh-ssh-');
  const socket = join(directory, 'agent');
  const askpassSocket = join(directory, 'askpass');
  const connections = new Set();
  let server, pid, reply = Buffer.from(passphrase + '\n');
  const baseEnv = {PATH:'/usr/bin:/bin', ...(process.env.HOME ? {HOME:process.env.HOME} : {})};
  try {
    await chmod(directory, 0o700);
    server = createServer(connection => {
      connections.add(connection);
      connection.on('close', () => connections.delete(connection));
      connection.on('error', () => {});
      // Consume before writing: even simultaneous/repeated prompts get one reply.
      const once = reply;
      reply = undefined;
      if (!once) return connection.destroy();
      connection.end(once, () => once.fill(0));
      connection.on('close', () => once.fill(0));
    });
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(askpassSocket, resolve);
    });
    await chmod(askpassSocket, 0o600);
    const started = await runProcess('/usr/bin/ssh-agent',['-s','-a',socket,'-t','60'],{env:baseEnv});
    pid = Number(started.output.match(/SSH_AGENT_PID=(\d+)/)?.[1]);
    if (started.exitCode !== 0 || !Number.isSafeInteger(pid) || pid <= 0 || !started.output.includes(`SSH_AUTH_SOCK=${socket};`)) throw new Error('Could not create isolated SSH agent.');
    signal?.throwIfAborted();
    const env = {...baseEnv,SSH_AUTH_SOCK:socket,SSH_AGENT_PID:String(pid)};
    const addEnv = {...env,SSH_ASKPASS:askpassHelper,SSH_ASKPASS_REQUIRE:'force',DISPLAY:'dsh-askpass:0',DSH_SSH_ASKPASS_NODE:process.execPath,DSH_SSH_ASKPASS_SOCKET:askpassSocket,ELECTRON_RUN_AS_NODE:'1'};
    // detached also removes the controlling terminal on Unix; never prompt there
    // even on OpenSSH versions lacking SSH_ASKPASS_REQUIRE=force support.
    const added = await runProcess('/usr/bin/ssh-add',['-'],{env:addEnv,input:secret.privateKey+'\n',signal,detached:true});
    if (added.exitCode !== 0) throw new Error('SSH key could not be loaded. Check the key and passphrase.');
    // Tear down askpass before running any remote command. Remote SSH receives no
    // broker configuration or passphrase, and cannot ask for another credential.
    for (const connection of connections) connection.destroy();
    await new Promise(resolve => server.close(resolve));
    server = undefined;
    reply?.fill(0);
    reply = undefined;
    signal?.throwIfAborted();
    return await operation(env);
  } finally {
    reply?.fill(0);
    for (const connection of connections) connection.destroy();
    if (server) await new Promise(resolve => server.close(resolve));
    if (Number.isSafeInteger(pid) && pid > 0) { try { process.kill(pid,'SIGTERM'); } catch {} }
    // directory is the exact absolute mkdtemp result, never a user-supplied path.
    if (!directory.startsWith('/tmp/dsh-ssh-') || directory.slice('/tmp/dsh-ssh-'.length).includes('/')) throw new Error('Invalid SSH temporary directory.');
    await rm(directory, {recursive:true,force:true});
  }
}
// Kept explicit and testable: no user config, default private-key files, host-key
// enrollment, agent forwarding, local forwards, or interactive authentication.
export function sshArguments(metadata, args, socket) {
  return ['-F','/dev/null','-o','BatchMode=yes','-o','PreferredAuthentications=publickey','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no','-o','ClearAllForwardings=yes','-o','IdentityFile=none','-o','ConnectTimeout=15','-o',`IdentityAgent=${socket}`,'-p',String(metadata.port || 22),'--',`${metadata.username}@${metadata.host}`,args.command];
}
export async function sshOperation(metadata, secret, args, signal) {
  if (metadata.allowAgentUse !== true || metadata.kind !== 'ssh-key') throw new Error('Enable agent SSH use in the vault first.');
  if (!/^[a-zA-Z0-9._-]+$/.test(metadata.host || '') || !/^[a-zA-Z0-9._-]+$/.test(metadata.username || '') || metadata.host.startsWith('-') || metadata.username.startsWith('-')) throw new Error('Set a valid SSH host and username in the vault.');
  if (typeof args.command !== 'string' || args.command.trimStart().startsWith('-')) throw new Error('Invalid remote command.');
  if (metadata.port != null && (!Number.isInteger(metadata.port) || metadata.port < 1 || metadata.port > 65535)) throw new Error('Invalid SSH port.');
  return withSshAgent(secret, signal, async env => {
    const result=await runProcess('/usr/bin/ssh',sshArguments(metadata,args,env.SSH_AUTH_SOCK),{env:{...env,SSH_ASKPASS_REQUIRE:'never'},signal});
    return {...result,output:redact(result.output,secret)};
  });
}
