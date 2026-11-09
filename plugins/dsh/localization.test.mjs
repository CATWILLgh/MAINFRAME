import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { registerMainframeLocale, embedLocaleDictionaries } from './build-locales.mjs';

// Public locale contract: registration synchronously publishes a snapshot revision;
// lookup follows the language's fallback chain and interpolates named parameters.
function localeFixture() {
  let active = 'en';
  const languages = [{id:'en'}, ...['zh','ru','ja','es','fr','de','pt'].map(id=>({id,fallback:'en'}))];
  const listeners = new Set(), dictionaries = new Map();
  let revision = 0;
  const publish = () => { revision++; for (const fn of [...listeners]) fn(); };
  return {
    getSnapshot: () => ({ active, locales: [...languages], revision }),
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    register(ns, id, dict) {
      const key = `${ns}:${id.toLowerCase()}`;
      assert.equal(dictionaries.has(key),false,'no duplicate registrations');
      dictionaries.set(key, dict); publish();
      return () => { dictionaries.delete(key); publish(); };
    },
    bind(ns) { return (key,params) => {
      let id=active, text;
      while(id) {
        text=dictionaries.get(`${ns}:${id.toLowerCase()}`)?.[key];
        if(text!==undefined)break;
        id=languages.find(lang=>lang.id===id)?.fallback;
      }
      return (text??key).replace(/\{(\w+)\}/g,(match,name)=>params&&name in params?String(params[name]):match);
    }; },
    setLocale(id) { active=id; publish(); },
    addLanguage(definition) { languages.push(definition); publish(); },
    counts: () => ({ listeners: listeners.size, dictionaries: dictionaries.size }),
  };
}

test('native registry stays live: Russian only, English for every other locale including late packs', () => {
  const locale=localeFixture();
  const dispose=registerMainframeLocale(locale,'test',{greet:'Hello {name}'},{greet:'Привет, {name}'});
  const t=locale.bind('test');
  for(const {id} of locale.getSnapshot().locales) {
    locale.setLocale(id);
    assert.equal(t('greet',{name:'DSH'}),id==='ru'?'Привет, DSH':'Hello DSH');
  }
  locale.addLanguage({id:'xx',fallback:'ru'});
  locale.setLocale('xx');
  assert.equal(t('greet',{name:'DSH'}),'Hello DSH');
  locale.setLocale('ru');
  assert.equal(t('greet',{name:'DSH'}),'Привет, DSH');
  dispose();
  assert.deepEqual(locale.counts(),{listeners:0,dictionaries:0});
});

for (const plugin of ['activity-analytics','secrets-vault']) {
  test(`${plugin}: centralized resource keys and placeholders are valid`, async () => {
    const root=new URL(`./${plugin}/`,import.meta.url);
    const template=await fs.readFile(new URL('client.template.js',root),'utf8');
    const output=await embedLocaleDictionaries(template,root);
    assert.ok(!output.includes('/* LOCALE_DICTIONARIES */'));
    assert.ok(output.includes('function registerMainframeLocale('));
    assert.ok(!template.includes('const en = {'));
    const en=JSON.parse(await fs.readFile(new URL('locale/en.json',root)));
    for(const key of template.matchAll(/\bt\(['"]([^'"]+)['"]/g)) assert.ok(key[1] in en.ui,`Missing UI key ${key[1]}`);
  });
}

test('all three plugin metadata dictionaries have English and Russian titles/descriptions', async () => {
  for(const plugin of ['activity-analytics','secrets-vault','message-time']) {
    for(const language of ['en','ru']) {
      const resource=JSON.parse(await fs.readFile(new URL(`./${plugin}/locale/${language}.json`,import.meta.url)));
      assert.equal(typeof resource.meta.title,'string');
      assert.equal(typeof resource.meta.description,'string');
      if(language==='ru')assert.match(resource.meta.description,/[а-яё]/iu);
    }
  }
});
