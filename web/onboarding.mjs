// All enrollment decisions come from the server; no local consent cache.
export class Onboarding {
  constructor(render, fetcher = globalThis.fetch.bind(globalThis)) {
    this.render = render; this.fetcher = fetcher; this.reset();
  }
  reset() {
    this.epoch = (this.epoch || 0) + 1;
    this.user = null; this.disclosure = null; this.busy = false;
    this.controller?.abort(); this.controller = new AbortController();
    this.state = {phase:'signed-out'}; this.render(this.state);
  }
  show(state) { this.state = state; this.render(state); }
  async request(path, body, epoch) {
    const token = await this.user.getIdToken();
    if (epoch !== this.epoch) throw new Error('stale');
    const timeout = new AbortController();
    const timer = setTimeout(()=>timeout.abort(),15000);
    const abort = ()=>timeout.abort();
    const signal=this.controller.signal;
    signal.addEventListener('abort',abort,{once:true});
    let rejectAbort;
    const cancelled = new Promise((_,reject)=>{rejectAbort=()=>reject(new Error('cancelled'));timeout.signal.addEventListener('abort',rejectAbort,{once:true});});
    try {
      const response = await Promise.race([this.fetcher(path, {
        method: body === undefined ? 'GET' : 'POST',
        headers: {'Authorization':`Bearer ${token}`, ...(body === undefined ? {} : {'Content-Type':'application/json'})},
        body: body === undefined ? undefined : JSON.stringify(body),
        cache:'no-store', credentials:'omit', redirect:'error', signal:timeout.signal
      }),cancelled]);
      if (!response.ok) { const error = new Error('request'); error.status=response.status; throw error; }
      return await response.json();
    } finally {
      clearTimeout(timer); signal.removeEventListener('abort',abort);timeout.signal.removeEventListener('abort',rejectAbort);
    }
  }
  failure(error, epoch) {
    if (epoch !== this.epoch) return;
    const message = error.status===403 ? 'This account cannot participate right now. Use a verified Google account; restricted accounts cannot join.'
      : error.status===401 ? 'Please sign out and sign in again to continue.'
      : error.status===409 || error.status===422 ? 'Your account or agreement needs another check. Refresh the registration below.'
      : 'Google login is connected. Player registration is not available right now. No saved agreement has been confirmed.';
    this.show({phase:'unavailable',message});
  }
  async start(user) {
    this.reset(); this.user=user;
    const epoch=this.epoch;
    if (!user.emailVerified) { this.show({phase:'unavailable',message:'Verify your email before registering as a player.'}); return; }
    this.busy=true; this.show({phase:'loading'});
    try {
      const account=await this.request('/v1/account',{},epoch);
      if (epoch!==this.epoch) return;
      if (typeof account.consent_required!=='boolean' || account.mode!=='test') throw new Error('invalid account');
      const disclosure=await this.request('/v1/consent',undefined,epoch);
      if (epoch!==this.epoch) return;
      if (typeof disclosure.notice!=='string' || !disclosure.notice.trim() ||
          !Array.isArray(disclosure.rules) || !disclosure.rules.every(x=>typeof x==='string') ||
          typeof disclosure.terms_version!=='string' || typeof disclosure.disclosure_version!=='string') throw new Error('invalid disclosure');
      this.disclosure=disclosure;
      this.show({phase:account.consent_required?'consent':'ready',disclosure});
    } catch(error) {this.failure(error,epoch);}
    finally {if(epoch===this.epoch)this.busy=false;}
  }
  async consent(accept, background = {}) {
    if(this.busy || !this.user || !this.disclosure ||
      (accept && this.state.phase!=='consent') || (!accept && this.state.phase!=='ready')) return;
    const epoch=this.epoch, disclosure=this.disclosure;
    this.busy=true; this.show({phase:'saving',accept,disclosure});
    try {
      const saved=await this.request('/v1/consent',{accept,
        terms_version:disclosure.terms_version,disclosure_version:disclosure.disclosure_version,
        ...(accept?{adultConfirmed:true,background}: {})},epoch);
      if(epoch!==this.epoch)return;
      if(saved.accepted!==accept)throw new Error('agreement not confirmed');
      this.show({phase:accept?'ready':'consent',disclosure,withdrawn:!accept});
    }catch(error){this.failure(error,epoch);}
    finally{if(epoch===this.epoch)this.busy=false;}
  }
}
