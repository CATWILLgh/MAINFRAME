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
  ['3.18.0.10300', '26785f28ab8fb9f8b0f3821f2bf71d294f4d0b8bf28108785292f86c7e14090d'],
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

async function verifyCurrentBuild() {
  const context = vm.createContext({}, { codeGeneration: { strings: false, wasm: false } });
  function run(code) {
    return vm.runInContext(code, context, { timeout: 1000 });
  }
  function evaluate(code) {
    return JSON.parse(run(`JSON.stringify(${code})`));
  }

  run(`
    const ${region('Ec={SessionStart:', ',RN=')};
    const JPn="Agent", eke="Task";
    const ${region('SRa=new Map([[JPn,', ';r(iW,')};
    const yrc=${region('yrc=3', ',ORt=').slice('yrc='.length)}, ORt={additionalContexts:[]};
    const Nr=(_, message)=>new Error(message), Wn={};
    ${region('function IPn(', 'var EPn=')}
    ${fn('dRo', 'function pRo(')}
    ${fn('I8e', 'var JPn,')}
    ${fn('nti', 'function rti(')}
    ${fn('xrc', 'function lti(')}
    ${fn('yP', 'function CEt(')}
    async ${fn('Jei', 'async function Kei(')}
  `);
  assert.deepEqual(evaluate('Object.keys(Ec)'), [
    'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PermissionRequest',
    'PostToolUse', 'PostToolUseFailure', 'Stop',
  ]);
  assert.deepEqual(evaluate('Object.values(Ec)'), evaluate('Object.keys(Ec)'));
  assert.equal(evaluate('uRo("Edit","Write|Edit")'), true);
  assert.equal(evaluate('uRo("MultiEdit","Write|Edit")'), false);
  assert.equal(evaluate('uRo("edit","Write|Edit")'), false);
  assert.equal(evaluate('uRo("fork","startup|resume|fork")'), true);
  assert.equal(evaluate('uRo("compact","startup|resume|fork")'), false);
  assert.equal(evaluate('dRo({matchValues:I8e("ApplyPatch")},"Write|Edit")'), true);
  assert.deepEqual(evaluate('I8e("Agent")'), ['Agent', 'Task']);
  assert.throws(() => run('IPn("PostToolUse",{hookSpecificOutput:{hookEventName:"PostToolUseFailure"}})'),
    /Hook returned wrong event name/);

  const deny = evaluate(`IPn('PreToolUse',{
    hookSpecificOutput:{hookEventName:'PreToolUse',permissionDecision:'deny',permissionDecisionReason:'bounded'}
  })`);
  assert.equal(deny.permissionBehavior, 'deny');
  assert.equal(deny.hookPermissionDecisionReason, 'bounded');
  for (const event of ['PostToolUse', 'PostToolUseFailure']) {
    assert.deepEqual(evaluate(`IPn("${event}",{
      hookSpecificOutput:{hookEventName:"${event}",additionalContext:"fallow advice"}
    })`), { additionalContexts: ['fallow advice'] });
  }
  assert.equal(evaluate('nti(IPn("Stop",{additionalContext:"advice"}),0)'), false);
  assert.equal(evaluate('nti(IPn("Stop",{continue:false,systemMessage:"advice"}),0)'), false);
  assert.equal(evaluate('nti(IPn("Stop",{continue:true}),0)'), false);
  assert.equal(evaluate('nti(IPn("Stop",{continue:true,additionalContext:"advice"}),2)'), true);
  assert.equal(evaluate('nti(IPn("Stop",{decision:"block",reason:"unresolved"}),2)'), true);
  assert.equal(evaluate('nti(IPn("Stop",{decision:"block",reason:"unresolved"}),3)'), false);
  const stopConsumer = region('let o=await this.runStopHooks(e.modelResponse', 'return e.activeTurn&&');
  includes(stopConsumer, [
    'if(this.shouldContinueAfterStopHooks(o,e.stopHookContinuationCount))',
    'e.stopHookContinuationCount+=1;let i=rIe(Ec.Stop,o.additionalContexts)',
    'await JC(this,e.turnRequestState,i?[i]:[],e.turnTraceContext)',
  ]);

  assert.equal(evaluate('xrc([{info:{role:"user",source:"fork"}}])'), 'fork');
  assert.equal(evaluate('xrc([{info:{role:"user",source:"fork"}},{info:{role:"user"}}])'), 'resume');
  includes(fn('uti', 'function dti('), [
    'await this.runSessionStartHooks(xrc(k),t,e?.abortSignal)', 'MRt(this,ke.additionalContexts)',
  ]);
  const sessionCalls = JSON.parse(await run(`(async()=>{
    const calls=[], runtime={
      config:{}, getMode:()=>"build", getSessionModelSelection:()=>null,
      workspaceHookAdmission:{activate:source=>calls.push(["admit",source])},
      hookRunner:{run:(input,options)=>calls.push([input.hookEventName,input.source,options.matchValue])}
    };
    for (const source of ["fork","resume","compact","compact"]) await Jei.call(runtime,source,{});
    return JSON.stringify(calls);
  })()`));
  assert.deepEqual(sessionCalls, [
    ['admit', 'fork'], ['SessionStart', 'fork', 'fork'],
    ['admit', 'compact'], ['SessionStart', 'compact', 'compact'],
    ['admit', 'compact'], ['SessionStart', 'compact', 'compact'],
  ]);
  includes(fn('Xei', 'function Qei('), [
    'runSessionStartHooks("compact",n,o,i)', 'c=rIe(Ec.SessionStart,a.additionalContexts)',
    '{entry:c,hasContext:!0}',
  ]);
  includes(fn('Zni', 'async function Xni('), [
    'await Xei(this,k,t,o.abortSignal,u)', '...Mn.entry?[Mn.entry]:[]',
  ]);

  const schema = region('Yut=H.object(', ',D8r=es(Yut)');
  assert.deepEqual([...schema.matchAll(/\b(\w+):H\./g)].map(match => match[1]), [
    'description', 'prompt', 'subagent_type', 'run_in_background',
  ]);
  const child = region('let qe=new hD(n.sessionId,', 'traceContext:n.traceContext});t.add(qe)');
  includes(child, ['taskType:"subagent_child"', 'executionPort:e.executionPort', '...Je', '...xe']);
  includes(region('xe=Jw({mode:ae', 'let qe=new hD(n.sessionId,'), [
    'Je=wEt({permissionBroker:this.permissionBroker', 'providerRuntimeHeadersPort:this.providerRuntimeHeadersPort',
  ]);
  includes(fn('Jw', 'var rfn,'), ['return{mode:', 'planEnabled:']);
  const hookPorts = /\b(?:hooks|hookRunner|workspaceHookSnapshot|workspaceHookAdmission):/;
  for (const section of [child, fn('wEt', 'function MKa('), fn('Jw', 'var rfn,')]) {
    assert.doesNotMatch(section, hookPorts);
  }

  // Follow tool input, the raw result, and advisory attachments across their native boundaries.
  const executor = fn('vDa', 'function bDa(');
  includes(executor, [
    'await tkt(e,S,L,_,O,k,i?.signal)',
    'if(q.permissionBehavior==="deny"||q.preventContinuation)',
    'a?.finishDenied("policy_denied"),$e}if(q.updatedInput',
    'St=await g2o(_.handler,L,ut,it,dt,_)',
    'await r2o(e,S,L,St,Mn.artifactPath,k,i?.signal)',
    'await $8e(e,Ec.PostToolUse,S,ge,k)',
    'hookAdditionalContexts:It',
    'await o2o(e,S,L,$e,k,i?.signal)',
    'Jkt(zt,[...ne??await V(),...await $8e(e,Ec.PostToolUseFailure,S,ut.additionalContexts,k)])',
  ]);
  includes(fn('tkt', 'async function n2o('), ['hookEventName:Ec.PreToolUse', 'toolInput:n', 'matchValues:I8e(t.name)']);
  includes(fn('r2o', 'async function o2o('), ['hookEventName:Ec.PostToolUse', 'toolResponse:o']);
  includes(fn('o2o', 'function i2o('), ['hookEventName:Ec.PostToolUseFailure', 'error:{message:c.message']);
  includes(fn('Jkt', 'var yDa,'), ['hookAdditionalContexts:[...t]']);
  includes(fn('zEt', 'function CX('), ['a.hookAdditionalContexts??[]', 'Md("tool_hook_context",c)']);
  includes(fn('SPn', 'function cRo('), [
    'case Ec.PostToolUse:t.tool_response=e.toolResponse',
    'case Ec.PostToolUseFailure:t.error_details=e.error,t.error=e.error.message',
  ]);
  const writeHandler = region('q4a=r(async', ',"writeHandler")');
  includes(writeHandler, [
    'type:"update",filePath:n,content:S,structuredPatch:', 'originalFile:c',
    'type:"create",filePath:n,content:S,structuredPatch:[],originalFile:null',
  ]);
  const editResult = fn('fMn', 'function Rja(');
  includes(editResult, [
    'pkt({filePath:e.inputFilePath,oldContent:e.originalFile,newContent:n})',
    'return nz({filePath:e.inputFilePath,oldString:e.actualOldString,newString:e.actualNewString,originalFile:e.originalFile,structuredPatch:u,userModified:!1,replaceAll:e.replaceAll',
  ]);
  assert.doesNotMatch(region('return nz({filePath:e.inputFilePath', '},{detail:'), /\bcontent:/);
  const editHandler = region('wja=r(async(e,t)=>', ',"editHandler")');
  includes(editHandler, [
    'if(!d)return o===""?fMn({context:t,filePath:u,inputFilePath:n,originalFile:"",actualOldString:"",actualNewString:i,newContent:i',
    'S=sTt(_.content),k=sTt(o),x=sTt(i);if(o===""){if(S.trim()!=="")return f6(ON.FILE_EXISTS_NO_OLD_STRING',
    'originalFile:S,actualOldString:"",actualNewString:x,newContent:x',
  ]);
}

if (build === '3.18.0.10300') {
  verifyCurrentBuild().then(reportSuccess, error => {
    console.error(error);
    process.exitCode = 1;
  });
} else {
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
  reportSuccess();
}

function reportSuccess() {
  console.log(`ZCode ${build} source-only hook, exact edit response, Stop cap, selection and child-boundary probes passed.`);
}
