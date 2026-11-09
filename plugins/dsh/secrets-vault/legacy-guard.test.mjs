import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,readdir,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {VaultStore} from './vault-store.js';

for (const kind of ['database','orphan-envelope','dangling-symlink']) {
  test(`adapter refuses ${kind} without reading or changing legacy data`,async t=>{
    const dir=await mkdtemp(path.join(tmpdir(),'vault-legacy-synthetic-'));
    const databasePath=path.join(dir,'vault.v2.json');
    const name=kind==='database'?'vault.db':'vault.db.recovery.json';
    const legacy=path.join(dir,name);
    if(kind==='dangling-symlink') await symlink(path.join(dir,'absent-synthetic-target'),legacy);
    else await writeFile(legacy,'SYNTHETIC-LEGACY-DO-NOT-READ',{mode:0o600});
    const store=new VaultStore({databasePath});
    try {
      for(const operation of [()=>store.status(),()=>store.setup('synthetic-test-password','synthetic-test-password')]) {
        await assert.rejects(operation(),{code:'LEGACY_VAULT_FORMAT'});
      }
      assert.deepEqual(await readdir(dir),[name]);
      if(kind!=='dangling-symlink') assert.equal(await readFile(legacy,'utf8'),'SYNTHETIC-LEGACY-DO-NOT-READ');
    } finally {
      await store.dispose();
      assert.equal(path.dirname(path.resolve(dir)),path.resolve(tmpdir()));
      assert.ok(path.basename(dir).startsWith('vault-legacy-synthetic-'));
      await rm(dir,{recursive:true});
    }
  });
}
