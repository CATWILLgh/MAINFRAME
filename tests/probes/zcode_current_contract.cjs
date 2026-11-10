// Source-only probe. Never import or launch the bundled runtime.
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

assert.equal(process.argv.length, 4, 'Usage: node zcode_current_contract.cjs /path/to/zcode.cjs BUILD');
const [, , bundle, build] = process.argv;
const pins = new Map([
  ['3.17.1.9553', '9afd565a104d660259e6bdeeaa5cb8abc74a908559e21aa3c5f6a06f2a9da6c6'],
  ['3.17.2.9661', 'd9afd58d694f98a5279bf548cdc7646413c125762e86730605a6071f9e0346d6'],
]);
assert.ok(pins.has(build), `Unreviewed ZCode build ${build}: inspect the public contract before adding a pin`);
const bytes = readFileSync(bundle);
assert.equal(createHash('sha256').update(bytes).digest('hex'), pins.get(build),
  `Different bundle for ZCode ${build}: inspect the public contract before changing its pin`);
const source = bytes.toString('utf8');

function region(start, end, anchor = start) {
  const at = source.indexOf(anchor);
  assert.ok(at >= 0, `Missing source anchor: ${anchor}`);
  const from = source.lastIndexOf(start, at);
  const to = source.indexOf(end, at + anchor.length);
  assert.ok(from >= 0 && to > from, `Missing source anchors: ${start} … ${end}`);
  return source.slice(from, to);
}

function fn(name, end) {
  return region(`function ${name}(`, end);
}

function includes(section, fragments) {
  for (const fragment of fragments) assert.ok(section.includes(fragment), `Missing source anchor: ${fragment}`);
}

const old = build === '3.17.1.9553';
const events = region('Tc={SessionStart:', ',ZM=');
assert.doesNotMatch(events, /Subagent(?:Start|Stop)/);
const context = vm.createContext({}, { codeGeneration: { strings: false, wasm: false } });
const [parseOutput, shouldContinue, matches] = old ? ['bIn', '$Wo', 'WSo'] : ['wIn', 'tVo', 'ZSo'];
const pureFunctions = old
  ? `const f9a=3;
    ${fn('bIn', 'function SIn(')}
    ${fn('vIn', 'function F_a(')}
    ${fn('F_a', 'function j_a(')}
    ${fn('WSo', 'function vIn(')}
    ${fn('$Wo', 'function g9a(')}
    const qSo=e=>['PreToolUse','PermissionRequest','UserPromptSubmit'].includes(e);`
  : `const ${region('D9a=3', ',l1t=')};
    ${fn('wIn', 'function kIn(')}
    ${fn('ZSo', 'function $_a(')}
    ${fn('KSo', 'var xIn=')}
    ${fn('tVo', 'function N9a(')}`;
vm.runInContext(`const ${events};${pureFunctions}`, context, { timeout: 1000 });

function evaluate(code) {
  return JSON.parse(vm.runInContext(`JSON.stringify(${code})`, context, { timeout: 1000 }));
}

const deny = evaluate(`${parseOutput}('PreToolUse',{
  hookSpecificOutput:{hookEventName:'PreToolUse',permissionDecision:'deny',permissionDecisionReason:'bounded'}
})`);
assert.equal(deny.permissionBehavior, 'deny');
if (!old) assert.equal(deny.hookPermissionDecisionReason, 'bounded');
const post = evaluate(`${parseOutput}('PostToolUse',{
  hookSpecificOutput:{hookEventName:'PostToolUse',additionalContext:'fallow advice'}
})`);
assert.deepEqual(post.additionalContexts, ['fallow advice']);
assert.equal(evaluate(`${shouldContinue}(${parseOutput}('Stop',{additionalContext:'advice'}),0)`), false);
assert.equal(evaluate(`${shouldContinue}(${parseOutput}('Stop',{decision:'block',reason:'unresolved'}),2)`), true);
assert.equal(evaluate(`${shouldContinue}(${parseOutput}('Stop',{decision:'block',reason:'unresolved'}),3)`), false);
assert.equal(evaluate(`${shouldContinue}(${parseOutput}('Stop',{continue:false,systemMessage:'unresolved'}),0)`), false);
assert.equal(evaluate(`${matches}('Edit','Write|Edit')`), true);

const schema = old ? region('cat=', 'ANr=', 'subagent_type:') : region('lat=W.object(', 'LNr=as(lat)');
includes(schema, ['description:', 'prompt:', 'subagent_type:', 'run_in_background:']);
assert.doesNotMatch(schema, /\b(?:model|thoughtLevel|reasoningEffort):/);

const child = old
  ? region('new $D(', 'logger:this.logger', 'taskType:"subagent_child"')
  : region('let We=new $D(n.sessionId,', 'traceContext:n.traceContext});t.add(We)');
includes(child, ['taskType:"subagent_child"', 'executionPort:e.executionPort']);
assert.doesNotMatch(child, /\b(?:hooks|hookRunner|workspaceHookSnapshot|workspaceHookAdmission):/);
const childPorts = old ? fn('sTt', 'function B8a(') : fn('aTt', 'function W8a(');
assert.doesNotMatch(childPorts, /\b(?:hooks|hookRunner):/);

includes(source, [
  'originalFile:c', 'content:S', 'originalFile:e.originalFile', 'oldString:e.actualOldString',
  'newString:e.actualNewString', 'replaceAll:e.replaceAll', 't.tool_response=e.toolResponse',
  'hookAdditionalContexts:Et',
]);
if (old) {
  includes(source, ['await Lko(e,S,F,xt,']);
} else {
  // Follow the successful raw tool result through PostToolUse and model-context projection.
  includes(source, ['pt=aTt({permissionBroker:this.permissionBroker']);
  includes(child, ['...pt']);
  includes(region('kt=await txo(_.handler', 'let Pr=UTo('), [
    'await $ko(e,S,F,kt,', 'let Et=[...ne,...await hBe(e,Tc.PostToolUse,S,ge,k)]',
  ]);
  includes(fn('$ko', 'async function qko('), ['hookEventName:Tc.PostToolUse', 'toolResponse:o']);
}
console.log(`ZCode ${build} source-only hook, exact edit response, Stop cap, selection and child-boundary probes passed.`);
