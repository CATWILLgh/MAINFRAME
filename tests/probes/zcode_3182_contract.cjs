// Called only after zcode_current_contract.cjs verifies the complete runtime hash.
// Execute audited functions/classes with synthetic data; never initialize the app.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const nodePath = require('node:path');

module.exports = async function verify3182({ source, region, fn, includes }) {
  const context = vm.createContext({ nodePath, Buffer }, { codeGeneration: { strings: false, wasm: false } });
  const run = code => vm.runInContext(code, context, { timeout: 1000 });
  const value = code => JSON.parse(run(`JSON.stringify(${code})`));
  const asyncValue = async code => JSON.parse(await run(`(async()=>JSON.stringify(await (${code})))()`));
  run(`
    const r=value=>value, Nr=(_,message)=>new Error(message), Wn={};
    const ${region('Ec={SessionStart:', ',ON=')};
    const l2n="Agent", rke="Task", ${region('wPa=new Map([[l2n,', ';r(sW,')};
    const ${region('voc=3', ',boc=')};
    ${fn('zPn', 'function $Pn(')}
    ${region('function HRo(', 'var qPn=')}
    ${fn('GRo', 'function JRo(')}
    ${fn('E8e', 'var l2n,')}
    ${fn('jti', 'function Bti(')}
    ${fn('bP', 'function DEt(')}
    ${fn('Toc', 'function Vti(')}
    async ${fn('Rti', 'async function Pti(')}
  `);
  assert.deepEqual(value('Object.keys(Ec)'), [
    'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PermissionRequest',
    'PostToolUse', 'PostToolUseFailure', 'Stop',
  ]);
  assert.equal(value('HRo("Edit","Write|Edit")'), true);
  assert.equal(value('HRo("MultiEdit","Write|Edit")'), false);
  assert.equal(value('GRo({matchValues:E8e("ApplyPatch")},"Write|Edit")'), true);
  assert.deepEqual(value('E8e("Agent")'), ['Agent', 'Task']);
  assert.throws(() => run('zPn("PostToolUse",{hookSpecificOutput:{hookEventName:"PostToolUseFailure"}})'), /wrong event name/);
  const denied = value('zPn("PreToolUse",{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"bounded"}})');
  assert.equal(denied.permissionBehavior, 'deny');
  assert.equal(denied.hookPermissionDecisionReason, 'bounded');
  for (const event of ['PostToolUse', 'PostToolUseFailure']) {
    assert.deepEqual(value(`zPn("${event}",{hookSpecificOutput:{hookEventName:"${event}",additionalContext:"fallow advice"}})`),
      { additionalContexts: ['fallow advice'] });
  }
  assert.equal(value('jti(zPn("Stop",{additionalContext:"advice"}),0)'), false);
  assert.equal(value('jti(zPn("Stop",{continue:false,systemMessage:"advice"}),0)'), false);
  assert.equal(value('jti(zPn("Stop",{continue:true}),0)'), false);
  assert.equal(value('jti(zPn("Stop",{decision:"block",reason:"unresolved"}),2)'), true);
  assert.equal(value('jti(zPn("Stop",{decision:"block",reason:"unresolved"}),3)'), false);
  assert.equal(value('Toc([{info:{role:"user",source:"fork"}}])'), 'fork');
  assert.equal(value('Toc([{info:{role:"user",source:"fork"}},{info:{role:"user"}}])'), 'resume');
  const calls = await asyncValue(`(async()=>{
    const calls=[], runtime={config:{},workingDirectory:"/fixture/project",getMode:()=>"build",
      getSessionModelSelection:()=>null, workspaceHookAdmission:{activate:source=>calls.push(["admit",source])},
      hookRunner:{run:(input,options)=>calls.push([input.hookEventName,input.source,input.cwd,options.matchValue])}};
    for(const source of ["fork","resume","compact","compact"]) await Rti.call(runtime,source,{});
    return calls;
  })()`);
  assert.deepEqual(calls, [
    ['admit', 'fork'], ['SessionStart', 'fork', '/fixture/project', 'fork'],
    ['admit', 'compact'], ['SessionStart', 'compact', '/fixture/project', 'compact'],
    ['admit', 'compact'], ['SessionStart', 'compact', '/fixture/project', 'compact'],
  ]);

  // Registration filtering is native; the callback factory is inert in this VM.
  run(`
    const configured=[], XRo=(_options,_event,hook)=>{configured.push(hook.command);return()=>undefined;};
    const tke=class{constructor(options){this.hooks=options.hooks;}};
    ${fn('bBe', 'function dCn(')}
    ${fn('dCn', 'function V_t(')}
    ${fn('WRo', 'function FPn(')}
    ${region('function xwt(', 'var tPo=')}
  `);
  assert.equal(value('xwt({config:{enabled:false,events:{},maxOutputBytes:1000}})??null'), null);
  assert.equal(value(`xwt({config:{enabled:true,timeoutMs:5000,maxOutputBytes:1000,
    events:{PreToolUse:[{matcher:"Bash",hooks:[{type:"process",command:"disabled",enabled:false},
      {type:"process",command:"allowed",timeoutMs:2000}]}]}}}).hooks.length`), 1);
  assert.deepEqual(value('configured'), ['allowed']);

  // Bash uses the current pre-tool cwd and updates it only after its cwd policy.
  run(`
    const Kwe={...nodePath,default:nodePath}, FRo={platform:"linux"}, g4o={platform:"linux"};
    const h4o={realpathSync:{native:()=>{throw new Error("synthetic path");}}};
    ${region('function jRo(', 'var Kwe,')}
    ${region('function _4o(', 'var h4o,')}
  `);
  assert.deepEqual(value('_4o({status:"completed",exitCode:0,resolvedCwd:"/fixture/project/sub",workspaceRoot:"/fixture/project",platform:"linux"})'),
    { nextWorkingDirectory: '/fixture/project/sub' });
  assert.equal(value('_4o({status:"completed",exitCode:0,resolvedCwd:"/outside",workspaceRoot:"/fixture/project",platform:"linux"}).nextWorkingDirectory'), '/fixture/project');
  includes(fn('w8a', 'function H6o('), ['cwd:_ke(void 0,{operation:"execute",workingDirectory:t.workingDirectory,workspaceRoot:t.workspaceRoot})', 'captureCwdAfterSuccess:e.run_in_background?void 0:!0']);
  includes(fn('W6o', 'function f8a('), ['let o=HFe.parse(e),i=t.executionPort', 'C.nextWorkingDirectory&&await t.setWorkingDirectory?.(C.nextWorkingDirectory)']);
  includes(fn('akt', 'async function j2o('), ['cwd:e.getWorkingDirectory()', 'hookEventName:Ec.PreToolUse', 'toolInput:n']);
  includes(fn('B2o', 'async function U2o('), ['cwd:e.getWorkingDirectory()', 'hookEventName:Ec.PostToolUse', 'toolResponse:o']);
  includes(fn('U2o', 'function z2o('), ['hookEventName:Ec.PostToolUseFailure', 'error:{message:c.message']);
  includes(fn('XRo', 'function ZRo('), ['case"process":', 'command:{mode:"argv",file:', 'cwd:c.cwd||e.getWorkingDirectory()', 'timeoutMs:a.timeoutMs', 'e.executionPort.run']);
  includes(fn('yac', 'function vac('), ['executionPort:t.executionPort', 'getWorkingDirectory:r(()=>e.workingDirectory']);
  includes(fn('LPn', 'function WRo('), ['t.tool_name=e.toolName,t.tool_input=e.toolInput,t.tool_use_id=e.toolCallId', 'case Ec.PostToolUse:t.tool_response=e.toolResponse', 'case Ec.PostToolUseFailure:t.error_details=e.error,t.error=e.error.message']);
  const executor = fn('bMa', 'function SMa(');
  includes(executor, ['await akt(e,S,L,_,O,k,i?.signal)', 'if(q.permissionBehavior==="deny"||q.preventContinuation)',
    'a?.finishDenied("policy_denied"),$e}if(q.updatedInput', 'St=await X2o(_.handler,L,ut,it,dt,_)',
    'await B2o(e,S,L,St,Mn.artifactPath,k,i?.signal)', 'hookAdditionalContexts:It', 'await U2o(e,S,L,$e,k,i?.signal)',
    'await W8e(e,Ec.PostToolUseFailure,S,ut.additionalContexts,k)']);
  assert.ok(executor.indexOf('St=await X2o(') < executor.indexOf('await B2o('));
  includes(fn('GEt', 'function EX('), ['a.hookAdditionalContexts??[]', 'Md("tool_hook_context",c)']);
  includes(region('Wja=r(async', ',"writeHandler")'), ['type:"update",filePath:n,content:S,structuredPatch:', 'originalFile:c', 'type:"create",filePath:n,content:S,structuredPatch:[],originalFile:null']);
  includes(fn('EMn', 'function P6a('), ['filePath:e.inputFilePath,oldString:e.actualOldString,newString:e.actualNewString,originalFile:e.originalFile', 'replaceAll:e.replaceAll']);
  assert.doesNotMatch(region('return oz({filePath:e.inputFilePath', '},{detail:'), /\bcontent:/);
  includes(region('k6a=r(async', ',"editHandler")'), ['originalFile:"",actualOldString:"",actualNewString:i,newContent:i', 'originalFile:S,actualOldString:"",actualNewString:x,newContent:x']);
  includes(fn('Hti', 'async function Ioc('), ['await this.runSessionStartHooks(Toc(k),t,e?.abortSignal)', 'URt(this,ke.additionalContexts)']);
  includes(fn('Mti', 'function Nti('), ['runSessionStartHooks("compact",n,o,i)', 'c=sIe(Ec.SessionStart,a.additionalContexts)', '{entry:c,hasContext:!0}']);
  includes(region('let o=await this.runStopHooks(e.modelResponse', 'return e.activeTurn&&'), ['if(this.shouldContinueAfterStopHooks(o,e.stopHookContinuationCount))', 'e.stopHookContinuationCount+=1;let i=sIe(Ec.Stop,o.additionalContexts)', 'await JC(this,e.turnRequestState,i?[i]:[],e.turnTraceContext)']);
  const schema = region('ndt=H.object(', ',uUr=es(ndt)');
  assert.deepEqual([...schema.matchAll(/\b(\w+):H\./g)].map(match => match[1]), ['description', 'prompt', 'subagent_type', 'run_in_background']);
  const child = region('let qe=new _D(n.sessionId,', 'traceContext:n.traceContext});t.add(qe)');
  includes(child, ['taskType:"subagent_child"', 'executionPort:e.executionPort', '...Je', '...xe']);
  for (const section of [child, fn('EEt', 'function NZa('), fn('Yw', 'var hfn,')]) {
    assert.doesNotMatch(section, /\b(?:hooks|hookRunner|workspaceHookSnapshot|workspaceHookAdmission):/);
  }
  await discovery(context, run, value, asyncValue, { source, region, fn, includes });
};

