#!/usr/bin/env node
'use strict';

// Developer evidence only. Never import or execute the application bundle.
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const expectedSha256 = 'e9f1868c0fdb863537ed910ee3828b9be96b8c2fd805473f63b439e1113266b8';
assert.equal(process.argv.length, 3, 'Usage: node tests/probes/zcode_native_contract.cjs /path/to/zcode.cjs');
const bytes = readFileSync(process.argv[2]);
const sha256 = createHash('sha256').update(bytes).digest('hex');
assert.equal(sha256, expectedSha256, 'Unreviewed bundle: inspect the new source before updating this probe');
const source = bytes.toString('utf8');
const evidence = [];

function locate(label, start, end) {
  const offset = source.indexOf(start);
  assert.ok(offset >= 0, `Missing ${label}`);
  assert.equal(source.indexOf(start, offset + start.length), -1, `Ambiguous ${label}`);
  const finish = end ? source.indexOf(end, offset + start.length) : offset + start.length;
  assert.ok(finish >= offset, `Missing end of ${label}`);
  evidence.push({
    label,
    byteOffset: Buffer.byteLength(source.slice(0, offset)),
    line: source.slice(0, offset).split('\n').length,
  });
  return source.slice(offset, finish);
}

function fn(name, next, async = false) {
  return locate(name, `${async ? 'async ' : ''}function ${name}(`, `function ${next}(`);
}

// Only these reviewed functions enter the VM. No require, process, filesystem,
// execution adapter, runtime constructor, or application initializer is exposed.
const outputFunctions = [fn('zNr', 'UNr'), fn('yft', 'Oni'), fn('Oni', 'Dni')];
const prevent = locate('FNr', 'function FNr(', 'var vft=');
const continuation = fn('R7r', 'Edi');
const runner = fn('R0i', 'P0i');
const configProjection = locate('$Ur config projection', 'function $Ur(', 'async function qUr(');
const cap = locate('Stop continuation cap', 'Idi=3,BAe=', 'Tdi=');
assert.ok(cap.startsWith('Idi=3,'));
const context = vm.createContext({}, { codeGeneration: { strings: false, wasm: false } });
vm.runInContext(`
  const on = Object.fromEntries(['Stop', 'PreToolUse', 'PermissionRequest',
    'PostToolUse', 'PostToolUseFailure', 'UserPromptSubmit', 'SessionStart']
    .map(name => [name, name]));
  const Idi = 3;
  ${outputFunctions.join('\n')}
  ${prevent}
  ${continuation}
  ${runner}
  ${configProjection}
`, context, { timeout: 1000 });

function evaluate(expression) {
  return JSON.parse(vm.runInContext(`JSON.stringify(${expression})`, context, { timeout: 1000 }));
}

for (const output of [
  { additionalContext: 'advice' },
  { additional_context: 'advice' },
  { hookSpecificOutput: { hookEventName: 'Stop', additionalContext: 'advice' } },
]) {
  const literal = JSON.stringify(output);
  assert.deepEqual(evaluate(`zNr('Stop', ${literal})`), { additionalContexts: ['advice'] });
  assert.equal(evaluate(`R7r(zNr('Stop', ${literal}), 0)`), false);
}
assert.deepEqual(evaluate("zNr('Stop', {systemMessage:'advice'})"), { additionalContexts: [] });
for (const output of [
  { continue: true, additionalContext: 'advice' },
  { decision: 'block', reason: 'quality finding' },
]) {
  const literal = JSON.stringify(output);
  assert.equal(evaluate(`R7r(zNr('Stop', ${literal}), 0)`), true);
  assert.equal(evaluate(`R7r(zNr('Stop', ${literal}), 2)`), true);
  assert.equal(evaluate(`R7r(zNr('Stop', ${literal}), 3)`), false);
}

// The caller matters: collecting advice does not establish consumption.
const stopConsumer = locate('normal Stop consumer',
  'if(this.shouldContinueAfterStopHooks(n,e.stopHookContinuationCount)){',
  'return e.activeTurn&&await this.fallbackPendingGuidesToQueue');
assert.ok(stopConsumer.includes('this.injectHookAdditionalContextIntoMessageHistory(on.Stop,n.additionalContexts)'));
assert.ok(stopConsumer.includes('"continue"'));
assert.equal(source.split('injectHookAdditionalContextIntoMessageHistory(on.Stop,').length - 1, 1);

