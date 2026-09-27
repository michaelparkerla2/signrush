import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DAILY_PHRASES} from '../web/daily-phrases.mjs';
import {availableCount,choosePhrase,coverageCounts,presentQueue} from '../web/phrase-queue.mjs';
test('daily phrases stay available until a player has seen them or coverage is full',()=>{
 assert.equal(DAILY_PHRASES.length,30);
 assert.equal(availableCount(DAILY_PHRASES,new Set(),{},0),30);
 assert.equal(availableCount(DAILY_PHRASES,new Set(['DAILY-001']),{'DAILY-002':10},0),28);
 assert.equal(availableCount(DAILY_PHRASES,new Set(),{},300),0);
 const chosen=choosePhrase(DAILY_PHRASES,new Set(['DAILY-001']),{'DAILY-002':1,'DAILY-003':0},()=>0);
 assert.equal(chosen.id,'DAILY-003');
 assert.equal(choosePhrase(DAILY_PHRASES,new Set(DAILY_PHRASES.map(phrase=>phrase.id)),{},()=>0),null);
 assert.deepEqual(coverageCounts({'DAILY-001':2,claimId:'abc',note:'skip'}),{'DAILY-001':2});
});
test('missing batch marker does not hide the catalog behind a stale zero',()=>{
 assert.equal(presentQueue(null).signAvailable,30);
 assert.equal(presentQueue({signAvailable:0,signInProgress:true}).signAvailable,30);
 assert.equal(presentQueue({signAvailable:0,catalogBatch:'daily-use-v1'}).signAvailable,0);
 assert.equal(presentQueue({signAvailable:0,signInProgress:true,catalogBatch:'daily-use-v1'}).signAvailable,1);
});
