import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const root = new URL('../', import.meta.url);
const source = await readFile(new URL('client.js', root), 'utf8');
const locales = Object.fromEntries(await Promise.all(['en', 'ru'].map(async language =>
  [language, JSON.parse(await readFile(new URL(`locale/${language}.json`, root), 'utf8'))])));

// A deliberately small hook/element harness: exercises callbacks and state, not
// DOM layout or React reconciliation. No Harness runtime or real history used.
function harness(fetchImpl = async () => ({ ok: true, json: async () => ({ ok: true, sessionId: 'copy', workspaceId: 'target' }) })) {
  const hooks = [];
  let cursor = 0;
  const React = {
    Fragment: 'Fragment',
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; },
    useState(initial) {
      const index = cursor++;
      if (!(index in hooks)) hooks[index] = initial;
      return [hooks[index], value => { hooks[index] = typeof value === 'function' ? value(hooks[index]) : value; }];
    },
    useRef(initial) {
      const index = cursor++;
      if (!(index in hooks)) hooks[index] = { current: initial };
      return hooks[index];
    },
    useEffect(effect) {
      const index = cursor++;
      if (!(index in hooks)) hooks[index] = effect();
    },
    useCallback(callback) { return callback; },
    useSyncExternalStore(_subscribe, getSnapshot) { return getSnapshot(); },
    useId() { return 'test-destination'; },
  };
  const primitives = { Modal: 'Modal', Button: 'Button', IconRightUpOutlineRegular: 'IconRightUpOutlineRegular' };
  let plugin, dictionaries;
  const requests = [], navigations = [], registrations = [], effects = [], imports = [], menus = [];
  const translate = (key, values = {}) => dictionaries.en[key].replace(/\{(\w+)\}/g, (_, name) => values[name] ?? `{${name}}`);
  const snapshot = { state: 'idle', phase: 'ready', items: [
    { workspaceId: 'source', title: 'Original', path: '/source', sessionIds: ['source-session'] },
    { workspaceId: 'target', title: 'Target', path: '/target', sessionIds: [] },
  ] };
  vm.runInNewContext(source, {
    fetch: async (...args) => { requests.push(args); return fetchImpl(...args); },
    window: { __ModuleLoader__: { load(entry) {
      assert.equal(entry.id, '@mainframe/dsh-workspace-transfer-safe');
      plugin = entry.factory(name => {
        imports.push(name);
        if (name === 'react') return React;
        if (name === '@deepseek-ai/dsh-client-ui-primitives') return primitives;
        throw new Error(`Unexpected import ${name}`);
      });
    } } },
  });
  plugin.apply({
    effect(callback) { effects.push(callback()); },
    locale: { register(_namespace, value) { dictionaries = value; return () => {}; }, bind: () => translate },
    contextMenus: { register(value) { menus.push(value); return () => {}; } },
    slots: {
      inject(name, callback) { callback(); },
      register(registration, Component) { registrations.push({ registration, Component }); return () => {}; },
    },
    workspaces: { list: { getSnapshot: () => snapshot, subscribe: () => () => {} } },
    uiWorkspace: { openSession(id) { navigations.push(id); } },
  });
  const menu = menus[0];
  const overlay = registrations.find(entry => entry.registration.name === 'shell.overlay');
  const injected = overlay.registration.inject();
  const t = (key, values = {}) => dictionaries.en[key].replace(/\{(\w+)\}/g, (_, name) => values[name] ?? `{${name}}`);
  let form;
  function open() {
    menu.resolve({ sessionId: 'source-session', displayTitle: 'Original conversation' })[0].run();
    form = overlay.Component({ ...injected, t });
    return render();
  }
  function render() {
    cursor = 0;
    return form.type(form.props);
  }
  return { plugin, dictionaries, imports, registrations, requests, navigations, snapshot,
    transfer: injected.transfer, menu, injected, open, render, t };
}

