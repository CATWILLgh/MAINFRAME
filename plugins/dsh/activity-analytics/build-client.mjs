import fs from 'node:fs/promises';
import { embedLocaleDictionaries } from '../build-locales.mjs';
const root=new URL('./',import.meta.url);
const core=await fs.readFile(new URL('time.js',root),'utf8');
const template=await embedLocaleDictionaries(await fs.readFile(new URL('client.template.js',root),'utf8'),root);
if(!template.includes('/* TIME_CORE */'))throw new Error('Missing core insertion marker');
// The pure time module is embedded unchanged except for its ES export keywords.
const outbox=await fs.readFile(new URL('outbox.js',root),'utf8');
if(!template.includes('/* OUTBOX_CORE */'))throw new Error('Missing outbox insertion marker');
const output=template.replace('/* TIME_CORE */',()=>core.replace(/^export /gm,'')).replace('/* OUTBOX_CORE */',()=>outbox.replace(/^export /gm,''));
await fs.writeFile(new URL('client.js',root),output);
