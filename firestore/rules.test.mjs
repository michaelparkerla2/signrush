import assert from "node:assert/strict";

import {before,after,beforeEach,test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {initializeTestEnvironment,assertSucceeds,assertFails} from '@firebase/rules-unit-testing';
import {doc,getDoc,setDoc,updateDoc,deleteDoc,collection,getDocs,query,limit,orderBy,writeBatch,serverTimestamp,Timestamp} from 'firebase/firestore';
let env;
before(async()=>{env=await initializeTestEnvironment({projectId:'demo-signrush-rules',firestore:{host:'127.0.0.1',port:8180,rules:await readFile(new URL('./firestore.rules',import.meta.url),'utf8')}});});
after(async()=>env?.cleanup());
beforeEach(async()=>{await env.clearFirestore();await env.withSecurityRulesDisabled(async c=>{
 for(const uid of ['alice','bob'])await setDoc(doc(c.firestore(),'pilotInvites',uid),{active:true});
});});
const db=(uid='alice',verified=true)=>env.authenticatedContext(uid,{email:'synthetic@example.test',email_verified:verified,firebase:{sign_in_provider:'google.com'}}).firestore();
const profile=()=>({uid:'alice',createdAt:serverTimestamp(),updatedAt:serverTimestamp(),status:'active',mode:'test',lastConsentId:null,consentAccepted:false});
async function create(d=db()){return setDoc(doc(d,'players/alice'),profile());}
function consent(d,id,action='accepted',extra={}){
 const b=writeBatch(d);
 b.set(doc(d,`players/alice/consents/${id}`),{action,termsVersion:'terms-2026-09-26-v3',disclosureVersion:'commercial-2026-09-26-v2',privacyVersion:'privacy-2026-09-26-v2',bundleHash:'3cd7079cf5b9a988b9480309dee50f633061ef8235865e504b9d82b0a3b33fde',uid:'alice',email:'synthetic@example.test',adultConfirmed:action==='accepted',publicDisplayAllowed:false,recordedAt:serverTimestamp(),...extra});
 b.update(doc(d,'players/alice'),{lastConsentId:id,consentAccepted:action==='accepted',updatedAt:serverTimestamp()});
 return b.commit();
}
test('only verified Google owner can register or read a player',async()=>{
 await assertFails(create(env.unauthenticatedContext().firestore()));
 await assertFails(create(db('alice',false)));await assertFails(create(db('mallory')));
 await assertSucceeds(create());await assertSucceeds(getDoc(doc(db(),'players/alice')));
 await assertFails(getDoc(doc(db('bob'),'players/alice')));
 await assertFails(getDocs(collection(db(),'players')));
});
test('registration cannot forge consent, cash, reward or privileged status',async()=>{
 for(const override of [{consentAccepted:true},{mode:'cash'},{points:500},{status:'admin'},{lastConsentId:'old'}])
  await assertFails(setDoc(doc(db(),'players/alice'),{...profile(),...override}));
});
test('accept and withdraw atomically with immutable history',async()=>{
 const d=db();await create(d);await assertSucceeds(consent(d,'one'));
 await assertSucceeds(consent(d,'two','withdrawn'));
 await assertSucceeds(getDoc(doc(d,'players/alice/consents/one')));
 await assertFails(updateDoc(doc(d,'players/alice/consents/one'),{action:'withdrawn'}));
 await assertFails(deleteDoc(doc(d,'players/alice/consents/one')));
});
test('partial writes and mismatched snapshots are rejected',async()=>{
 const d=db();await create(d);
 await assertFails(updateDoc(doc(d,'players/alice'),{lastConsentId:'orphan',consentAccepted:true,updatedAt:serverTimestamp()}));
 await assertFails(setDoc(doc(d,'players/alice/consents/orphan'),{action:'accepted',termsVersion:'terms-2026-09-26-v3',disclosureVersion:'commercial-2026-09-26-v2',privacyVersion:'privacy-2026-09-26-v2',bundleHash:'3cd7079cf5b9a988b9480309dee50f633061ef8235865e504b9d82b0a3b33fde',uid:'alice',email:'synthetic@example.test',adultConfirmed:true,publicDisplayAllowed:false,recordedAt:serverTimestamp()}));
 const b=writeBatch(d);b.set(doc(d,'players/alice/consents/mismatch'),{action:'withdrawn',termsVersion:'terms-2026-09-26-v3',disclosureVersion:'commercial-2026-09-26-v2',privacyVersion:'privacy-2026-09-26-v2',bundleHash:'3cd7079cf5b9a988b9480309dee50f633061ef8235865e504b9d82b0a3b33fde',uid:'alice',email:'synthetic@example.test',adultConfirmed:false,publicDisplayAllowed:false,recordedAt:serverTimestamp()});
 b.update(doc(d,'players/alice'),{lastConsentId:'mismatch',consentAccepted:true,updatedAt:serverTimestamp()});await assertFails(b.commit());
});
test('old versions, client times and event replay are rejected',async()=>{
 const d=db();await create(d);
 await assertFails(consent(d,'old','accepted',{termsVersion:'old'}));
 await assertFails(consent(d,'clock','accepted',{recordedAt:Timestamp.fromMillis(1)}));
 await consent(d,'one');await consent(d,'two','withdrawn');
 await assertFails(updateDoc(doc(d,'players/alice'),{lastConsentId:'one',consentAccepted:true,updatedAt:serverTimestamp()}));
});
test('players cannot change status, delete accounts or grant invitations',async()=>{
 const d=db();await create(d);await assertFails(updateDoc(doc(d,'players/alice'),{status:'active',mode:'cash'}));
 await assertFails(deleteDoc(doc(d,'players/alice')));
 await assertFails(setDoc(doc(d,'pilotInvites/mallory'),{active:true}));
 await assertFails(getDoc(doc(d,'pilotInvites/alice')));
});
test('suspension and revoked invitation fail closed',async()=>{
 const d=db();await create(d);
 await env.withSecurityRulesDisabled(c=>updateDoc(doc(c.firestore(),'players/alice'),{status:'suspended'}));
 await assertFails(consent(d,'accept'));await assertSucceeds(consent(d,'withdraw','withdrawn'));
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'pilotInvites/alice'),{active:false}));
 await assertFails(getDoc(doc(d,'players/alice')));await assertFails(consent(d,'again','withdrawn'));
});
test('hidden prompts, answers and rewards remain inaccessible',async()=>{
 for(const path of ['prompts/example','heldoutAnswers/example','rewards/alice','exports/example']){
  await assertFails(getDoc(doc(db(),path)));await assertFails(setDoc(doc(db(),path),{value:'guess'}));
 }
});

