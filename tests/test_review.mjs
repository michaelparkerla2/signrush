import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Review,validPlaybackURL} from '../web/review.mjs';
function fixture(){
 const els=new Map(),root={hidden:true,dataset:{},querySelector(s){if(!els.has(s))els.set(s,{hidden:true,value:'',textContent:'',pause(){},removeAttribute(){}});return els.get(s);}};
 const review=new Review(root);let next,calls=[];
 review.connect({watch:n=>{next=n;return()=>{};},request:async()=>calls.push('request'),refresh:async()=>calls.push('refresh'),submit:async t=>calls.push(t)});
 return {review,els,next,calls};
}
test('only fixed short-lived private playback URLs are accepted',()=>{
 const valid='https://storage.googleapis.com/umi-signrush-raw/pilot/playback/'+'a'.repeat(32)+'/silent-v1.mp4?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Signature=test&X-Goog-Expires=300';
 assert.equal(validPlaybackURL(valid),true);
 for(const bad of [valid.replace('playback','recordings'),valid.replace('https:','http:'),valid.replace('storage.googleapis.com','evil.example'),valid.replace('=300','=9999')])assert.equal(validPlaybackURL(bad),false);
});
test('empty queue explains self-review exclusion and allows a retry',async()=>{const {review,els,next,calls}=fixture();next({state:'empty'});assert.match(els.get('#review-status').textContent,/own recordings/);await review.request();assert.deepEqual(calls,['request']);});
test('review submission trims text and prevents double clicks',async()=>{
 const {review,els,next,calls}=fixture();next({state:'assigned',playbackURL:'invalid'});els.get('#review-answer').value='  Meaning  ';review.el('review-quality').value='good';
 await Promise.all([review.submit(),review.submit()]);assert.deepEqual(calls,['Meaning']);
 next({state:'pending'});assert.equal(els.get('#review-complete').hidden,false);assert.equal(els.get('#review-answer').value,'');
});
test('signout suppresses a late job and clears the video',()=>{const {review,next}=fixture();review.reset();next({state:'assigned',playbackURL:'invalid'});assert.equal(review.active,false);assert.equal(review.job,null);});
test('quality must be selected before submitting and owner tests show no reward',async()=>{
 const {review,next,calls,els}=fixture();next({state:'assigned',playbackURL:'invalid'});
 review.el('review-answer').value='Meaning';await review.submit();assert.equal(calls.length,0);
 next({state:'pending',outcome:{status:'test_only',independentReviews:0}});
 assert.equal(els.get('#review-outcome').textContent,'Test review saved');assert.match(els.get('#review-progress').textContent,/earns no points/);
});

test('known empty queue answers immediately without creating an assignment request',async()=>{const {review,calls,els}=fixture();review.service.availability=async()=>false;await review.request();assert.deepEqual(calls,[]);assert.equal(review.job.state,'empty');assert.equal(els.get('#review-loading').hidden,true);});
test('unknown availability still requests server assignment; signout cancels late preflight',async()=>{const {review,calls}=fixture();review.service.availability=async()=>null;await review.request();assert.deepEqual(calls,['request']);let resolve;review.service.availability=()=>new Promise(r=>resolve=r);const pending=review.request();review.reset();resolve(false);await pending;assert.equal(review.job,null);assert.deepEqual(calls,['request']);});
test('loading indicator follows assignment state and stops on empty or reset',()=>{const {review,next,els}=fixture();next({state:'requested'});assert.equal(els.get('#review-loading').hidden,false);assert.match(els.get('#review-status').textContent,/without refreshing/);next({state:'empty'});assert.equal(els.get('#review-loading').hidden,true);next({state:'preparing'});review.reset();assert.equal(els.get('#review-loading').hidden,true);});
test('slow assignment stops spinner after 30 seconds and recovers on server response',t=>{t.mock.timers.enable({apis:['setTimeout']});const {review,next,els}=fixture();next({state:'requested'});t.mock.timers.tick(30000);assert.equal(els.get('#review-loading').hidden,true);assert.match(els.get('#review-status').textContent,/longer than expected/);next({state:'empty'});assert.match(els.get('#review-status').textContent,/No eligible videos/);review.reset();});

test('stale, missing or future queue timestamps never block a fresh server request',async()=>{
 const {freshEmptyQueue}=await import('../web/review.mjs');
 const d={reviewAvailable:0,reviewInProgress:false};
 assert.equal(freshEmptyQueue(d,100000),false);
 assert.equal(freshEmptyQueue({...d,updatedAt:{toMillis:()=>1000}},100000),false);
 assert.equal(freshEmptyQueue({...d,updatedAt:{toMillis:()=>100001}},100000),false);
 assert.equal(freshEmptyQueue({...d,updatedAt:{toMillis:()=>90000}},100000),true);
 assert.equal(freshEmptyQueue({...d,reviewInProgress:true,updatedAt:{toMillis:()=>90000}},100000),false);
});
