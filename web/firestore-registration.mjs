// The existing onboarding controller uses this small transport for registration.
// All persisted decisions are confirmed by Firestore transactions + Security Rules.
export function firestoreRegistration(auth, db, sdk, disclosure) {
 const {doc,collection,runTransaction,serverTimestamp}=sdk;
 const response=data=>({ok:true,json:async()=>data});
 const fail=status=>({ok:false,status});
 const current=event=>event?.action==='accepted' && event.termsVersion===disclosure.terms_version && event.disclosureVersion===disclosure.disclosure_version;
 return async(path,options)=>{
  const user=auth.currentUser;
  if(!user)return fail(401);
  if(!user.emailVerified)return fail(403);
  const profile=doc(db,'players',user.uid);
  try {
   if(path==='/v1/consent' && options.method==='GET')return response(disclosure);
   if(path==='/v1/account' && options.method==='POST'){
    const result=await runTransaction(db,async tx=>{
     const snap=await tx.get(profile);
     if(!snap.exists()){
      tx.set(profile,{uid:user.uid,mode:'test',status:'active',createdAt:serverTimestamp(),updatedAt:serverTimestamp(),lastConsentId:null,consentAccepted:false});
      return {account_id:user.uid,mode:'test',consent_required:true};
     }
     const data=snap.data();
     if(data.status!=='active' || data.mode!=='test')throw Object.assign(new Error('blocked'),{code:'permission-denied'});
     const event=data.lastConsentId?(await tx.get(doc(db,'players',user.uid,'consents',data.lastConsentId))).data():null;
     return {account_id:user.uid,mode:'test',consent_required:!(data.consentAccepted && current(event))};
    });
    return response(result);
   }
   if(path==='/v1/consent' && options.method==='POST'){
    const body=JSON.parse(options.body);
    if(typeof body.accept!=='boolean' || body.terms_version!==disclosure.terms_version || body.disclosure_version!==disclosure.disclosure_version)return fail(422);
    const event=doc(collection(db,'players',user.uid,'consents'));
    await runTransaction(db,async tx=>{
     const snap=await tx.get(profile);
     if(!snap.exists() || (body.accept && snap.data().status!=='active'))throw Object.assign(new Error('blocked'),{code:'permission-denied'});
     tx.set(event,{action:body.accept?'accepted':'withdrawn',termsVersion:body.terms_version,disclosureVersion:body.disclosure_version,recordedAt:serverTimestamp()});
     tx.update(profile,{lastConsentId:event.id,consentAccepted:body.accept,updatedAt:serverTimestamp()});
     if(!body.accept){tx.delete(doc(db,'leaderboard',user.uid));tx.delete(doc(db,'gameProfiles',user.uid));}
    });
    return response({accepted:body.accept});
   }
   return fail(404);
  }catch(error){return fail(error.code==='permission-denied'?403:error.code==='unauthenticated'?401:503);}
 };
}
