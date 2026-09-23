export function validPlaybackURL(value){
 try{const u=new URL(value);return u.protocol==='https:' && u.hostname==='storage.googleapis.com' && /^\/umi-signrush-raw\/pilot\/playback\/[a-f0-9]{32}\/silent-v1\.mp4$/.test(u.pathname) && u.searchParams.get('X-Goog-Algorithm')==='GOOG4-RSA-SHA256' && u.searchParams.has('X-Goog-Signature') && u.searchParams.get('X-Goog-Expires')==='300';}catch{return false;}
}
export class Review {
 constructor(root){
  this.root=root;this.el=id=>root.querySelector('#'+id);this.epoch=0;
  this.el('find-review').onclick=()=>this.request();
  this.el('refresh-review-video').onclick=()=>this.refresh();
  this.el('review-answer').oninput=()=>this.buttons();
  this.el('review-quality').onchange=()=>this.buttons();
  this.el('review-form').onsubmit=e=>{e.preventDefault();this.submit();};
  this.el('review-video').onerror=()=>{if(this.active){this.el('refresh-review-video').hidden=false;this.message('Video unavailable? Reload it and try again.');}};
  this.reset();
 }
 reset(){this.epoch++;this.unsubscribe?.();this.active=false;this.busy=false;this.job=null;this.service=null;this.src=null;this.el('review-video').pause();this.el('review-video').removeAttribute('src');this.el('review-answer').value='';this.el('review-quality').value='';this.root.hidden=true;}
 connect(service){
  this.reset();this.active=true;this.service=service;const epoch=this.epoch;
  this.unsubscribe=service.watch(job=>{if(epoch!==this.epoch)return;this.job=job;this.draw();},()=>{if(epoch===this.epoch){this.job={state:'blocked'};this.draw();}});this.draw();
 }
 message(s){this.el('review-status').textContent=s;}
 buttons(){this.el('submit-review').disabled=this.busy||this.job?.state!=='assigned'||!this.el('review-answer').value.trim()||!this.el('review-quality').value;}
 draw(){
  const j=this.job,s=j?.state;this.root.dataset.phase=s||'idle';
  this.el('find-review').hidden=Boolean(j)&&!['empty','pending','blocked'].includes(s);this.el('find-review').disabled=this.busy;
  this.el('find-review').textContent=s==='pending'?'Review another video':s==='empty'?'Check for a video':'Find a video';
  this.el('review-form').hidden=s!=='assigned';this.el('review-player').hidden=!['assigned','refresh_requested'].includes(s);
  this.el('review-complete').hidden=s!=='pending';
  this.el('refresh-review-video').hidden=s!=='assigned';this.el('refresh-review-video').disabled=this.busy;
  const texts={idle:'Watch a signer, then write the meaning in English.',requested:'Finding a video for you…',empty:'No eligible videos yet. Your own recordings and phrases you’ve already seen are excluded.',preparing:'Getting your private video ready…',assigned:'Watch the signing. What does it mean?',refresh_requested:'Reloading the private video…',submitted:'Saving your review…',pending:'',blocked:'This review isn’t available. Sign in again to check your access.'};
  this.message(texts[s||'idle']||'');
  if(s==='assigned' && j.playbackURL!==this.src){
   if(!validPlaybackURL(j.playbackURL)){this.el('review-form').hidden=true;this.message('The video link could not be verified.');return;}
   this.src=j.playbackURL;this.el('review-video').src=this.src;
  }
  if(!['assigned','refresh_requested'].includes(s)){this.el('review-video').pause();this.el('review-video').removeAttribute('src');this.src=null;}
  if(s==='pending'){this.el('review-answer').value='';this.el('review-quality').value='';}
  const outcome=j?.outcome;
  this.el('review-outcome').textContent=({approved:'Review approved',test_only:'Test review saved',ineligible:'Review not eligible',adjudication_required:'Needs a closer look'})[outcome?.status]||'Awaiting consensus';
  this.el('review-progress').textContent=outcome?.status==='approved'?'5 test points earned. No cash value.':outcome?.status==='test_only'?'Saved for interface testing. This is not an independent review and earns no points.':outcome?.status==='adjudication_required'?'A human check is needed. No points awarded for this review.':`${outcome?.independentReviews||0} of 3 independent reviews received.`;this.buttons();
 }
 async action(fn){if(this.busy||!this.active)return;this.busy=true;this.buttons();const epoch=this.epoch;try{await fn();}catch{if(epoch===this.epoch)this.message('That update wasn’t confirmed. Please try again.');}finally{if(epoch===this.epoch){this.busy=false;this.buttons();this.el('find-review').disabled=false;this.el('refresh-review-video').disabled=false;}}}
 request(){if(this.job&&!['empty','pending','blocked'].includes(this.job.state))return;return this.action(()=>this.service.request());}
 refresh(){if(this.job?.state!=='assigned')return;return this.action(()=>this.service.refresh());}
 submit(){const text=this.el('review-answer').value.trim();const quality=this.el('review-quality').value;if(this.job?.state!=='assigned'||!text||text.length>1000||!['good','poor','not_sure'].includes(quality))return;return this.action(()=>this.service.submit(text,quality));}
}
export function reviewService(user,db,sdk){
 const ref=sdk.doc(db,'reviewJobs',user.uid);
 return {watch:(next,error)=>sdk.onSnapshot(ref,s=>next(s.exists()?s.data():null),error),
  request:()=>sdk.setDoc(ref,{uid:user.uid,state:'requested',requestedAt:sdk.serverTimestamp()}),
  refresh:()=>sdk.updateDoc(ref,{state:'refresh_requested'}),
  submit:(text,quality)=>sdk.updateDoc(ref,{state:'submitted',text,quality,submittedAt:sdk.serverTimestamp()})};
}
