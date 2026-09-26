// Camera data is held in memory until explicit submit; no microphone requested.
export const MAX_BYTES=8*1024*1024;
export const MAX_SECONDS=30;
export function recordingType(Recorder){
 return ['video/webm;codecs=vp8','video/webm','video/mp4'].find(t=>Recorder?.isTypeSupported(t));
}
export function validUploadURL(value){
 try {const u=new URL(value);return u.protocol==='https:' && u.hostname==='storage.googleapis.com' && u.pathname.startsWith('/upload/storage/v1/b/umi-signrush-raw/o') && u.searchParams.has('upload_id');}catch{return false;}
}
export class Signing {
 constructor(root,{mediaDevices=globalThis.navigator?.mediaDevices,Recorder=globalThis.MediaRecorder,fetcher=globalThis.fetch.bind(globalThis)}={}){
  this.root=root;this.mediaDevices=mediaDevices;this.Recorder=Recorder;this.fetcher=fetcher;this.epoch=0;
  this.el=id=>root.querySelector('#'+id);
  this.el('get-phrase').onclick=()=>this.requestPhrase();
  this.el('open-camera').onclick=()=>this.openCamera();
  this.el('record').onclick=()=>this.record();
  this.el('stop').onclick=()=>this.stop();
  this.el('retake').onclick=()=>{this.clearClip();this.openCamera();};
  this.el('submit-video').onclick=()=>this.submit();
  this.el('framing-check').onchange=()=>this.draw();
  globalThis.addEventListener?.('pagehide',()=>this.reset());
  this.reset();
 }
 reset(){
  this.epoch++;this.unsubscribe?.();this.unsubscribe=null;this.active=false;this.job=null;this.busy=false;this.uploading=false;
  this.abort?.abort();this.stopCamera();this.clearClip();this.service=null;this.root.hidden=true;
 }
 connect(service){
  this.reset();this.service=service;this.active=true;this.root.hidden=false;this.message('Get a phrase, then sign it on camera.');
  const epoch=this.epoch;
  this.unsubscribe=service.watch(job=>{if(epoch!==this.epoch)return;this.job=job;this.draw();if(job?.state==='uploading' && this.blob && !this.uploading)this.upload(job);},()=>{if(epoch===this.epoch){this.job={state:'blocked'};this.stopCamera();this.clearClip();this.draw();this.message('We couldn’t check your task. Sign in again to refresh it.');}});
  this.draw();
 }
 message(text){this.el('signing-status').textContent=text;}
 draw(){
  const j=this.job,s=j?.state;
  this.root.dataset.phase=['saved','failed','blocked'].includes(s)?s:this.recording?'recording':this.blob?'review':s||'idle';
  this.el('capture-surface').hidden=!j?.prompt;
  this.el('submission-result').hidden=s!=='saved';
  this.el('signing-title').textContent=s==='saved'?'Your submission':'Your signing challenge';
  const outcome=j?.outcome;
  this.el('signing-outcome').textContent=({approved:'Approved · Game points earned',quality_check_required:'Video quality needs a check',adjudication_required:'Needs a closer look',collection_full:'Collection target reached',rejected:'Recording not approved',test_only:'Non-qualifying recording',participation_paused:'Participation paused'})[outcome?.status]||'Awaiting review';
  this.el('signing-progress').textContent=outcome?.status==='approved'?'Your points have been added. Keep it up!':outcome?.status==='rejected'?'Independent reports found this video unusable. It has been removed from the task pool and earns no points.':outcome?.status==='quality_check_required'?'The meaning matched, but video quality needs a human check.':outcome?.status==='adjudication_required'?'Reviews need adjudication. No signer points awarded.':`${outcome?.independentReviews||0} of ${outcome?.requiredReviews||3} independent reviews received.`;
  this.el('get-phrase').hidden=Boolean(j)&&!['saved','failed','blocked'].includes(s);
  this.el('get-phrase').textContent=j?'Try another phrase ↗':'Get my phrase ↗';this.el('get-phrase').disabled=this.busy;
  this.el('phrase-panel').hidden=!j?.prompt;this.el('phrase-text').textContent=j?.prompt?`“${j.prompt}”`:'';
  this.el('phrase-coverage').textContent=Number.isInteger(j?.approvedSigners)&&Number.isInteger(j?.signerCap)?`${j.approvedSigners} / ${j.signerCap} approved unique signers`:'';
  const assigned=s==='assigned';
  this.el('open-camera').hidden=!assigned || Boolean(this.stream) || Boolean(this.blob);
  this.el('record').hidden=!assigned || !this.stream || this.recording || Boolean(this.blob);
  this.el('stop').hidden=!this.recording;
  this.el('retake').hidden=!assigned || !this.blob || this.busy;
  this.el('submit-video').hidden=!assigned || !this.blob;
  this.el('submit-video').disabled=this.busy || !this.el('framing-check').checked;
  this.el('framing-label').hidden=!assigned || !this.blob;
  const messages={requested:'Finding an eligible phrase for you. Please wait; your request is saved. If this takes longer than expected, you can return later.',upload_requested:'Preparing your private upload…',uploading:'Uploading your recording…',submitted:'Upload received. Checking the saved file…',saved:'',failed:'This recording was kept separately as a failed attempt. No points were awarded.',blocked:'This task could not continue. Your recording has not been approved.'};
  if(Object.hasOwn(messages,s))this.message(messages[s]);
  this.el('signing-receipt').textContent=['saved','failed'].includes(s)?`Recording ID: ${j.assignmentId}`:'';
  if(['saved','failed','blocked'].includes(s)){this.stopCamera();this.clearClip();}
 }
 async requestPhrase(){
  if(this.busy||!this.active)return;
  const open=this.job&&!['saved','failed','blocked'].includes(this.job.state);
  if(open)return;
  this.busy=true;this.draw();const epoch=this.epoch;
  try{const result=await this.service.request();if(epoch===this.epoch&&result==='empty')this.message('No signing phrases are open right now. Check back after more are added.');}
  catch{if(epoch===this.epoch)this.message('The phrase request wasn’t confirmed. Wait a moment, then try again.');}
  finally{if(epoch===this.epoch){this.busy=false;this.draw();}}
 }
 async openCamera(){
  if(this.busy||this.job?.state!=='assigned')return;
  if(!this.mediaDevices?.getUserMedia||!recordingType(this.Recorder)){this.message('Recording is unavailable here. Open SignRush in a current Chrome or Safari browser.');return;}
  this.busy=true;const epoch=this.epoch;
  try{
   const stream=await this.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30,max:30}}});
   if(epoch!==this.epoch || this.job?.state!=='assigned'){stream.getTracks().forEach(t=>t.stop());return;}
   this.stream=stream;const v=this.el('camera');v.srcObject=stream;v.hidden=false;v.classList.add('mirrored');v.controls=false;v.muted=true;
   await v.play();this.message('Ready? Keep your face and hands in view.');
  }catch{if(epoch===this.epoch){this.stopCamera();this.message('Camera access didn’t start. Allow the camera for this page, then try again.');}}
  finally{if(epoch===this.epoch){this.busy=false;this.draw();}}
 }
 record(){
  if(this.recording||!this.stream||this.job?.state!=='assigned')return;
  const epoch=this.epoch;let chunks=[],size=0,overflow=false;this.started=performance.now();this.recording=true;
  try{this.recorder=new this.Recorder(this.stream,{mimeType:recordingType(this.Recorder),videoBitsPerSecond:1200000});}catch{this.recording=false;this.message('This browser couldn’t start recording. Try Chrome.');return;}
  this.recorder.ondataavailable=e=>{if(epoch!==this.epoch)return;if(e.data.size){size+=e.data.size;if(size>MAX_BYTES){overflow=true;chunks=[];this.stop();}else if(!overflow)chunks.push(e.data);}};
  this.recorder.onerror=()=>{overflow=true;this.stop();};
  this.recorder.onstop=()=>{
   if(epoch!==this.epoch)return;clearInterval(this.timer);this.recording=false;this.stopCamera();
   if(overflow||!size){this.message('That take could not be kept. Try a shorter recording.');this.draw();return;}
   this.blob=new Blob(chunks,{type:this.recorder.mimeType});chunks=[];this.clipURL=URL.createObjectURL(this.blob);
   const v=this.el('camera');v.srcObject=null;v.src=this.clipURL;v.classList.remove('mirrored');v.controls=true;v.muted=true;
   this.message('Review your take, then submit or retake.');this.draw();
  };
  try{this.recorder.start(250);}catch{this.stopCamera();this.message('Recording could not start. Try opening the camera again.');this.draw();return;}this.message('Recording · Sign the words above.');
  this.timer=setInterval(()=>{const n=(performance.now()-this.started)/1000;this.el('recording-time').textContent=`${Math.min(MAX_SECONDS,Math.floor(n))} / ${MAX_SECONDS} sec`;if(n>=MAX_SECONDS)this.stop();},200);this.draw();
 }
 stop(){if(this.recorder?.state==='recording')this.recorder.stop();}
 discardTake(){if(this.recorder){this.recorder.onstop=null;this.recorder.ondataavailable=null;}this.stopCamera();this.clearClip();this.draw();}
 stopCamera(){clearInterval(this.timer);this.stop();this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.recording=false;this.el('camera').srcObject=null;}
 clearClip(){if(this.clipURL)URL.revokeObjectURL(this.clipURL);this.clipURL=null;this.blob=null;const v=this.el('camera');v.removeAttribute('src');v.hidden=true;this.el('framing-check').checked=false;this.el('recording-time').textContent='';}
 async submit(){
  if(this.busy||!this.blob||this.job?.state!=='assigned'||!this.el('framing-check').checked)return;
  this.busy=true;this.draw();const epoch=this.epoch;
  try{
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await this.blob.arrayBuffer())),x=>x.toString(16).padStart(2,'0')).join('');
   if(epoch!==this.epoch)return;
   await this.service.prepare({size:this.blob.size,mime:this.blob.type.split(';')[0],sha256:hash});
  }catch{if(epoch===this.epoch)this.message('Upload preparation wasn’t confirmed. Keep this tab open and try again.');}
  finally{if(epoch===this.epoch){this.busy=false;this.draw();}}
 }
 async upload(job){
  if(!validUploadURL(job.uploadURL)){this.message('The upload destination could not be verified.');return;}
  this.uploading=true;const epoch=this.epoch;this.abort=new AbortController();const timer=setTimeout(()=>this.abort?.abort(),120000);
  try{
   const response=await this.fetcher(job.uploadURL,{method:'PUT',headers:{'Content-Type':job.mime},body:this.blob,credentials:'omit',redirect:'error',signal:this.abort.signal});
   if(epoch!==this.epoch)return;
   if(!response.ok)throw new Error('upload');
   await this.service.finish();
  }catch{if(epoch===this.epoch)this.message('Upload wasn’t confirmed. The cloud check will reconcile any completed file. Keep this tab open.');}
  finally{clearTimeout(timer);}
 }
}
export function signingService(user,db,sdk){
 const ref=sdk.doc(db,'signingJobs',user.uid);
 return {
  watch:(next,error)=>sdk.onSnapshot(ref,snap=>next(snap.exists()?snap.data():null),error),
  request:()=>sdk.setDoc(ref,{uid:user.uid,state:'requested',requestedAt:sdk.serverTimestamp()}),
  prepare:fields=>sdk.updateDoc(ref,{...fields,state:'upload_requested'}),
  finish:()=>sdk.updateDoc(ref,{state:'submitted'})
 };
}
