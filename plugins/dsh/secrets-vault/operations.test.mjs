import test from 'node:test';
import assert from 'node:assert/strict';
import {approvedOrigin,redact,sshOperation,sshArguments,withSshAgent,runProcess} from './operations.js';
import { mkdtemp, readFile, rm, stat, access, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
test('HTTPS scope is exact and never follows redirect/auth URL',()=>{
 const m={allowAgentUse:true,url:'https://example.com/path'};
 assert.equal(approvedOrigin(m,'https://example.com/other').origin,'https://example.com');
 for(const u of ['http://example.com','https://evil.example.com','https://example.com:8443','https://user:pass@example.com']) assert.throws(()=>approvedOrigin(m,u));
 assert.throws(()=>approvedOrigin({...m,allowAgentUse:false},m.url));
});
test('redacts raw, URL, base64 and multiline key fragments',()=>{
 const secret={token:'synthetic+/=token',privateKey:'-----BEGIN KEY-----\n123456789012345678901234567890\n-----END KEY-----'};
 for(const v of [secret.token,encodeURIComponent(secret.token),Buffer.from(secret.token).toString('base64'),'123456789012345678901234567890']) assert(!redact(v,secret).includes(v));
});
test('SSH forbids option commands and requires user authority before starting',async()=>{
 await assert.rejects(sshOperation({kind:'ssh-key',allowAgentUse:false},{privateKey:'fake'},{command:'id'}));
 await assert.rejects(sshOperation({kind:'ssh-key',allowAgentUse:true,host:'host',username:'user'},{privateKey:'fake'},{command:' -oProxyCommand=evil'}));
 await assert.rejects(sshOperation({kind:'ssh-key',allowAgentUse:true,host:'host',username:'user',port:'22'},{privateKey:'fake'},{command:'id'}));
});

test('SSH uses only its isolated agent, known hosts, and no forwarding', async () => {
 const args = sshArguments({host:'synthetic.invalid',username:'test',port:2222},{command:'id'},'/tmp/synthetic-agent');
 for (const option of ['BatchMode=yes','PreferredAuthentications=publickey','StrictHostKeyChecking=yes','ForwardAgent=no','ClearAllForwardings=yes','IdentityFile=none','IdentityAgent=/tmp/synthetic-agent']) assert(args.includes(option));
 assert.deepEqual(args.slice(0,2), ['-F','/dev/null']);
 // Ask ssh to expand config only: this does not connect or read any key.
 const config = await runProcess('/usr/bin/ssh',['-G',...args],{env:{PATH:'/usr/bin:/bin',HOME:process.env.HOME}});
 assert.equal(config.exitCode,0);
 for (const line of ['stricthostkeychecking true','forwardagent no','clearallforwardings yes','identityfile none','identityagent /tmp/synthetic-agent']) assert(config.output.includes(line),line);
});

test('SSH rejects unsupported passphrase framing and honors pre-aborted signals', async () => {
 for (const passphrase of ['line\nbreak','line\rbreak','nul\0byte','x'.repeat(65536),42]) {
  await assert.rejects(withSshAgent({privateKey:'fake',passphrase},undefined,()=>assert.fail('must not start')));
 }
 const controller = new AbortController(); controller.abort();
 await assert.rejects(withSshAgent({privateKey:'fake'},controller.signal,()=>assert.fail('must not start')));
});

test('real local ssh-agent loads encrypted keys through one-shot private askpass', {timeout:60000}, async t => {
 // Synthetic-only fixtures. ssh-keygen is allowed files/argv for generated test
 // material; production operation below receives key/passphrase only in memory.
 const directory = await mkdtemp(join(tmpdir(),'dsh-synthetic-ssh-'));
 const passphrase = 'synthetic only: $() `quotes` ü +/= test';
 const env = {PATH:'/usr/bin:/bin',HOME:directory};
 const fixtures = [];
 try {
  for (const [name,options] of [
   ['openssh-ed25519',['-t','ed25519']],
   ['pem-rsa',['-t','rsa','-b','2048','-m','PEM']],
   ['plain-ed25519',['-t','ed25519']]
  ]) {
   const path = join(directory,name);
   const phrase = name.startsWith('plain') ? '' : passphrase;
   const generated = await runProcess('/usr/bin/ssh-keygen',['-q',...options,'-N',phrase,'-C','synthetic-ssh-test','-f',path],{env});
   assert.equal(generated.exitCode,0,generated.output);
   fixtures.push({privateKey:await readFile(path,'utf8'),passphrase:phrase,publicKey:(await readFile(path+'.pub','utf8')).trim()});
  }
  for (const fixture of fixtures) await t.test(fixture.publicKey.split(' ')[0]+(fixture.passphrase ? ' encrypted' : ' unencrypted'), async () => {
   let agentDirectory;
   const value = await withSshAgent(fixture, undefined, async agentEnv => {
    agentDirectory = join(agentEnv.SSH_AUTH_SOCK,'..');
    assert.equal((await stat(agentDirectory)).mode & 0o777,0o700);
    assert.equal((await stat(agentEnv.SSH_AUTH_SOCK)).mode & 0o777,0o600);
    assert.deepEqual((await readdir(agentDirectory)).sort(),['agent']);
    await assert.rejects(access(join(agentDirectory,'askpass'))); // closed before callback
    assert.equal(agentEnv.DSH_SSH_ASKPASS_SOCKET,undefined);
    assert.equal(agentEnv.SSH_ASKPASS,undefined);
    assert(!Object.values(agentEnv).some(v=>String(v).includes(passphrase)));
    const listed = await runProcess('/usr/bin/ssh-add',['-L'],{env:agentEnv});
    assert.equal(listed.exitCode,0,listed.output);
    // Legacy PEM does not carry its public-key comment into the agent.
    assert.deepEqual(listed.output.trim().split(' ').slice(0,2),fixture.publicKey.split(' ').slice(0,2));
    assert.equal(listed.output.trim().split('\n').length,1);
    return 'loaded';
   });
   assert.equal(value,'loaded');
   await assert.rejects(access(agentDirectory));
  });
  await t.test('wrong or missing passphrase fails without retry or leaked secret', async () => {
   for (const phrase of ['wrong synthetic passphrase','']) {
    await assert.rejects(withSshAgent({...fixtures[0],passphrase:phrase},undefined,()=>assert.fail('must not execute')), error => {
     assert.match(error.message,/SSH key could not be loaded/);
     assert(!error.message.includes(passphrase));
     return true;
    });
   }
  });
  await t.test('ambient agents and askpass configuration are never inherited', async () => {
   const names = ['SSH_AUTH_SOCK','SSH_AGENT_PID','SSH_ASKPASS','SSH_ASKPASS_REQUIRE','NODE_OPTIONS'];
   const previous = Object.fromEntries(names.map(name=>[name,process.env[name]]));
   try {
    process.env.SSH_AUTH_SOCK='/tmp/arbitrary-synthetic-agent';
    process.env.SSH_AGENT_PID='123';
    process.env.SSH_ASKPASS='/tmp/arbitrary-synthetic-askpass';
    process.env.SSH_ASKPASS_REQUIRE='never';
    process.env.NODE_OPTIONS='--require=/tmp/nonexistent-synthetic-node-module';
    await withSshAgent(fixtures[0],undefined,async agentEnv => {
     assert.notEqual(agentEnv.SSH_AUTH_SOCK,process.env.SSH_AUTH_SOCK);
     assert.notEqual(agentEnv.SSH_AGENT_PID,process.env.SSH_AGENT_PID);
     assert.equal(agentEnv.SSH_ASKPASS,undefined);
     assert.equal(agentEnv.NODE_OPTIONS,undefined);
     const listed=await runProcess('/usr/bin/ssh-add',['-L'],{env:agentEnv});
     assert.equal(listed.exitCode,0);
     assert.deepEqual(listed.output.trim().split(' ').slice(0,2),fixtures[0].publicKey.split(' ').slice(0,2));
    });
   } finally {
    for (const name of names) if (previous[name] === undefined) delete process.env[name]; else process.env[name]=previous[name];
   }
  });
  await t.test('cleanup on callback failure and cancellation', async () => {
   let location;
   await assert.rejects(withSshAgent(fixtures[0],undefined,async agentEnv => {
    location = join(agentEnv.SSH_AUTH_SOCK,'..');
    throw new Error('synthetic failure');
   }),/synthetic failure/);
   await assert.rejects(access(location));
   const controller = new AbortController();
   await assert.rejects(withSshAgent(fixtures[0],controller.signal,async agentEnv => {
    location = join(agentEnv.SSH_AUTH_SOCK,'..');
    controller.abort();
    return runProcess('/usr/bin/ssh-add',['-L'],{env:agentEnv,signal:controller.signal});
   }));
   await assert.rejects(access(location));
  });
 } finally {
  // directory is the exact mkdtemp result created above, never a user path.
  assert(directory.startsWith(join(tmpdir(),'dsh-synthetic-ssh-')));
  await rm(directory,{recursive:true,force:true});
 }
});

test('askpass helper fails closed without a private broker', async () => {
 const helper = fileURLToPath(new URL('./ssh-askpass',import.meta.url));
 const result = await runProcess(helper,[],{env:{PATH:'/usr/bin:/bin',DSH_SSH_ASKPASS_NODE:process.execPath,DSH_SSH_ASKPASS_SOCKET:'/tmp/nonexistent-dsh-synthetic-socket'}});
 assert.equal(result.exitCode,1);
 assert.equal(result.output,'');
});