test('signing requires current consent and only the player can read a job',async()=>{
 const d=db();await create(d);const ref=doc(d,'signingJobs/alice');
 const job={uid:'alice',state:'requested',requestedAt:serverTimestamp()};
 await assertFails(setDoc(ref,job));await consent(d,'join');await assertSucceeds(setDoc(ref,job));
 await assertSucceeds(getDoc(ref));await assertFails(getDoc(doc(db('bob'),'signingJobs/alice')));
 await assertFails(getDocs(collection(d,'signingJobs')));await assertFails(deleteDoc(ref));
 await assertFails(updateDoc(ref,{state:'assigned',prompt:'cheat'}));
});
test('only bounded upload metadata can be added to a server assignment',async()=>{
 const d=db();await create(d);await consent(d,'join');const ref=doc(d,'signingJobs/alice');
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'signingJobs/alice'),{uid:'alice',state:'assigned',assignmentId:'test',prompt:'Hello.'}));
 const fields={state:'upload_requested',size:100,mime:'video/webm',sha256:'a'.repeat(64)};
 for(const extra of [{size:8388609},{size:0},{mime:'text/html'},{sha256:'bad'},{prompt:'changed'},{assignmentId:'other'},{uploadURL:'forged'}])await assertFails(updateDoc(ref,{...fields,...extra}));
 await assertSucceeds(updateDoc(ref,fields));await assertFails(updateDoc(ref,{state:'saved'}));
 await assertFails(updateDoc(ref,{state:'requested'}));
});
test('upload completion cannot approve quality or earn rewards and withdrawal blocks writes',async()=>{
 const d=db();await create(d);await consent(d,'join');const ref=doc(d,'signingJobs/alice');
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'signingJobs/alice'),{uid:'alice',state:'uploading',assignmentId:'test'}));
 await assertFails(updateDoc(ref,{state:'saved',points:30}));await assertSucceeds(updateDoc(ref,{state:'submitted'}));
 await consent(d,'withdraw','withdrawn');await assertFails(getDoc(ref));
 await assertFails(updateDoc(ref,{state:'requested'}));
 for(const path of ['pilotRecordings/test','pilotLimits/signing-v1','corpusCoverage/daily-use-v1','corpusPolicy/daily-use-v1','corpusSigners/alice'])await assertFails(getDoc(doc(d,path)));
});

