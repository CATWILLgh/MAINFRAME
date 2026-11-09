import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { normalizeSessionTitle } from '@deepseek-ai/dsh-session-title';
import { createCollaboration } from './core.js';
import { createWaitMany } from './wait-many.js';
import { openTaskDomain } from './storage.js';
import { createLifecycleManagement } from './lifecycle-management.js';
import { createCollaborationTool } from './tool-surface.js';

export const inject = ['tools', 'workspaceRegistry', 'sessionController', 'agents', 'storageDomain', 'llm', 'sessionTitle'];
export async function apply(ctx) {
  // Cordis awaits async effect setup and its owned disposer on unload. An ordinary
  // event named "dispose" is not a lifecycle hook and would leak the open domain.
  await ctx.effect(async()=>{
    let domain,api,many,lifecycle,timer,cleanupTask;
    const cleanup=()=>cleanupTask??=(async()=>{
      clearInterval(timer);
      await Promise.allSettled([api,many,lifecycle].filter(Boolean).map(owner=>Promise.resolve().then(()=>owner.dispose())));
      await domain?.close();
    })();
    try {
      domain=await openTaskDomain(ctx);
      api=createCollaboration(ctx,createUserMessage,{table:domain.table('tasks')});
      many=createWaitMany(ctx);
      lifecycle=createLifecycleManagement(ctx,{normalizeTitle:normalizeSessionTitle});
      await api.ready;
      ctx.on('agent/pre-step',async({agent,signal},next)=>{
        const decision=await next();
        if(decision.kind==='enter')try{await api.onLive(agent,signal);}catch{/* Storage failure must not reject a native step. */}
        return decision;
      });
      ctx.on('agent/disposed',({agent})=>api.onDisposed(agent));
      timer=setInterval(()=>api.background(()=>api.maintenance()),60000);timer.unref?.();
      ctx.effect(()=>ctx.tools.register(createCollaborationTool(api,many,lifecycle)));
      return cleanup;
    } catch(error) {
      // Setup can fail before Cordis receives a returned disposer.
      await cleanup();
      throw error;
    }
  });
}
