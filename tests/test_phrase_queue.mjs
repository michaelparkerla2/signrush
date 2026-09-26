import {test} from 'node:test';
import assert from 'node:assert/strict';
import {presentQueue} from '../web/phrase-queue.mjs';
test('missing or legacy dashboards never invent available tasks',()=>{
 for(const value of [null,{signAvailable:30,catalogBatch:'daily-use-v1'},{signAvailable:0}]){
  assert.equal(presentQueue(value).signAvailable,null);assert.equal(presentQueue(value).queueKnown,false);
 }
});
test('current server counts preserve exhaustion and in-progress jobs independently',()=>{
 const empty=presentQueue({signAvailable:0,catalogBatch:'daily-use-v1',catalogSize:200,signInProgress:true});
 assert.equal(empty.signAvailable,0);assert.equal(empty.queueKnown,true);assert.equal(empty.signInProgress,true);
 assert.equal(presentQueue({signAvailable:200,catalogBatch:'daily-use-v1',catalogSize:200}).signAvailable,200);
});