test('review requests are private and cannot select a recording or reveal references',async()=>{
 const d=db();await create(d);const ref=doc(d,'reviewJobs/alice');const job={uid:'alice',state:'requested',requestedAt:serverTimestamp()};
 await assertFails(setDoc(ref,job));await consent(d,'join');
 await assertFails(setDoc(ref,{...job,recordingId:'chosen'}));await assertSucceeds(setDoc(ref,job));
 await assertSucceeds(getDoc(ref));await assertFails(getDoc(doc(db('bob'),'reviewJobs/alice')));
 await assertFails(getDocs(collection(d,'reviewJobs')));await assertFails(updateDoc(ref,{state:'assigned'}));
 for(const path of ['pilotReviews/secret','pilotRecordings/secret','pilotActivity/alice'])await assertFails(getDoc(doc(d,path)));
});
test('a review answer can be submitted once but cannot forge consensus or change the video',async()=>{
 const d=db();await create(d);await consent(d,'join');const ref=doc(d,'reviewJobs/alice');
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'reviewJobs/alice'),{uid:'alice',state:'assigned',reviewId:'opaque',playbackURL:'private'}));
 const answer={state:'submitted',quality:'good',text:'An independent interpretation.',submittedAt:serverTimestamp()};
 for(const extra of [{reviewId:'other'},{playbackURL:'forged'},{score:100},{text:''},{text:'x'.repeat(1001)}])await assertFails(updateDoc(ref,{...answer,...extra}));
 await assertSucceeds(updateDoc(ref,answer));await assertFails(updateDoc(ref,{text:'changed'}));await assertFails(updateDoc(ref,{state:'pending'}));
 await assertFails(deleteDoc(ref));
});
test('review refresh is restricted and withdrawal blocks requests',async()=>{
 const d=db();await create(d);await consent(d,'join');const ref=doc(d,'reviewJobs/alice');
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'reviewJobs/alice'),{uid:'alice',state:'assigned',reviewId:'opaque'}));
 await assertSucceeds(updateDoc(ref,{state:'refresh_requested'}));await assertFails(updateDoc(ref,{state:'requested'}));
 await consent(d,'withdraw','withdrawn');await assertFails(getDoc(ref));
 await assertFails(updateDoc(ref,{state:'submitted',quality:'good',text:'guess',submittedAt:serverTimestamp()}));
});
test('test points are owner-readable and cannot be forged',async()=>{
 await env.withSecurityRulesDisabled(async c=>{
  await setDoc(doc(c.firestore(),'playerRewards/alice'),{points:12,mode:'test'});
 });
 await assertSucceeds(getDoc(doc(db(),'playerRewards/alice')));
 await assertFails(getDoc(doc(db('bob'),'playerRewards/alice')));
 await assertFails(updateDoc(doc(db(),'playerRewards/alice'),{points:5000}));
 await assertFails(setDoc(doc(db(),'rewardEvents/fake'),{uid:'alice',points:5000}));
 await assertFails(getDocs(collection(db(),'playerRewards')));
});
test('completed tasks can be replaced but in-flight submissions cannot',async()=>{
 const d=db();await create(d);await consent(d,'join');
 const request={uid:'alice',state:'requested',requestedAt:serverTimestamp()};
 for(const [collection,done] of [['signingJobs','saved'],['reviewJobs','pending']]){
  const ref=doc(d,collection,'alice');
  await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),collection,'alice'),{uid:'alice',state:'submitted'}));
  await assertFails(setDoc(ref,request));
  await env.withSecurityRulesDisabled(c=>updateDoc(doc(c.firestore(),collection,'alice'),{state:done}));
  await assertSucceeds(setDoc(ref,request));
 }
});
test('dashboard is private and server-controlled',async()=>{
 const d=db();await create(d);await consent(d,'join');
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'playerDashboard/alice'),{pending:1,mode:'test'}));
 await assertSucceeds(getDoc(doc(d,'playerDashboard/alice')));
 await assertFails(getDoc(doc(db('bob'),'playerDashboard/alice')));
 await assertFails(setDoc(doc(d,'playerDashboard/alice'),{approved:99}));
});

