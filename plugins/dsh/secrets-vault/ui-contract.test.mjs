import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const text = name => readFile(new URL(name, import.meta.url), 'utf8');
test('catalog has native display metadata and a self-colored icon', async () => {
  const pkg=JSON.parse(await text('package.json'));
  assert.equal(pkg.version,'2.0.7');
  assert.deepEqual(pkg.engines,{dsh:'0.2.2-rc.1'});
  assert.equal(pkg.exports['./icon'],'./icon.svg');
  assert.ok(pkg.exports['./locale/*.json']);
  for (const lang of ['en','ru']) {
    const locale=JSON.parse(await text(`locale/${lang}.json`));
    assert.equal(locale.meta.title,lang==='ru'?'Хранилище секретов':'Secrets Vault');
    assert.ok(locale.meta.description.length>20);
  }
  const svg=await text('icon.svg');
  assert.match(svg,/viewBox="0 0 64 64"/);
  assert.doesNotMatch(svg,/currentColor|<script|href=/i);
});
test('dynamic UI preserves supported imports and keyboard modal contract',async()=>{
  const source=await text('client.template.js');
  assert.doesNotMatch(source,/require\(['"]@deepseek-ai\//);
  assert.match(source,/aria-modal/);
  assert.match(source,/Escape/);
  assert.match(source,/shiftKey/);
  assert.match(source,/previous/);
  assert.match(source,/shell\.overlay/);
  assert.match(source,/commandUi\.register/);
});
test('modal backdrop is translucent without fading the dialog',async()=>{
  const source=await text('client.template.js');
  const css=source.match(/const css = `([\s\S]*?)`;/)[1];
  const backdrop=css.match(/\.sv-overlay\{([^}]+)\}/)[1];
  const dialog=css.match(/\.sv-dialog\{([^}]+)\}/)[1];
  assert.ok(backdrop.includes('background:color-mix(in srgb,var(--dsw-alias-bg-overlay) 40%,transparent)'));
  assert.doesNotMatch(backdrop,/(?:^|;)opacity:/);
  assert.ok(dialog.includes('background:var(--dsw-alias-bg-layer-1)'));
  assert.doesNotMatch(dialog,/(?:^|;)opacity:/);
});
test('management page uses the complete native Plugins layout contract',async()=>{
  const source=await text('client.template.js');
  const css=source.match(/const css = `([\s\S]*?)`;/)[1];
  const rule=selector=>css.match(new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\{([^}]+)\\}'))?.[1];
  const page=rule('.sv-page');
  for(const declaration of ['display:flex','flex-direction:column','align-items:center','gap:32px','padding:0 clamp(24px,4vw,48px) 48px','overflow:auto'])assert.ok(page.includes(declaration),declaration);
  assert.match(css,/\.sv-page>\.sv-head,\.sv-page>\.sv-content\{width:100%;max-width:960px;flex:none\}/);
  assert.ok(rule('.sv-head').includes('align-items:flex-start'));
  assert.doesNotMatch(rule('.sv-head'),/margin-bottom/);
  assert.doesNotMatch(source,/sv-status|scrollbar-gutter:stable|box-sizing:content-box/);
  assert.match(source,/className:'sv-button sv-icon sv-refresh'/);
  assert.match(source,/'aria-busy':s.pending/);
  assert.match(source,/t\(s.initialized\?'lockedHelp':'setupIntro'\)/);
  assert.doesNotMatch(source,/require\(['"]@deepseek-ai\//);
  for(const color of css.matchAll(/#[\da-f]{3,8}\b|\brgba?\(/gi))assert.fail(`Hard-coded UI color: ${color[0]}`);
});