// Inspect the actual constructor arguments, not a hypothetical child config.
const child = locate('default subagent constructor', 'let X=new Fh(t.sessionId,', ',q=t.resumeFromStore===!0;');
const argumentBoundary = child.indexOf('},{agentTelemetry:');
assert.ok(argumentBoundary > 0);
const childConfig = child.slice(0, argumentBoundary);
const childDependencies = child.slice(argumentBoundary);
assert.ok(childConfig.includes('taskType:"subagent_child"'));
assert.ok(childDependencies.includes('executionPort:e.executionPort'));
for (const key of ['hooks', 'hookRunner', 'workspaceHookSnapshot', 'workspaceHookAdmission', 'sessionMailboxPort']) {
  assert.doesNotMatch(child, new RegExp(`\\b${key}:`));
}
assert.ok(!childConfig.includes('...this.config'));
assert.ok(!childDependencies.includes('...e,'));
// No callbacks are mocked: this branch must return before requesting one.
assert.equal(evaluate("R0i({config:$Ur({taskType:'subagent_child',subagents:{enabled:false}})},{executionPort:{}},'child') === undefined"), true);

const initialize = locate('n$r context initialization', 'async function n$r(', 'async function o$r(');
assert.ok(initialize.includes('this.workingDirectory=r.workingDirectory,this.workspaceRoot=r.workingDirectory'));
const startup = locate('startup initialization ordering', 'await this.ensureContextInitialized(u),R("context_initialization",P)', 'R("session_start_hooks",P)');
assert.ok(startup.includes('this.runSessionStartHooks("startup",u,_)'));
const resume = locate('resume initialization ordering', 'this.workingDirectory=n.directory', 'this.runSessionStartHooks("resume",t,e?.abortSignal)');
assert.ok(resume.includes('this.contextInitialized=!1'));
assert.ok(resume.includes('await this.ensureContextInitialized(t)'));
const sessionStart = locate('T7r SessionStart', 'async function T7r(', 'async function C7r(');
assert.ok(sessionStart.includes('this.sessionStartHookRan||'));
assert.ok(sessionStart.includes('this.sessionStartHookRan=!0'));
assert.ok(sessionStart.includes('cwd:this.workingDirectory'));
assert.deepEqual([...source.matchAll(/\.runSessionStartHooks\("([^"]+)"/g)].map(match => match[1]).sort(), ['resume', 'startup']);
assert.equal(source.split('sessionStartHookRan=!1').length - 1, 1);

const bashSchema = locate('Bash strict input schema', 'gK=E.object({command:', ',_9e=tr(gK)');
assert.ok(bashSchema.endsWith('.strict()'));
assert.doesNotMatch(bashSchema, /\b(?:cwd|workdir|workingDirectory):/);
const bashRequest = fn('eQo', 'N3r');
assert.ok(bashRequest.includes('cwd:Yq(void 0,'));
assert.ok(bashRequest.includes('workingDirectory:t.workingDirectory'));
const cwdPolicy = fn('n4r', 'o4r');
assert.ok(cwdPolicy.includes('(e.runtimeScope??"main")!=="main"'));
const env = fn('hft', '$V');
assert.ok(env.includes('CLAUDE_PROJECT_DIR:t.cwd||r'));
assert.ok(env.includes('ZCODE_PROJECT_DIR:t.cwd||r'));
for (const [label, start, end] of [
  ['tool Pre payload', 'async function jCr(', 'async function FCr('],
  ['tool Post payload', 'async function zCr(', 'async function UCr('],
]) {
  const payload = locate(label, start, end);
  assert.ok(payload.includes('cwd:e.getWorkingDirectory()'));
  assert.ok(payload.includes('sessionId:e.sessionId'));
  assert.ok(payload.includes('toolCallId:t.id'));
  assert.doesNotMatch(payload, /\b(?:workspaceRoot|runtimeScope|parentSessionId):/);
}
locate('compatible stdin', 'async function fft(', 'function jNr(');
locate('Post context projection', 'function $Er(', 'function qEr(');

console.log(JSON.stringify({
  sha256,
  checks: 'passed',
  scope: 'Pinned bundle source assertions and extracted-function execution; no live Desktop event delivery',
  offsets: 'zero-based UTF-8 bytes; lines are one-based',
  evidence,
}, null, 2));
