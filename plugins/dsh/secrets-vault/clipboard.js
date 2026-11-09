import { spawn } from 'node:child_process';

/** Private pipeline: contents never appear in tool args/results, argv or logs. */
export function readClipboard(signal) {
  signal?.throwIfAborted();
  if (process.platform !== 'darwin') return Promise.reject(new Error('Clipboard import is available on macOS only.'));
  return new Promise((resolve,reject)=>{
    const child=spawn('/usr/bin/pbpaste',[],{signal,stdio:['ignore','pipe','ignore'],env:{PATH:'/usr/bin:/bin',LANG:'en_US.UTF-8'}});
    let chunks=[],size=0,failed=false;
    const timer=setTimeout(()=>{failed=true;child.kill('SIGKILL');},5000);
    child.stdout.on('data',chunk=>{size+=chunk.length;if(size>1048576){failed=true;chunks=[];child.kill('SIGKILL');}else if(!failed)chunks.push(chunk);});
    child.once('error',()=>{failed=true;chunks=[];}); // Drain close before settling cancellation.
    child.once('close',code=>{clearTimeout(timer);if(signal?.aborted){chunks=[];reject(signal.reason);return;}if(failed||code!==0){chunks=[];reject(new Error('Clipboard import failed.'));return;}const text=Buffer.concat(chunks).toString('utf8');chunks=[];resolve(text);});
  });
}
export async function importClipboard({store,metadata,id,read=readClipboard,signal}) {
  signal?.throwIfAborted();
  const state=await store.status();
  signal?.throwIfAborted();
  if(!state.unlocked) throw new Error('Unlock the vault before clipboard import.');
  let text=await read(signal);
  try {
    signal?.throwIfAborted();
    if(!text || !text.trim() || Buffer.byteLength(text)>1048576 || text.includes('\0')) throw new Error('Clipboard must contain a nonempty text credential.');
    const field=metadata.kind==='token'?'token':metadata.kind==='password'?'password':'privateKey';
    if(field==='token') {text=text.trim();if(/[\r\n]/.test(text))throw new Error('Clipboard token must be one line.');}
    // Import/replacement cannot grant agent use; user reviews authorization in UI.
    return await store.save({id,metadata:{...metadata,allowAgentUse:false},secret:{[field]:text}});
  } finally {text=null;}
}