test('public Google registration needs no invite but consent and isolation still apply',async()=>{
 const d=db('new-player');const ref=doc(d,'players/new-player');
 await assertSucceeds(setDoc(ref,{...profile(),uid:'new-player'}));
 await assertSucceeds(getDoc(ref));
 await assertFails(getDoc(doc(d,'players/alice')));
 await assertFails(setDoc(doc(d,'signingJobs/new-player'),{uid:'new-player',state:'requested',requestedAt:serverTimestamp()}));
 const b=writeBatch(d);
 b.set(doc(d,'players/new-player/consents/join'),{action:'accepted',termsVersion:'terms-2026-09-26-v3',disclosureVersion:'commercial-2026-09-26-v2',privacyVersion:'privacy-2026-09-26-v2',bundleHash:'3cd7079cf5b9a988b9480309dee50f633061ef8235865e504b9d82b0a3b33fde',uid:'new-player',email:'synthetic@example.test',adultConfirmed:true,publicDisplayAllowed:false,recordedAt:serverTimestamp()});
 b.update(ref,{consentAccepted:true,lastConsentId:'join',updatedAt:serverTimestamp()});
 await assertSucceeds(b.commit());
 for(const kind of ['signingJobs','reviewJobs'])await assertSucceeds(setDoc(doc(d,kind,'new-player'),{uid:'new-player',state:'requested',requestedAt:serverTimestamp()}));
 for(const path of ['pilotRecordings/private','heldoutAnswers/private','pilotInvites/new-player'])await assertFails(getDoc(doc(d,path)));
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'pilotInvites/new-player'),{active:false}));
 await assertFails(getDoc(ref));await assertFails(getDoc(doc(d,'reviewJobs/new-player')));
});
test('verified non-Google tokens cannot enroll',async()=>{
 const d=env.authenticatedContext('new-player',{email_verified:true,firebase:{sign_in_provider:'password'}}).firestore();
 await assertFails(setDoc(doc(d,'players/new-player'),{...profile(),uid:'new-player'}));
});