async function discovery(context, run, value, asyncValue, { source, region, fn, includes }) {
  run(`
    const fixtureFiles=new Map([
      ["/fixture/home/.zcode/AGENTS.md","synthetic user instructions"],
      ["/fixture/project/AGENTS.md","synthetic workspace instructions"],
      ["/fixture/home/.zcode/skills/mainframe-synthetic/SKILL.md","---\\nname: mainframe-synthetic\\ndescription: Synthetic method\\n---\\nExact synthetic skill body".replaceAll("\\\\n","\\n")],
      ["/fixture/home/.zcode/commands/mainframe-synthetic.md","---\\ndescription: Synthetic workflow\\nargument-hint: task\\n---\\nExact synthetic command body".replaceAll("\\\\n","\\n")]
    ]);
    const fixtureDirs=new Set(["/fixture/project","/fixture/project/.git","/fixture/home/.zcode/skills",
      "/fixture/home/.zcode/skills/mainframe-synthetic","/fixture/home/.zcode/commands"]);
    const missing=path=>Object.assign(new Error("Synthetic path missing"),{code:"ENOENT",path});
    const stat=async path=>{if(!fixtureFiles.has(path)&&!fixtureDirs.has(path))throw missing(path);
      return {size:fixtureFiles.has(path)?Buffer.byteLength(fixtureFiles.get(path)):0,
        isFile:()=>fixtureFiles.has(path),isDirectory:()=>fixtureDirs.has(path),isSymbolicLink:()=>false};};
    const fixtureFs={stat,lstat:stat,realpath:async path=>{await stat(path);return path;},
      readFile:async(path,encoding)=>{if(!fixtureFiles.has(path))throw missing(path);return encoding?fixtureFiles.get(path):Buffer.from(fixtureFiles.get(path));},
      readdir:async path=>{await stat(path);const prefix=path+"/",names=new Set([...fixtureFiles.keys(),...fixtureDirs].filter(p=>p.startsWith(prefix)).map(p=>p.slice(prefix.length).split("/")[0]).filter(Boolean));
        return [...names].map(name=>({name,isFile:()=>fixtureFiles.has(prefix+name),isDirectory:()=>fixtureDirs.has(prefix+name),isSymbolicLink:()=>false}));}};
    const jbo=fixtureFs,CCn={homedir:()=>"/fixture/home"},xx=nodePath,w0a=".git",Lbo="~/",k0a=10,Fbo="skills",x0a=".zcode",T0a=".agents";
    ${region('async function Bbo(', 'var jbo,')}
    const Gbo=fixtureFs,Jbo=CCn,Tx=nodePath,Vbo="commands",J0a=".git",Hbo="~/",K0a=10,Z0a=".zcode",Y0a=".agents";
    ${region('async function Kbo(', 'var Gbo,')}
    const qSe=fixtureFs,ECn=nodePath,elt="SKILL.md",XNr=new Set(["node_modules","dist","build","out","target","vendor","coverage",".cache",".next",".turbo",".venv","__pycache__"]),pPs=new Set([".system"]);
    ${fn('dfn', 'var elt,')}
    ${region('async function jZ(', 'var qSe,')}
    const Wbo={realpathSync:path=>path},jU=fixtureFs,WE=nodePath,P0a=1024,O0a=new Set(["name","description","when_to_use","license","metadata"]),D0a=1e5,M0a=5,N0a=[];
    ${region('function BZ(', 'var Wbo,')}
    const ${region('RCn=class{', ';r(BZ,')};
    const Kj=fixtureFs,j9=nodePath,eSo=".md",n_a=/^[a-z0-9][a-z0-9_:-]{0,63}$/,r_a=1e5,tSo=1024,o_a=12,i_a=new Set(["allowed-tools","argument-hint","description","disable-noninteractive","model","skills"]);
    ${region('function nSo(', 'var Kj,')}
    const ${region('MCn=class{', ';r(nSo,')};
    const xse=fixtureFs,Kye=CCn,ey=nodePath,F3s=["AGENTS.md"],j3s=100*1024,J3s=new Set(["ENOENT","EISDIR","ENOTDIR"]);
    async ${region('function B3s(', 'async function G3s(')}
    ${fn('nVr', 'async function rVr(')}
    async ${fn('rVr', 'async function V8(')}
  `);
  const roots = await asyncValue('Bbo("/fixture/project",{homeDirectory:"/fixture/home"})');
  assert.deepEqual(roots.map(root => root.path), ['/fixture/home/.zcode/skills', '/fixture/home/.agents/skills', '/fixture/project/.zcode/skills', '/fixture/project/.agents/skills']);
  const commands = await asyncValue('Kbo("/fixture/project",{homeDirectory:"/fixture/home"})');
  assert.equal(commands[0].path, '/fixture/home/.zcode/commands');
  assert.equal(commands[1].path, '/fixture/home/.agents/commands');
  const instructions = await asyncValue('B3s({workingDirectory:"/fixture/project",projectRoot:"/fixture/project",priorityFiles:["AGENTS.md"]},[],{HOME:"/fixture/home"})');
  assert.equal(instructions.content, 'synthetic user instructions\n\nsynthetic workspace instructions');
  const skill = await asyncValue('BZ({homeDirectory:"/fixture/home"}).loadSkill({workingDirectory:"/fixture/project",name:"mainframe-synthetic"})');
  assert.equal(skill.content, 'Exact synthetic skill body');
  assert.equal(skill.metadata.description, 'Synthetic method');
  assert.deepEqual((await asyncValue('BZ({homeDirectory:"/fixture/home",disabledPaths:["/fixture/home/.zcode/skills/mainframe-synthetic/SKILL.md"]}).discoverSkills({workingDirectory:"/fixture/project"})')).skills, []);
  const command = await asyncValue('nSo({homeDirectory:"/fixture/home"}).loadCommand({workingDirectory:"/fixture/project",name:"mainframe-synthetic"})');
  assert.equal(command.content, 'Exact synthetic command body');
  assert.equal(command.metadata.argumentHint, 'task');
  assert.deepEqual((await asyncValue('nSo({homeDirectory:"/fixture/home",disabledPaths:["/fixture/home/.zcode/commands/mainframe-synthetic.md"]}).discoverCommands({workingDirectory:"/fixture/project"})')).commands, []);
  includes(source, ['(0,nk.join)(t,".zcode","cli","config.json")']);
  includes(fn('rCi', 'function oCi('), ['(0,ID.join)(e.storageRoot,"agents")', 'source:"user"', '(0,ID.join)(e.workingDirectory,".zcode","agents")']);
  run(`
    const B0s=new Set(["inherit","main","sonnet","opus","haiku"]),XMe="custom:";
    ${fn('kot', 'function Yon(')}
    ${fn('eq', 'var XMe,')}
    ${fn('woe', 'function jwr(')}
    ${region('function sLr(', 'var dLr=')}
    const _Ps=new Set(["red","blue","green","yellow","purple","orange","pink","cyan"]),yPs=new Set(["acceptEdits","auto","bypassPermissions","default","dontAsk","plan"]),vPs=new Set(["user","project","local"]);
    ${region('function yie(', 'var _Ps,')}
    const LN="LocalToolSearch",mx="ToolSearch";
    ${region('function rUe(', 'var Ake=')}
  `);
  const profile = value(`yie({source:"user",content:"---\\nname: synthetic-reader\\ndescription: Synthetic role\\nmodel: custom:fixture-provider:fixture-model\\nthoughtLevel: high\\ncolor: blue\\ninjectAgentsMd: false\\ndisallowedTools:\\n  - Edit\\n  - Write\\n---\\nUse the required skill".replaceAll("\\\\n","\\n")}).profile`);
  assert.equal(profile.systemPrompt, 'Use the required skill');
  assert.deepEqual(profile.modelSelection, { providerId: 'fixture-provider', modelId: 'fixture-model', options: { reasoningLevel: 'high' } });
  assert.equal(profile.color, 'blue');
  assert.equal(profile.injectAgentsMd, false);
  assert.deepEqual(profile.disallowedTools, ['Edit', 'Write']);
  assert.deepEqual(value('hDo(["Read","Edit","Write","Skill"],["Edit","Write"])'), ['Read', 'Skill']);
  includes(fn('brc', 'function Src('), ['...e.disallowedTools??[]', 'zle(e.allowedTools,n)']);
};
