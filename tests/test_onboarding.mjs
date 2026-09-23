import test from 'node:test';
import assert from 'node:assert/strict';
import {Onboarding} from '../web/onboarding.mjs';
const user={emailVerified:true,getIdToken:async()=> 'synthetic-token'};
const disclosure={notice:'Training use, including failed attempts.',rules:['Test rule'],terms_version:'pilot-v1',disclosure_version:'training-v1'};
const ok=data=>({ok:true,json:async()=>data});
function setup(responses){
 const states=[],calls=[];
 const controller=new Onboarding(s=>states.push(s),async(path,options)=>{
  calls.push({path,options});
  const response=responses.shift();
  if(response instanceof Error)throw response;
  return typeof response==='function'?response():response;
 });
 return {controller,states,calls};
}
test('registration requires explicit consent and confirms the exact versions',async()=>{
 const {controller,calls}=setup([ok({consent_required:true,mode:'test'}),ok(disclosure),ok({accepted:true})]);
 await controller.start(user);
 assert.equal(controller.state.phase,'consent');assert.equal(calls.length,2);
 await controller.consent(true);
 assert.equal(controller.state.phase,'ready');
 assert.deepEqual(JSON.parse(calls[2].options.body),{accept:true,terms_version:'pilot-v1',disclosure_version:'training-v1'});
 for(const call of calls){
  assert.equal(call.options.headers.Authorization,'Bearer synthetic-token');
  assert.equal(call.options.redirect,'error');assert.equal(call.options.credentials,'omit');
  assert.ok(!call.path.includes('token'));
 }
});
test('an unavailable server never claims registration or agreement saved',async()=>{
 const {controller}=setup([{ok:false,status:501}]);await controller.start(user);
 assert.equal(controller.state.phase,'unavailable');assert.match(controller.state.message,/No saved agreement/);
});
test('save failure stays unconfirmed and requires a fresh account check',async()=>{
 const {controller}=setup([ok({consent_required:true,mode:'test'}),ok(disclosure),{ok:false,status:503}]);
 await controller.start(user);await controller.consent(true);
 assert.equal(controller.state.phase,'unavailable');
});
test('accepted accounts can withdraw and must agree again to resume',async()=>{
 const {controller}=setup([ok({consent_required:false,mode:'test'}),ok(disclosure),ok({accepted:false})]);
 await controller.start(user);assert.equal(controller.state.phase,'ready');
 await controller.consent(false);assert.equal(controller.state.phase,'consent');assert.equal(controller.state.withdrawn,true);
});
test('sign-out suppresses an in-flight enrollment response',async()=>{
 let release;
 const {controller,calls}=setup([()=>new Promise(resolve=>{release=resolve;})]);
 const pending=controller.start(user);
 await new Promise(resolve=>setImmediate(resolve));
 controller.reset();release(ok({consent_required:false,mode:'test'}));await pending;
 assert.equal(controller.state.phase,'signed-out');assert.equal(calls.length,1);
});
test('sign-out during token refresh prevents any HTTP request',async()=>{
 let release;
 const {controller,calls}=setup([]);
 const pending=controller.start({emailVerified:true,getIdToken:()=>new Promise(resolve=>{release=resolve;})});
 controller.reset();release('synthetic-token');await pending;
 assert.equal(calls.length,0);assert.equal(controller.state.phase,'signed-out');
});
test('unverified or restricted users never reach consent',async()=>{
 const a=setup([]);await a.controller.start({...user,emailVerified:false});assert.equal(a.calls.length,0);
 const b=setup([{ok:false,status:403}]);await b.controller.start(user);assert.equal(b.controller.state.phase,'unavailable');assert.match(b.controller.state.message,/restricted accounts/);
});
test('duplicate clicks submit only one consent request',async()=>{
 let release;
 const {controller,calls}=setup([ok({consent_required:true,mode:'test'}),ok(disclosure),()=>new Promise(resolve=>{release=resolve;})]);
 await controller.start(user);const first=controller.consent(true);
 await new Promise(resolve=>setImmediate(resolve));await controller.consent(true);
 release(ok({accepted:true}));await first;assert.equal(calls.length,3);
});