test('payout preferences are owner-only, validated and never an award or verified account',async()=>{
 const d=db();await create(d);const ref=doc(d,'payoutPreferences/alice');
 const value={method:'paypal',destination:'synthetic@example.com',usResident:false,version:1,updatedAt:serverTimestamp()};
 await assertFails(setDoc(ref,value));await consent(d,'join');await assertSucceeds(setDoc(ref,value));
 await assertSucceeds(getDoc(ref));await assertFails(getDoc(doc(db('bob'),'payoutPreferences/alice')));
 await assertFails(getDocs(collection(d,'payoutPreferences')));await assertFails(deleteDoc(doc(db('bob'),'payoutPreferences/alice')));
 for(const extra of [{destination:'invalid'},{verified:true},{status:'verified'},{balance:5000},{method:'zelle'},{updatedAt:Timestamp.fromMillis(1)},{usResident:true}])await assertFails(setDoc(ref,{...value,...extra}));
 await assertSucceeds(setDoc(ref,{...value,method:'venmo',destination:'synthetic-user',usResident:true}));
 await assertFails(setDoc(ref,{...value,method:'venmo',destination:'synthetic-user',usResident:false}));
 await assertFails(setDoc(ref,{...value,method:'venmo',destination:'https://venmo.com/user',usResident:true}));
 await consent(d,'withdraw','withdrawn');await assertFails(setDoc(ref,value));await assertSucceeds(getDoc(ref));await assertSucceeds(deleteDoc(ref));
});

test('avatar profiles are private and leaderboard scores cannot be invented',async()=>{
 const d=db();await create(d);await consent(d,'one');
 const p={alias:'Swift Signer',avatar:'sprout',listed:true,updatedAt:serverTimestamp()};
 const e={alias:p.alias,avatar:p.avatar,points:0,updatedAt:serverTimestamp()};
 await assertFails(setDoc(doc(d,'leaderboard/alice'),e));
 const join=writeBatch(d);join.set(doc(d,'gameProfiles/alice'),p);join.set(doc(d,'leaderboard/alice'),e);await assertSucceeds(join.commit());
 await assertFails(getDoc(doc(db('bob'),'gameProfiles/alice')));
 await assertFails(setDoc(doc(d,'gameProfiles/alice'),{...p,avatar:'external-url'}));
 await assertFails(setDoc(doc(d,'leaderboard/alice'),{...e,points:999}));
 await assertFails(setDoc(doc(d,'leaderboard/alice'),{...e,email:'a@b.co'}));
 await assertFails(setDoc(doc(d,'leaderboard/bob'),e));
 await env.withSecurityRulesDisabled(c=>setDoc(doc(c.firestore(),'playerRewards/alice'),{points:35,mode:'test'}));
 await assertSucceeds(setDoc(doc(d,'leaderboard/alice'),{...e,points:35}));
 await assertFails(setDoc(doc(d,'leaderboard/alice'),{...e,points:0}));
 await assertFails(getDocs(collection(d,'leaderboard')));
 await assertSucceeds(getDocs(query(collection(d,'leaderboard'),orderBy('points','desc'),limit(50))));
 await assertFails(getDocs(query(collection(env.unauthenticatedContext().firestore(),'leaderboard'),limit(50))));
 await assertFails(setDoc(doc(d,'gameProfiles/alice'),{...p,listed:false}));
 const leave=writeBatch(d);leave.set(doc(d,'gameProfiles/alice'),{...p,listed:false});leave.delete(doc(d,'leaderboard/alice'));await assertSucceeds(leave.commit());
 await assertFails(setDoc(doc(d,'leaderboard/alice'),{...e,points:35}));
});
test('withdrawal atomically removes a public leaderboard entry',async()=>{
 const d=db();await create(d);await consent(d,'one');
 const join=writeBatch(d);join.set(doc(d,'gameProfiles/alice'),{alias:'Tester',avatar:'nova',listed:true,updatedAt:serverTimestamp()});join.set(doc(d,'leaderboard/alice'),{alias:'Tester',avatar:'nova',points:0,updatedAt:serverTimestamp()});await join.commit();
 await assertFails(consent(d,'two','withdrawn'));
 const b=writeBatch(d);b.set(doc(d,'players/alice/consents/two'),{action:'withdrawn',termsVersion:'terms-2026-09-26-v3',disclosureVersion:'commercial-2026-09-26-v2',privacyVersion:'privacy-2026-09-26-v2',bundleHash:'3cd7079cf5b9a988b9480309dee50f633061ef8235865e504b9d82b0a3b33fde',uid:'alice',email:'synthetic@example.test',adultConfirmed:false,publicDisplayAllowed:false,recordedAt:serverTimestamp()});b.update(doc(d,'players/alice'),{lastConsentId:'two',consentAccepted:false,updatedAt:serverTimestamp()});b.delete(doc(d,'leaderboard/alice'));b.delete(doc(d,'gameProfiles/alice'));await assertSucceeds(b.commit());
 await assertFails(setDoc(doc(d,'leaderboard/alice'),{alias:'Tester',avatar:'nova',points:0,updatedAt:serverTimestamp()}));
});

