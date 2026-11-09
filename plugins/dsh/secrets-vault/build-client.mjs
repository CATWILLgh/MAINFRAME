import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { embedLocaleDictionaries } from '../build-locales.mjs';

export async function buildClient() {
  const template = await fs.readFile(new URL('./client.template.js', import.meta.url), 'utf8');
  return embedLocaleDictionaries(template, import.meta.url);
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  await fs.writeFile(new URL('./client.js', import.meta.url), await buildClient());
}
