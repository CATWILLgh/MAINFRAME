import test from 'node:test';
import assert from 'node:assert/strict';
import {importClipboard} from './clipboard.js';
test('clipboard import returns opaque id only and removes usage authority',async()=>{
 let saved;
 const store={status:async()=>({unlocked:true}),save:async v=>{saved=v;return {id:'synthetic-id'};}};
 const result=await importClipboard({store,metadata:{name:'Test',kind:'token',allowAgentUse:true},read:async()=>'  synthetic-test-secret  '});
 assert.deepEqual(result,{id:'synthetic-id'});
 assert.equal(saved.secret.token,'synthetic-test-secret');
 assert.equal(saved.metadata.allowAgentUse,false);
 assert(!JSON.stringify(result).includes('synthetic-test-secret'));
});
test('locked vault never reads clipboard',async()=>{
 let read=false;
 await assert.rejects(importClipboard({store:{status:async()=>({unlocked:false})},metadata:{kind:'token'},read:async()=>{read=true;return 'fake';}}));
 assert.equal(read,false);
});
test('preserves password whitespace and key lines; rejects empty, NUL and multiline token',async()=>{
 let saved;const store={status:async()=>({unlocked:true}),save:async v=>{saved=v;return {id:'x'};}};
 await importClipboard({store,metadata:{kind:'password'},read:async()=>' password \n'});assert.equal(saved.secret.password,' password \n');
 await importClipboard({store,metadata:{kind:'ssh-key'},read:async()=>'fake\nkey\n'});assert.equal(saved.secret.privateKey,'fake\nkey\n');
 for(const text of ['','   ','a\0b','a\nb']) await assert.rejects(importClipboard({store,metadata:{kind:'token'},read:async()=>text}));
});