test('adjudication history stays private and revealed prompt cannot be used to rewrite a saved answer',async()=>{
 const d=db();await create(d);await consent(d,'one');
 await env.withSecurityRulesDisabled(async c=>{
  await setDoc(doc(c.firestore(),'reviewJobs/alice'),{uid:'alice',state:'pending',text:'Original blind answer',referencePrompt:'Intended meaning'});
  await setDoc(doc(c.firestore(),'meaningAssessmentHistory/finding'),{verdict:'unrelated'});
 });
 await assertSucceeds(getDoc(doc(d,'reviewJobs/alice')));
 await assertFails(updateDoc(doc(d,'reviewJobs/alice'),{text:'Intended meaning'}));
 await assertFails(updateDoc(doc(d,'reviewJobs/alice'),{referencePrompt:'Forged'}));
 await assertFails(getDoc(doc(d,'meaningAssessmentHistory/finding')));
 await assertFails(setDoc(doc(d,'meaningAssessmentHistory/forged'),{verdict:'equivalent'}));
});

test('one agreement stores current evidence and optional private background atomically',async()=>{
 const {firestoreRegistration}=await import('../web/firestore-registration.mjs');
 const {pilotDisclosure}=await import('../web/pilot-disclosure.mjs');
 const sdk=await import('firebase/firestore');
 const transport=firestoreRegistration({currentUser:{uid:'alice',email:'synthetic@example.test',emailVerified:true}},db(),sdk,pilotDisclosure);
 const account=await transport('/v1/account',{method:'POST'});assert.equal(account.ok,true);
 const payload={accept:true,terms_version:pilotDisclosure.terms_version,disclosure_version:pilotDisclosure.disclosure_version,adultConfirmed:true,background:{aslExperience:'fluent',hearingIdentity:'deaf',aslRole:'translator'}};
 const missing=await transport('/v1/consent',{method:'POST',body:JSON.stringify({...payload,adultConfirmed:false})});assert.equal(missing.ok,false);
 const saved=await transport('/v1/consent',{method:'POST',body:JSON.stringify(payload)});assert.equal(saved.ok,true);
 const profile=(await getDoc(doc(db(),'players/alice'))).data();
 const receipt=(await getDoc(doc(db(),`players/alice/consents/${profile.lastConsentId}`))).data();
 assert.equal(receipt.bundleHash,pilotDisclosure.bundle_hash);assert.equal(receipt.adultConfirmed,true);assert.equal(receipt.publicDisplayAllowed,false);
 assert.equal((await getDoc(doc(db(),'contributorProfiles/alice'))).data().aslRole,'translator');
 await assertFails(getDoc(doc(db('bob'),'contributorProfiles/alice')));
 await assertFails(updateDoc(doc(db(),`players/alice/consents/${profile.lastConsentId}`),{adultConfirmed:false}));
 const stopped=await transport('/v1/consent',{method:'POST',body:JSON.stringify({...payload,accept:false})});assert.equal(stopped.ok,true);
 assert.equal((await getDoc(doc(db(),'players/alice'))).data().consentAccepted,false);
 assert.deepEqual((await getDoc(doc(db(),`players/alice/consents/${profile.lastConsentId}`))).data(),receipt);
 await assertFails(setDoc(doc(db(),'signingJobs/alice'),{state:'requested',requestedAt:serverTimestamp()}));

});
test('old consent, forged release and missing adulthood cannot unlock participation',async()=>{
 const d=db();await create(d);
 for(const extra of [{adultConfirmed:false},{bundleHash:'forged'},{termsVersion:'pilot-v1'},{publicDisplayAllowed:true}])await assertFails(consent(d,'bad'+Object.keys(extra)[0],'accepted',extra));
 await env.withSecurityRulesDisabled(async c=>{
  await setDoc(doc(c.firestore(),'players/alice/consents/old'),{action:'accepted',termsVersion:'pilot-v1',disclosureVersion:'training-v1'});
  await updateDoc(doc(c.firestore(),'players/alice'),{lastConsentId:'old',consentAccepted:true});
 });
 await assertFails(setDoc(doc(d,'signingJobs/alice'),{uid:'alice',state:'requested',requestedAt:serverTimestamp()}));
});
test('privacy requests are private and may be filed after consent withdrawal',async()=>{
 const d=db();await create(d);await consent(d,'one');await consent(d,'two','withdrawn');
 await assertSucceeds(setDoc(doc(d,'privacyRequests/request'),{uid:'alice',kind:'deletion',details:'Please review my data.',status:'requested',createdAt:serverTimestamp()}));
 await assertFails(getDoc(doc(db('bob'),'privacyRequests/request')));
 await assertFails(updateDoc(doc(d,'privacyRequests/request'),{status:'completed'}));
});

