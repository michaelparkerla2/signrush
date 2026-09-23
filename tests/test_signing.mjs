import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Signing,validUploadURL,recordingType} from '../web/signing.mjs';
function fixture(mediaDevices){
 const els=new Map();const root={hidden:true,dataset:{},querySelector(selector){if(!els.has(selector))els.set(selector,{hidden:true,checked:false,disabled:false,textContent:'',classList:{add(){},remove(){}},removeAttribute(){},play:async()=>{}});return els.get(selector);}};
 const signing=new Signing(root,{mediaDevices,Recorder:{isTypeSupported:()=>true},fetcher:async()=>{throw Error('unexpected network');}});
 let next;const service={watch:(n)=>{next=n;return()=>{};},request:async()=>{},prepare:async()=>{},finish:async()=>{}};
 signing.connect(service);next({state:'assigned',prompt:'Synthetic test phrase'});return {signing,els,service,next};
}
test('only fixed private Google upload endpoint is accepted',()=>{
 const good='https://storage.googleapis.com/upload/storage/v1/b/umi-signrush-raw/o?upload_id=test';
 assert.equal(validUploadURL(good),true);
 for(const bad of [good.replace('https:','http:'),good.replace('storage.googleapis.com','evil.example'),good.replace('umi-signrush-raw','other-bucket'),'javascript:alert(1)'])assert.equal(validUploadURL(bad),false);
});
test('late camera permission after signout stops every track',async()=>{
 let resolve,stopped=0;const {signing}=fixture({getUserMedia:()=>new Promise(r=>resolve=r)});
 const pending=signing.openCamera();signing.reset();resolve({getTracks:()=>[{stop:()=>stopped++}]});await pending;assert.equal(stopped,1);assert.equal(signing.stream,null);
});
test('camera asks for no audio and reset releases stream',async()=>{
 let constraints,stopped=0;const {signing}=fixture({getUserMedia:async c=>{constraints=c;return {getTracks:()=>[{stop:()=>stopped++}]};}});
 await signing.openCamera();assert.equal(constraints.audio,false);signing.reset();assert.equal(stopped,1);
});
test('permission rejection is recoverable without a recording',async()=>{
 const {signing,els}=fixture({getUserMedia:async()=>{throw Error('denied');}});await signing.openCamera();assert.equal(signing.busy,false);assert.equal(signing.blob,null);assert.match(els.get('#signing-status').textContent,/Camera access/);
});
test('submit does nothing without explicit framing confirmation',async()=>{
 const {signing,service}=fixture();let calls=0;service.prepare=async()=>calls++;signing.blob=new Blob(['synthetic']);await signing.submit();assert.equal(calls,0);signing.reset();
});
test('unsupported recorder selects no format',()=>assert.equal(recordingType({isTypeSupported:()=>false}),undefined));

test('the assigned phrase stays explicitly quoted while recording and reviewing',()=>{
 const {signing,els}=fixture();
 for(const recording of [false,true]){signing.recording=recording;signing.draw();assert.equal(els.get('#phrase-text').textContent,'“Synthetic test phrase”');assert.equal(els.get('#capture-surface').hidden,false);}
 signing.recording=false;signing.blob=new Blob(['take']);signing.draw();assert.equal(signing.root.dataset.phase,'review');assert.equal(els.get('#phrase-text').textContent,'“Synthetic test phrase”');signing.reset();
});

test('a just-saved take shows completion instead of the review controls',()=>{
 const {signing,els,next}=fixture();signing.blob=new Blob(['take']);
 next({state:'saved',prompt:'Synthetic test phrase',assignmentId:'test'});
 assert.equal(signing.root.dataset.phase,'saved');assert.equal(els.get('#submission-result').hidden,false);assert.equal(els.get('#submit-video').hidden,true);assert.equal(signing.blob,null);signing.reset();
});
