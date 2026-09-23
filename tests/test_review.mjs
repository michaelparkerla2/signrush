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
