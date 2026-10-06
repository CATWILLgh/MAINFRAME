#!/usr/bin/env node
'use strict';
// Inspect the shipped bundle and execute only its reviewed pure output parser.
// Never import the bundle, start the application, or contact a model.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {createHash} = require('node:crypto');
const vm = require('node:vm');
assert.equal(process.argv.length, 3);
const bytes = readFileSync(process.argv[2]);
assert.equal(createHash('sha256').update(bytes).digest('hex'),
  'fad4c35c4c36ec210d8a06d3fa0e77de23c8545e2eb6ff90aea1eb38d1e6275f',
  'Unreviewed ZCode build; inspect its source before changing this pin');
const source = bytes.toString('utf8');
function extract(name, next) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0);
  assert.equal(source.indexOf(`function ${name}(`, start + 1), -1);
  const end = source.indexOf(`function ${next}(`, start);
  assert.ok(end > start);
  return source.slice(start, end);
}
const context = vm.createContext({}, {codeGeneration: {strings: false, wasm: false}});
vm.runInContext(`const Tl = Object.fromEntries(['PreToolUse','PostToolUse',
  'PostToolUseFailure','Stop','SessionStart','PermissionRequest','UserPromptSubmit']
  .map(n => [n,n]));
  ${extract('Lio','Fio')}
  ${extract('A0n','_Qs')}
  ${extract('_Qs','yQs')}
  function Nio(e) { return ['PreToolUse','PermissionRequest','UserPromptSubmit'].includes(e); }
`, context, {timeout: 1000});
for (const event of ['PreToolUse','PostToolUse']) {
  const result = JSON.parse(vm.runInContext(`JSON.stringify(Lio('${event}',
    {hookSpecificOutput:{hookEventName:'${event}',additionalContext:'bounded advice'}}))`,
    context, {timeout:1000}));
  assert.deepEqual(result, {additionalContexts:['bounded advice']});
}
for (const exact of ['session_id:e.sessionId', 't.tool_use_id=e.toolCallId',
  't.tool_input=e.toolInput', 't.tool_response=e.toolResponse',
  'let z=await foo(e,b,L,_,E,w,s?.signal)',
  'let Xe=await hoo(e,b,L,st,Je.artifactPath,w,s?.signal)',
  'Je=kio(Je,[...z.additionalContexts,...Xe.additionalContexts],jt)']) {
  assert.ok(source.includes(exact), `Missing reviewed identity/context consumer: ${exact}`);
}
const childAt = source.indexOf('taskType:"subagent_child"');
assert.ok(childAt >= 0);
const child = source.slice(source.lastIndexOf('new ',childAt), source.indexOf('logger:this.log',childAt));
assert.ok(child.includes('executionPort:e.executionPort'));
assert.doesNotMatch(child, /\b(?:hooks|hookRunner|workspaceHookSnapshot|workspaceHookAdmission):/);
console.log('ZCode 3.14.4.7912: neutral Pre/Post context, operation aliases and primary-only scope verified from shipped code. Native conversation acceptance remains separate.');
