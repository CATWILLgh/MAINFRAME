// Build-time only. JSON files are the sole translation owners; browser artifacts
// embed them because dynamic client modules cannot import package JSON at runtime.
import fs from 'node:fs/promises';

export function registerMainframeLocale(locale, namespace, en, ru) {
  const disposers = new Map();
  let refreshing = false;
  function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      for (const { id } of locale.getSnapshot().locales) {
        const key = id.toLowerCase();
        if (!disposers.has(key)) {
          // Mark before register: it synchronously notifies snapshot subscribers.
          disposers.set(key, null);
          disposers.set(key, locale.register(namespace, id, key === 'ru' ? ru : en));
        }
      }
    } finally { refreshing = false; }
  }
  refresh();
  const unsubscribe = locale.subscribe(refresh);
  return () => {
    unsubscribe();
    for (const dispose of disposers.values()) dispose?.();
    disposers.clear();
  };
}

export async function embedLocaleDictionaries(template, root) {
  const marker = '/* LOCALE_DICTIONARIES */';
  if (template.split(marker).length !== 2) throw new Error('Expected one locale insertion marker');
  const dictionaries = {};
  for (const language of ['en', 'ru']) {
    const resource = JSON.parse(await fs.readFile(new URL(`locale/${language}.json`, root), 'utf8'));
    const dictionary = resource.ui;
    if (!dictionary || typeof dictionary !== 'object' || Array.isArray(dictionary)) throw new Error(`Missing ${language} UI dictionary`);
    for (const [key, text] of Object.entries(dictionary)) {
      if (!key || typeof text !== 'string' || !text.trim() || /[\u200b\ufeff]/u.test(text)) throw new Error(`Invalid ${language} locale entry: ${key}`);
    }
    dictionaries[language] = dictionary;
  }
  const keys = dictionary => Object.keys(dictionary).sort();
  if (JSON.stringify(keys(dictionaries.en)) !== JSON.stringify(keys(dictionaries.ru))) throw new Error('English/Russian locale keys differ');
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
  for (const key of keys(dictionaries.en)) {
    if (JSON.stringify(placeholders(dictionaries.en[key])) !== JSON.stringify(placeholders(dictionaries.ru[key]))) throw new Error(`Locale placeholders differ: ${key}`);
  }
  const literal = value => JSON.stringify(value, null, 2).replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
  return template.replace(marker, () => `const en = ${literal(dictionaries.en)};\nconst ru = ${literal(dictionaries.ru)};\n${registerMainframeLocale.toString()}`);
}
