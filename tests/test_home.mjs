import {test} from 'node:test';
import assert from 'node:assert/strict';
import {progress} from '../web/home.mjs';
test('stars use real test points and a distinct next milestone',()=>{
 assert.deepEqual(progress(0),{points:0,target:25,remaining:25,value:0});
 assert.deepEqual(progress(24),{points:24,target:25,remaining:1,value:24});
 assert.deepEqual(progress(25),{points:25,target:50,remaining:25,value:0});
 assert.equal(progress(-5).points,0);
});
import {Home} from '../web/home.mjs';
function fixture(){
 const elements=new Map();const root={hidden:true,classList:{add(){},remove(){}},querySelector(id){if(!elements.has(id))elements.set(id,{textContent:'',value:0,hidden:false,disabled:false,close(){this.open=false;},showModal(){this.open=true;},setAttribute(){}});return elements.get(id);}};
 const home=new Home(root);let points;
 home.connect({tasks(next){next({signAvailable:1,reviewAvailable:0,pending:1,approved:0,submitted:1});return()=>{};},points(next){points=next;return()=>{};}});
 return {home,points};
}
test('wallet displays live test points and signout clears and closes it',()=>{
 const {home,points}=fixture();points(37);home.el('cash-out').onclick();
 assert.equal(home.el('cash-wallet').open,true);assert.equal(home.el('wallet-test-points').textContent,'37');
 home.reset();assert.equal(home.el('cash-wallet').open,false);assert.equal(home.el('wallet-test-points').textContent,'—');
 points(99);assert.equal(home.el('wallet-test-points').textContent,'—');
});
test('opening wallet does not request any payment or award points',()=>{
 const {home,points}=fixture();points(0);home.el('cash-out').onclick();home.el('close-wallet').onclick();
 assert.equal(home.el('wallet-test-points').textContent,'0');assert.equal(home.previous,0);
});