test('reports require an assigned video and a separate valid report reason',async()=>{
 const d=db();await create(d);await consent(d,'one');
 await env.withSecurityRulesDisabled(async c=>{await setDoc(doc(c.firestore(),'reviewJobs/alice'),{uid:'alice',state:'assigned',reviewId:'opaque'});});
 await assertFails(updateDoc(doc(d,'reviewJobs/alice'),{state:'submitted',text:'made-up translation',quality:'poor',reportReason:'not_signing',submittedAt:serverTimestamp()}));
 await assertFails(updateDoc(doc(d,'reviewJobs/alice'),{state:'submitted',text:'',quality:'poor',reportReason:'disagree',submittedAt:serverTimestamp()}));
 await assertSucceeds(updateDoc(doc(d,'reviewJobs/alice'),{state:'submitted',text:'',quality:'poor',reportReason:'not_signing',submittedAt:serverTimestamp()}));
 await assertFails(updateDoc(doc(d,'reviewJobs/alice'),{reportReason:'unusable_quality'}));
});
test('third strike cannot be cleared by the client and blocks both task types',async()=>{
 const d=db();await create(d);await consent(d,'one');
 await env.withSecurityRulesDisabled(async c=>{
  await updateDoc(doc(c.firestore(),'players/alice'),{status:'cancelled'});
  await setDoc(doc(c.firestore(),'playerModeration/alice'),{strikes:3,blocked:true});
 });
 await assertSucceeds(getDoc(doc(d,'playerModeration/alice')));
 await assertFails(updateDoc(doc(d,'playerModeration/alice'),{strikes:0,blocked:false}));
 await assertFails(updateDoc(doc(d,'players/alice'),{status:'active'}));
 for(const collection of ['signingJobs','reviewJobs'])await assertFails(setDoc(doc(d,collection+'/alice'),{uid:'alice',state:'requested',requestedAt:serverTimestamp()}));
 await assertFails(getDoc(doc(db('bob'),'playerModeration/alice')));
});
