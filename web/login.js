import {firebaseConfig} from './firebase-config.js';
import {Onboarding} from './onboarding.mjs';
import {firestoreRegistration} from './firestore-registration.mjs';
import {pilotDisclosure} from './pilot-disclosure.mjs';
import {Signing,signingService} from './signing.mjs';
import {Review,reviewService} from './review.mjs';
import {Home,homeService} from './home.mjs';
import {Game,gameService} from './game.mjs';
const game=new Game(document);
let gameContext=null;
const home=new Home(document.querySelector('#home'),document);
let homeContext=null;
const signing=new Signing(document.querySelector('#signing'));
const reviewing=new Review(document.querySelector('#reviewing'));
let signingContext=null,reviewContext=null,rewardContext=null,rewardUnsubscribe=null,taskMode='home';
function showMode(mode){
 if(mode!=='sign' && signing.job?.state==='assigned' && (signing.stream||signing.blob)){
  if(!window.confirm('Leave this take? Your unsubmitted recording will be discarded.'))return;
  signing.discardTake();
 }
 taskMode=mode;
 home.root.hidden=mode!=='home';
 document.getElementById('arena').hidden=mode!=='arena';
 document.getElementById('mode-arena').setAttribute('aria-pressed',String(mode==='arena'));
 document.getElementById('mode-home').setAttribute('aria-pressed',String(mode==='home'));
 document.getElementById('test-rewards').hidden=mode==='home';
 document.getElementById('mode-sign').setAttribute('aria-pressed',String(mode==='sign'));
 document.getElementById('mode-review').setAttribute('aria-pressed',String(mode==='review'));
 signing.root.hidden=mode!=='sign';reviewing.root.hidden=mode!=='review';
 if(mode!=='review')reviewing.el('review-video').pause();
}
document.getElementById('mode-arena').onclick=()=>showMode('arena');
document.getElementById('home-arena').onclick=()=>showMode('arena');
document.getElementById('mode-home').onclick=()=>showMode('home');
document.getElementById('home-sign').onclick=()=>{showMode('sign');signing.requestPhrase();};
document.getElementById('home-review').onclick=()=>{showMode('review');reviewing.request();};
document.getElementById('mode-sign').onclick=()=>showMode('sign');
document.getElementById('mode-review').onclick=()=>showMode('review');
const login = document.querySelector('#login');
const status = document.querySelector('#status');
const enterRush=document.querySelector('#enter-rush');
function setLoginDisabled(value){login.disabled=value;enterRush.disabled=value;}
function authStatus(message){status.textContent=message;document.querySelector('#entry-status').textContent=message;}
const account = document.querySelector('#account');
const byId = id=>document.getElementById(id);
let currentUser=null,previousRegistration=null,payoutAutoOpen=false;
function openPayout(welcome=false){
 byId('cash-wallet').close();
 byId('payout-welcome').hidden=!welcome;
 byId('payout-done').textContent=welcome?'Skip, add later when I have points':'Done';
 if(!byId('payout-dialog').open)byId('payout-dialog').showModal();
 payoutAutoOpen=home.payout.loading;
 home.payout.edit();
}
for(const id of ['payout-nav','home-payout','wallet-payout'])byId(id).onclick=()=>openPayout();
for(const id of ['close-payout','payout-done'])byId(id).onclick=()=>byId('payout-dialog').close();
home.payout.onChange=()=>{
 byId('home-payout').querySelector('strong').textContent=home.payout.saved?'Manage payout account':'Add payout account';
 if(home.payout.saved)byId('payout-done').textContent='Done · Let’s play';
 if(payoutAutoOpen&&!home.payout.loading){payoutAutoOpen=false;if(byId('payout-dialog').open&&!home.payout.saved&&!home.payout.error)home.payout.edit();}
};
const registration=new Onboarding(state=>{
 const phase=state.phase;
 const ready=phase==='ready';
 const justRegistered=ready&&previousRegistration?.phase==='saving'&&previousRegistration.accept;
 previousRegistration=state;
 byId('payout-nav').hidden=!ready;
 if(!ready){payoutAutoOpen=false;byId('payout-dialog').close();}
 document.body.classList.toggle('player-ready',ready);
 byId('account-toggle').hidden=!ready;
 byId('account-toggle').setAttribute('aria-expanded','false');
 byId('account-panel').hidden=ready;
 byId('agreement-details').open=false;
 byId('privacy-request-panel').hidden=phase==='signed-out'||phase==='loading';
 byId('task-modes').hidden=!ready;
 byId('test-rewards').hidden=!ready;
 if(ready&&rewardContext&&!rewardUnsubscribe)rewardUnsubscribe=rewardContext();
 if(!ready){rewardUnsubscribe?.();rewardUnsubscribe=null;byId('test-points').textContent='Checking points…';}
 if(phase==='ready' && signingContext && !signing.active) signing.connect(signingContext());
 else if(phase!=='ready' && signing.active) signing.reset();
 if(ready && reviewContext && !reviewing.active)reviewing.connect(reviewContext());
 else if(!ready && reviewing.active)reviewing.reset();
 if(ready&&homeContext&&!home.active)home.connect(homeContext());
 if(ready&&gameContext&&!game.service)game.connect(gameContext());
 if(!ready){game.reset();byId('arena').hidden=true;}
 if(!ready&&home.active)home.reset();
 if(ready)showMode(taskMode);
 if(justRegistered)openPayout(true);
 byId('onboarding').hidden=phase==='signed-out';
 byId('agreement').hidden=!state.disclosure;
 byId('consent-form').hidden=phase!=='consent';
 byId('retry-registration').hidden=phase!=='unavailable';
 byId('withdraw').hidden=phase!=='ready';
 byId('agree').checked=false;byId('save-consent').disabled=true;
 if(phase==='signed-out'){for(const id of ['asl-experience','hearing-identity','asl-role'])byId(id).value='unspecified';byId('privacy-request-text').value='';byId('privacy-request-status').textContent='';}
 byId('registration-status').textContent=state.message || ({
  loading:'Checking your player profile…',
  consent:state.withdrawn?'Your agreement was withdrawn. Participation is paused.':'Welcome to SignRush! A little about you, then you’re ready to join.',
  saving:state.accept?'Saving your agreement…':'Withdrawing your agreement…',
  ready:''
 }[phase] || '');
 if(state.disclosure){
  byId('rules').replaceChildren(...state.disclosure.rules.map(rule=>{const li=document.createElement('li');li.textContent=rule;return li;}));
  byId('disclosure').textContent=state.disclosure.notice;
  byId('agreement-versions').textContent=`Rules: ${state.disclosure.terms_version} · Training disclosure: ${state.disclosure.disclosure_version}`;
 }else{
  byId('rules').replaceChildren();byId('disclosure').textContent='';byId('agreement-versions').textContent='';
 }
});
byId('account-toggle').addEventListener('click',()=>{
 const panel=byId('account-panel');panel.hidden=!panel.hidden;
 if(panel.hidden)byId('agreement-details').open=false;
 byId('account-toggle').setAttribute('aria-expanded',String(!panel.hidden));
});
byId('agree').addEventListener('change',()=>{byId('save-consent').disabled=!byId('agree').checked;});
byId('consent-form').addEventListener('submit',event=>{event.preventDefault();if(byId('agree').checked)registration.consent(true,{aslExperience:byId('asl-experience').value,hearingIdentity:byId('hearing-identity').value,aslRole:byId('asl-role').value});});
byId('retry-registration').addEventListener('click',()=>{if(currentUser)registration.start(currentUser);});
byId('withdraw').addEventListener('click',()=>registration.consent(false));
const errors = {
 'auth/popup-blocked':'Your browser blocked the sign-in window. Allow popups for this page and try again.',
 'auth/popup-closed-by-user':'Sign-in was closed. You can try again whenever you’re ready.',
 'auth/unauthorized-domain':'This preview address is not authorized for sign-in yet.',
 'auth/network-request-failed':'We couldn’t reach Google. Check your connection and try again.',
 'auth/cancelled-popup-request':'A sign-in window is already open. Please finish there.',
 'auth/operation-not-allowed':'Google sign-in is not available yet.'
};
try {
 const [{initializeApp},sdk,firestoreSDK] = await Promise.all([
  import('https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js'),
  import('https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js'),
  import('https://www.gstatic.com/firebasejs/12.19.0/firebase-firestore.js')
 ]);
 const app = initializeApp(firebaseConfig);
 const auth = sdk.getAuth(app);
 // Standard Firestore in the no-billing Spark project; verified Google accounts and private owner-only rules.
 const useFirestoreRegistration = true;
 if(useFirestoreRegistration) registration.fetcher=firestoreRegistration(auth,firestoreSDK.getFirestore(app),firestoreSDK,pilotDisclosure);
 byId('privacy-request-form').addEventListener('submit',async event=>{
  event.preventDefault();const user=auth.currentUser;if(!user)return;
  const button=byId('privacy-request-save');button.disabled=true;
  byId('privacy-request-status').textContent='Saving your request…';
  try{await firestoreSDK.addDoc(firestoreSDK.collection(firestoreSDK.getFirestore(app),'privacyRequests'),{uid:user.uid,kind:byId('privacy-request-kind').value,details:byId('privacy-request-text').value.trim(),status:'requested',createdAt:firestoreSDK.serverTimestamp()});
   if(auth.currentUser?.uid===user.uid){byId('privacy-request-status').textContent='Request saved privately for review. No email was sent. This is not confirmation that processing is complete.';byId('privacy-request-text').value='';}
  }catch{if(auth.currentUser?.uid===user.uid)byId('privacy-request-status').textContent='Could not confirm your request. Please try again.';}finally{button.disabled=false;}
 });
 // Keep credentials only in memory. Never print, store, or put tokens in URLs.
 await sdk.setPersistence(auth,sdk.inMemoryPersistence);
 const provider = new sdk.GoogleAuthProvider();
 provider.setCustomParameters({prompt:'select_account'});
 sdk.onAuthStateChanged(auth,user=>{
  rewardUnsubscribe?.();rewardUnsubscribe=null;currentUser=user;
  rewardContext=user?()=>firestoreSDK.onSnapshot(firestoreSDK.doc(firestoreSDK.getFirestore(app),'playerRewards',user.uid),s=>{if(currentUser?.uid===user.uid)byId('test-points').textContent=`${s.exists()?s.data().points:0} points`;},()=>{byId('test-points').textContent='Points unavailable';}):null;
  gameContext=user?()=>gameService(user,firestoreSDK.getFirestore(app),firestoreSDK):null;
  homeContext=user?()=>homeService(user,firestoreSDK.getFirestore(app),firestoreSDK):null;
  signingContext=user?()=>signingService(user,firestoreSDK.getFirestore(app),firestoreSDK):null;
  reviewContext=user?()=>reviewService(user,firestoreSDK.getFirestore(app),firestoreSDK):null;
  login.hidden=Boolean(user);enterRush.hidden=Boolean(user);account.hidden=!user;
  authStatus(user?'Signed in securely.':'Sign in or create your account with Google.');
  if(user){
   document.querySelector('#identity').textContent=user.email || 'Signed-in player';
   document.querySelector('#uid').textContent=user.uid;
   document.querySelector('#verified').textContent=user.emailVerified?'Email verified by Google.':'Email verification is still required before pilot access.';
   registration.start(user);
  }else{
   registration.reset();
   for(const id of ['identity','uid','verified']) document.getElementById(id).textContent='';
  }
  setLoginDisabled(false);
 });
 const startSignIn=async()=>{
  if(login.disabled)return;
  setLoginDisabled(true);authStatus('Finish signing in in the Google window…');
  try{await sdk.signInWithPopup(auth,provider);}
  catch(error){authStatus(errors[error.code] || 'Sign-in could not finish. Please try again in your regular browser.');}
  finally{setLoginDisabled(false);}
 };
 login.addEventListener('click',startSignIn);
 enterRush.addEventListener('click',startSignIn);
 document.querySelector('#logout').addEventListener('click',async()=>{
  try{registration.reset();await sdk.signOut(auth);}catch{status.textContent='Sign-out could not finish. Close this tab to clear this temporary session.';}
 });
}catch{
 authStatus('Sign-in could not load. Check your connection and reload this page.');
 setLoginDisabled(true);
}