function elements(tree) {
  if (Array.isArray(tree)) return tree.flatMap(elements);
  if (!tree || typeof tree !== 'object' || !tree.props) return [];
  return [tree, ...elements(tree.props.children), ...elements(tree.props.footer)];
}
const primary = tree => elements(tree).find(node => node.type === 'Button' && node.props.variant === 'primary');
const alertText = tree => elements(tree).find(node => node.props.role === 'alert')?.props.children.join('');
function prepare(h) {
  let tree = h.open();
  assert.equal(primary(tree).props.disabled, true);
  const select = elements(tree).find(node => node.type === 'select');
  assert.deepEqual(elements(select).filter(node => node.type === 'option').map(node => node.props.value), ['', 'target']);
  select.props.onChange({ target: { value: 'target' } });
  tree = h.render();
  assert.equal(elements(tree).some(node => node.type === 'input' && node.props.type === 'checkbox'), false);
  assert.equal(primary(tree).props.disabled, false);
  return tree;
}

const serverError = (code, copySessionId) => async () => ({ ok: true, json: async () => ({
  ok: false, error: { code, message: 'Sanitized server explanation', ...(copySessionId ? { copySessionId } : {}) },
}) });

test('client imports, service dependencies, slots and localized resources stay in sync', () => {
  const h = harness();
  assert.deepEqual(h.imports, ['react', '@deepseek-ai/dsh-client-ui-primitives']);
  assert.deepEqual(Array.from(h.plugin.inject), ['slots', 'locale', 'workspaces', 'uiWorkspace', 'contextMenus']);
  assert.equal(h.registrations.length, 2);
  for (const language of ['en', 'ru']) {
    const { meta, ...messages } = locales[language];
    assert.ok(meta.title && meta.description);
    assert.deepEqual(JSON.parse(JSON.stringify(h.dictionaries[language])), messages);
  }
});

test('native menu action uses the shared icon column, no extra divider, and captured target', () => {
  const h = harness();
  assert.equal(h.menu.target, 'session');
  assert.equal(h.menu.order, 550);
  const actions = h.menu.resolve({ sessionId: 'captured', displayTitle: 'Captured conversation' });
  assert.equal(actions.length, 1);
  const [action] = actions;
  assert.equal(action.label, h.t('action'));
  assert.equal(action.separatorBefore, undefined);
  const icon = h.registrations.find(entry => entry.registration.name === 'contextMenu.icon');
  assert.equal(action.icon.key, icon.registration.key);
  assert.equal(icon.Component().type, 'IconRightUpOutlineRegular');
  assert.ok(!h.registrations.some(entry => entry.registration.name === 'sidebar.workspaces.session.menu.item'));
  action.run();
  assert.equal(h.injected.source.getSnapshot().sessionId, 'captured');
  assert.equal(h.injected.source.getSnapshot().displayTitle, 'Captured conversation');
  h.menu.resolve({ sessionId: 'other' })[0].run();
  assert.equal(h.injected.source.getSnapshot().sessionId, 'captured');
  assert.equal(h.requests.length, 0);
});

test('uses authenticated same-origin API endpoint and exact minimal request body', async () => {
  const h = harness();
  const result = await h.transfer('source-session', 'target');
  assert.equal(result.sessionId, 'copy');
  const [url, request] = h.requests[0];
  assert.equal(url, '/api/mainframe/workspace-transfer');
  assert.equal(request.method, 'POST');
  assert.equal(request.credentials, 'same-origin');
  assert.equal(request.redirect, 'error');
  assert.equal(request.headers['Content-Type'], 'application/json');
  assert.equal(request.headers['x-mainframe-workspace-transfer'], '1');
  assert.deepEqual(JSON.parse(request.body), { sessionId: 'source-session', workspaceId: 'target' });
});

test('confirmation requires destination without a hidden checkbox gate, then navigates only to new ID', async () => {
  const h = harness();
  const tree = prepare(h);
  assert.equal(h.requests.length, 0);
  await primary(tree).props.onClick();
  assert.equal(h.requests.length, 1);
  assert.deepEqual(h.navigations, ['copy']);
  assert.equal(h.injected.source.getSnapshot(), null);
});

test('double submit and close are blocked while request is pending', async () => {
  let resolve;
  const h = harness(() => new Promise(done => { resolve = done; }));
  const click = primary(prepare(h)).props.onClick;
  const pending = click();
  await click();
  h.render().props.onClose();
  assert.equal(h.requests.length, 1);
  assert.notEqual(h.injected.source.getSnapshot(), null);
  assert.equal(primary(h.render()).props.disabled, true);
  resolve({ ok: true, json: async () => ({ ok: true, sessionId: 'copy', workspaceId: 'target' }) });
  await pending;
});

