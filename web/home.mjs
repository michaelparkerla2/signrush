import {Payout,payoutService} from './payout.mjs';
export function progress(points){
 const safe=Number.isSafeInteger(points)&&points>=0?points:0;
 return {points:safe,target:(Math.floor(safe/25)+1)*25,remaining:25-safe%25,value:safe%25};
}
export class Home {
 constructor(root,payoutRoot=root){this.root=root;this.el=id=>root.querySelector('#'+id);this.epoch=0;this.payout=new Payout(payoutRoot);
  this.el('cash-out').onclick=()=>this.el('cash-wallet').showModal();
  this.el('close-wallet').onclick=()=>this.el('cash-wallet').close();
  this.el('share-signrush').onclick=()=>this.share();
  this.el('copy-signrush').onclick=()=>this.copyLink();
  this.reset();}
 reset(){this.payout.reset();this.epoch++;this.stops?.forEach(stop=>stop());this.stops=[];this.active=false;this.previous=null;this.el('cash-wallet').close();this.el('wallet-test-points').textContent='—';this.el('share-status').textContent='';this.el('home-points').textContent='—';this.el('star-progress').value=0;this.el('milestone-label').textContent='Checking your progress…';this.el('earned-stars').textContent='Your stars are waiting';this.root.hidden=true;}
 async copyLink(){
  const epoch=this.epoch;
  try{await navigator.clipboard.writeText('https://signrush-login.web.app/');if(epoch===this.epoch)this.el('share-status').textContent='Link copied. Share it wherever you like.';}
  catch{if(epoch===this.epoch)this.el('share-status').textContent='Copy this link: https://signrush-login.web.app/';}
 }
 async share(){
  if(!navigator.share)return this.copyLink();
  const epoch=this.epoch;
  try{await navigator.share({title:'SignRush',text:'Take a peek at SignRush, an ASL game in an open pilot.',url:'https://signrush-login.web.app/'});if(epoch===this.epoch)this.el('share-status').textContent='Thanks for spreading the word!';}
  catch(error){if(error.name!=='AbortError'&&epoch===this.epoch)this.el('share-status').textContent='Sharing could not open. Try Copy link below.';}
 }
 connect(service){
  this.reset();this.active=true;const epoch=this.epoch;
  if(service.payout)this.payout.connect(service.payout);
  this.el('home-message').textContent='Two ways to play. One goal: make every meaning count.';
  for(const id of ['home-sign-count','home-review-count','home-pending','home-approved','home-submitted'])this.el(id).textContent='…';
  this.el('home-sign').disabled=true;this.el('home-review').disabled=true;
  this.stops.push(service.tasks(d=>{
   if(epoch!==this.epoch)return;
   for(const [id,key] of [['home-sign-count','signAvailable'],['home-review-count','reviewAvailable'],['home-pending','pending'],['home-approved','approved'],['home-submitted','submitted']])this.el(id).textContent=d?String(d[key]??0):'…';
   this.el('home-sign').disabled=!(d?.signAvailable||d?.signInProgress);this.el('home-review').disabled=!(d?.reviewAvailable||d?.reviewInProgress);
   this.el('home-sign-label').textContent=d?.signInProgress?'Continue signing':'Sign a phrase';
   this.el('home-review-label').textContent=d?.reviewInProgress?'Finish your review':'Decode a sign';
   this.el('queue-note').textContent=d?(d.signAvailable||d.reviewAvailable||d.signInProgress||d.reviewInProgress?'Pick a challenge. Pending reviews can finish while you keep going.':'You’re caught up! Check back for more eligible challenges.'):'Checking your available challenges…';
  },()=>{if(epoch===this.epoch)this.el('queue-note').textContent='Task counts are unavailable. Try refreshing.';}));
  this.stops.push(service.points(points=>{
   if(epoch!==this.epoch)return;const p=progress(points);
   this.el('home-points').textContent=String(p.points);this.el('wallet-test-points').textContent=String(p.points);this.el('star-progress').value=p.value;
   this.el('star-progress').setAttribute('aria-label',`${p.remaining} test points to your next star`);
   this.el('milestone-label').textContent=`${p.remaining} points to ${p.points>=25?'your next':'your first'} star`;
   this.el('earned-stars').textContent=`${Math.floor(p.points/25)} stars collected`;
   if(this.previous!==null&&p.points>this.previous){this.el('home-message').textContent=`Hooray! +${p.points-this.previous} test points. Your effort is adding up!`;this.root.classList.remove('celebrate');void this.root.offsetWidth;this.root.classList.add('celebrate');}
   this.previous=p.points;
  },()=>{if(epoch===this.epoch){this.el('home-points').textContent='—';this.el('wallet-test-points').textContent='Unavailable';}}));
 }
}
export function homeService(user,db,sdk){return {
 payout:payoutService(user,db,sdk),
 tasks:(next,error)=>sdk.onSnapshot(sdk.doc(db,'playerDashboard',user.uid),s=>next(s.exists()?s.data():null),error),
 points:(next,error)=>sdk.onSnapshot(sdk.doc(db,'playerRewards',user.uid),s=>next(s.exists()?s.data().points:0),error)
};}
