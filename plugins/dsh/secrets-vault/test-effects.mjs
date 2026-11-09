// Synthetic Cordis lifecycle ownership. Ordinary event names never trigger teardown.
export function ownedEffects() {
  const effects=[];let active=true,disposal;
  const effect=setup=>{
    if(!active)throw new Error('Inactive effect');
    const cleanup=setup();let result,called=false;
    const dispose=()=>{if(!called){called=true;result=cleanup?.();}return result;};
    effects.push(dispose);return dispose;
  };
  const on=event=>{if(event==='dispose')throw new Error('dispose is not a lifecycle event');};
  const dispose=()=>{
    active=false;
    return disposal??=Promise.all(effects.splice(0).reverse().map(fn=>{
      try{return Promise.resolve(fn());}catch(error){return Promise.reject(error);}
    }));
  };
  return {effect,on,dispose};
}