test('source-open error stays localized and permits a deliberate retry after closing source', async () => {
  const h = harness(serverError('source-open'));
  await primary(prepare(h)).props.onClick();
  const tree = h.render();
  assert.equal(alertText(tree), h.t('sourceOpen'));
  assert.ok(primary(tree));
  assert.equal(h.navigations.length, 0);
});

for (const code of ['partial-transfer', 'source-close-failed']) {
  for (const copySessionId of ['partial-copy', undefined]) {
    test(`${code} ${copySessionId ? 'with' : 'without'} copy ID locks out retry`, async () => {
      const h = harness(serverError(code, copySessionId));
      await primary(prepare(h)).props.onClick();
      const tree = h.render();
      assert.equal(primary(tree), undefined);
      assert.equal(elements(tree).some(node => node.type === 'select' || node.type === 'input'), false);
      assert.equal(h.requests.length, 1);
      assert.equal(h.navigations.length, 0);
      assert.equal(alertText(tree), copySessionId ? h.t('partial', { id: copySessionId }) : h.t('failed', { message: 'Sanitized server explanation' }));
    });
  }
}

for (const [label, fetchImpl, expectedKey] of [
  ['network failure', async () => { throw new Error('private transport data'); }, 'networkError'],
  ['invalid JSON', async () => ({ ok: true, json: async () => { throw new Error('private parser data'); } }), 'invalidResponse'],
  ['empty response', async () => ({ ok: true, json: async () => null }), 'invalidResponse'],
  ['same ID success', async () => ({ ok: true, json: async () => ({ ok: true, sessionId: 'source-session', workspaceId: 'target' }) }), 'invalidResponse'],
  ['wrong workspace success', async () => ({ ok: true, json: async () => ({ ok: true, sessionId: 'copy', workspaceId: 'wrong' }) }), 'invalidResponse'],
  ['HTTP failure without error details', async () => ({ ok: false, json: async () => ({ ok: true }) }), 'invalidResponse'],
]) {
  test(`${label} reports unknown outcome and removes retry controls`, async () => {
    const h = harness(fetchImpl);
    await primary(prepare(h)).props.onClick();
    const tree = h.render();
    assert.equal(primary(tree), undefined);
    assert.equal(alertText(tree), h.t(expectedKey));
    assert.equal(h.navigations.length, 0);
    assert.equal(h.requests.length, 1);
  });
}

test('sanitized non-ambiguous server failures retain retry controls', async () => {
  const h = harness(serverError('workspace-missing'));
  await primary(prepare(h)).props.onClick();
  assert.equal(alertText(h.render()), h.t('failed', { message: 'Sanitized server explanation' }));
  assert.ok(primary(h.render()));
});

test('compact dialog uses native description, title-only choices and collapsed limitations', () => {
  const h = harness();
  const tree = prepare(h);
  assert.equal(tree.type, 'Modal');
  assert.equal(tree.props.description, h.t('conversation', { title: 'Original conversation' }));
  assert.equal(primary(tree).props.children[0], 'Move');
  const target = elements(tree).find(node => node.type === 'option' && node.props.value === 'target');
  assert.equal(target.props.children[0], 'Target');
  assert.equal(target.props.title, '/target');
  assert.equal(elements(tree).find(node => node.type === 'details').props.open, undefined);
  assert.ok(elements(tree).some(node => node.props.id === 'test-destination-path'));
});

for (const [code, key] of [['seeded-source', 'seededSource'], ['session-active', 'activeSource']]) {
  test(`${code} is explained in the selected language`, async () => {
    const h = harness(serverError(code));
    await primary(prepare(h)).props.onClick();
    assert.equal(alertText(h.render()), h.t(key));
    assert.equal(h.navigations.length, 0);
  });
}

test('workspace stream must be idle and ready before confirmation is enabled', () => {
  const h = harness();
  h.snapshot.state = 'loading';
  let tree = h.open();
  assert.equal(primary(tree).props.disabled, true);
  assert.equal(elements(tree).find(node => node.type === 'select').props.disabled, true);
  h.snapshot.state = 'idle';
  h.snapshot.phase = 'pending';
  tree = h.render();
  assert.equal(elements(tree).find(node => node.type === 'select').props.disabled, true);
});
