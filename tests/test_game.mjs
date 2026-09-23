import {test} from 'node:test';
import assert from 'node:assert/strict';
import {level,validProfile,gameService} from '../web/game.mjs';
test('trophies unlock only at earned-point thresholds',()=>{
 assert.equal(level(24).earned.length,0);assert.equal(level(25).earned[0].name,'First spark');assert.equal(level(100).earned.length,2);assert.equal(level(500).earned.length,4);assert.equal(level(-1).number,1);
 assert.throws(()=>validProfile('a@b.co','sprout',true));assert.throws(()=>validProfile('Tester','unknown',true));
});
test('leaderboard projection reads authoritative points and rechecks opt-in on every sync',async()=>{
 const rows=new Map([['gameProfiles/alice',{alias:'Tester',avatar:'sprout',listed:true}],['playerRewards/alice',{points:35}]]);
 const sdk={doc:(_,c,id)=>`${c}/${id}`,serverTimestamp:()=>123,runTransaction:(_,fn)=>fn({get:async ref=>({exists:()=>rows.has(ref),data:()=>rows.get(ref)}),set:(ref,d)=>rows.set(ref,d),delete:ref=>rows.delete(ref)})};
 const service=gameService({uid:'alice'},{},sdk);await service.sync();assert.equal(rows.get('leaderboard/alice').points,35);
 await service.save({alias:'New Name',avatar:'nova',listed:false,points:999});assert.equal(rows.has('leaderboard/alice'),false);
 await service.sync();assert.equal(rows.has('leaderboard/alice'),false);assert.equal(rows.get('gameProfiles/alice').points,undefined);
});
import {Game} from '../web/game.mjs';
test('signout suppresses late profile loads and clears the player editor',async()=>{
 const previous=globalThis.document;
 const element=()=>({children:[],dataset:{},value:'',checked:false,append(...c){this.children.push(...c);},replaceChildren(...c){this.children=c;},setAttribute(){},close(){this.open=false;},showModal(){this.open=true;}});
 globalThis.document={createElement:element};
 try{const elements=new Map();const root={querySelector:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);}};const g=new Game(root);let resolve;
  const loading=g.connect({load:()=>new Promise(r=>resolve=r),board:()=>()=>{},points:n=>{n(0);return()=>{};}});g.reset();resolve({alias:'Old Player',avatar:'nova',listed:true});await loading;
  assert.equal(g.profile,null);assert.equal(g.loaded,false);assert.equal(g.el('player-alias').value,'');assert.equal(g.el('edit-player').disabled,true);
 }finally{globalThis.document=previous;}
});
