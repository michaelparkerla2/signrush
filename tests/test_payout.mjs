import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Payout,preference,masked} from '../web/payout.mjs';
const valid=()=>preference('paypal',' test@example.com ','test@example.com',false,true);
function fixture(){const els=new Map();const root={querySelector(id){if(!els.has(id))els.set(id,{value:'',textContent:'',hidden:false,disabled:false,checked:false,focus(){}});return els.get(id);}};return new Payout(root);}
function fill(p){p.edit();p.el('payout-method').value='paypal';p.el('payout-destination').value='test@example.com';p.el('payout-confirm').value='test@example.com';p.el('payout-own').checked=true;}
test('recipient validation rejects mismatches and unsupported details',()=>{
 assert.equal(valid().destination,'test@example.com');assert.equal(preference('venmo','@example-user','example-user',true,true).destination,'example-user');
 for(const args of [['paypal','x','x',false,true],['paypal','a@b.co','c@b.co',false,true],['venmo','example-user','example-user',false,true],['paypal','a@b.co','a@b.co',false,false],['zelle','a@b.co','a@b.co',false,true]])assert.throws(()=>preference(...args));
 assert.equal(masked(valid()),'te•••@example.com');
});
test('failed loads never present an empty preference ready to overwrite',async()=>{const p=fixture();await p.connect({load:async()=>{throw Error();}});assert.equal(p.el('payout-edit').disabled,true);assert.equal(p.el('payout-retry').hidden,false);p.edit();assert.equal(p.editing,false);});
test('saving requires server completion, prevents double submits and preserves failed form',async()=>{
 const p=fixture();let reject,count=0;await p.connect({load:async()=>null,save:()=>{count++;return new Promise((_,r)=>reject=r);}});fill(p);
 const first=p.save();await p.save();assert.equal(count,1);assert.equal(p.saved,null);reject(Error());await first;
 assert.equal(p.editing,true);assert.equal(p.el('payout-destination').value,'test@example.com');assert.match(p.el('payout-status').textContent,/wasn’t confirmed/);
});
test('save displays masked unverified detail and removal clears it after acknowledgement',async()=>{
 const p=fixture();let stored=null;await p.connect({load:async()=>null,save:async d=>stored=d,remove:async()=>stored=null});fill(p);await p.save();
 assert.deepEqual(stored,valid());assert.equal(p.editing,false);assert.match(p.el('payout-detail').textContent,/Not verified/);assert.equal(p.el('payout-destination').value,'');await p.remove();assert.equal(p.saved,null);assert.equal(stored,null);
});
test('signout clears identifiers and ignores delayed load or save completion',async()=>{
 const p=fixture();let resolve;const loading=p.connect({load:()=>new Promise(r=>resolve=r)});p.reset();resolve(valid());await loading;assert.equal(p.saved,null);
 await p.connect({load:async()=>null,save:()=>new Promise(r=>resolve=r)});fill(p);const saving=p.save();p.reset();resolve();await saving;
 assert.equal(p.saved,null);assert.equal(p.el('payout-destination').value,'');assert.equal(p.el('payout-status').textContent,'');
});
