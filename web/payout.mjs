// A private, unverified payout preference. This module never initiates a payment.
export function preference(method, destination, confirmation, usResident, acknowledged) {
 destination=destination.trim();confirmation=confirmation.trim();
 if(method==='venmo'){destination=destination.replace(/^@/,'');confirmation=confirmation.replace(/^@/,'');}
 if(!['paypal','venmo'].includes(method))throw new Error('Choose PayPal or Venmo.');
 if(method==='paypal'&&(destination.length>254||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(destination)))throw new Error('Enter the email address on your PayPal account.');
 if(method==='venmo'&&!/^[A-Za-z0-9_-]{5,30}$/.test(destination))throw new Error('Enter your Venmo username: 5–30 letters, numbers, hyphens or underscores.');
 if(destination!==confirmation)throw new Error('The two entries don’t match. Please check them.');
 if(method==='venmo'&&!usResident)throw new Error('Venmo setup requires a US account.');
 if(!acknowledged)throw new Error('Confirm that these are your own payout details.');
 return {method,destination,usResident:method==='venmo',version:1};
}
export function masked(p){
 if(p.method==='paypal'){const [name,domain]=p.destination.split('@');return `${name.slice(0,2)}•••@${domain}`;}
 return `@${p.destination.slice(0,2)}•••${p.destination.slice(-2)}`;
}
export class Payout {
 constructor(root){this.el=id=>root.querySelector('#'+id);this.epoch=0;
  this.el('payout-edit').onclick=()=>this.edit();
  this.el('payout-cancel').onclick=()=>{this.editing=false;this.clear();this.draw();};
  this.el('payout-method').onchange=()=>{this.clear();this.method();};
  this.el('payout-form').onsubmit=e=>{e.preventDefault();this.save();};
  this.el('payout-remove').onclick=()=>this.remove();
  this.el('payout-retry').onclick=()=>this.connect(this.service);
  this.reset();
 }
 clear(){for(const id of ['payout-destination','payout-confirm'])this.el(id).value='';for(const id of ['payout-own','payout-us'])this.el(id).checked=false;}
 reset(){this.epoch++;this.service=null;this.saved=null;this.loading=true;this.busy=false;this.editing=false;this.error=false;this.clear();this.message('');this.draw();}
 message(text){this.el('payout-status').textContent=text;}
 method(){const venmo=this.el('payout-method').value==='venmo';this.el('payout-label').textContent=venmo?'Venmo username':'PayPal email';this.el('payout-confirm-label').textContent=venmo?'Re-enter username':'Re-enter email';this.el('payout-us-label').hidden=!venmo;
  for(const id of ['payout-destination','payout-confirm']){this.el(id).type=venmo?'text':'email';this.el(id).inputMode=venmo?'text':'email';this.el(id).maxLength=venmo?31:254;}
  this.el('payout-destination').placeholder=venmo?'@your-username':'you@example.com';
 }
 draw(){this.el('payout-form').hidden=!this.editing;this.el('payout-summary').hidden=this.editing;
  this.el('payout-title').textContent=this.loading?'Checking payout details…':this.error?'Payout details unavailable':this.saved?'Payout details saved':'Choose how you’d like to get paid';
  this.el('payout-detail').textContent=this.saved?`${this.saved.method==='paypal'?'PayPal':'Venmo'} · ${masked(this.saved)} · Not verified`:'Save your preference for future cash rewards.';
  this.el('payout-edit').textContent=this.saved?'Edit details':'Add payout method';this.el('payout-edit').disabled=this.loading||this.busy||this.error;
  this.el('payout-remove').hidden=!this.saved;this.el('payout-remove').disabled=this.busy;
  this.el('payout-retry').hidden=!this.error;this.el('payout-fields').disabled=this.busy;
  this.el('payout-save').textContent=this.busy?'Saving…':'Save payout details';
  this.el('payout-cancel').disabled=this.busy;
  this.onChange?.();
 }
 async connect(service){this.reset();this.service=service;const epoch=this.epoch;
  try{const saved=await service.load();if(epoch!==this.epoch)return;this.saved=saved;}
  catch{if(epoch!==this.epoch)return;this.error=true;this.message('We couldn’t load your payout details. Please try again.');}
  finally{if(epoch===this.epoch){this.loading=false;this.draw();}}
 }
 edit(){if(!this.service||this.loading||this.busy||this.error)return;this.editing=true;this.clear();this.el('payout-method').value=this.saved?.method||'paypal';this.method();this.el('payout-destination').value=this.saved?.destination||'';this.message('');this.draw();this.el('payout-destination').focus?.();}
 async save(){if(this.busy||!this.editing||!this.service)return;let data;
  try{data=preference(this.el('payout-method').value,this.el('payout-destination').value,this.el('payout-confirm').value,this.el('payout-us').checked,this.el('payout-own').checked);}
  catch(e){this.message(e.message);return;}
  const epoch=this.epoch;this.busy=true;this.draw();
  try{await this.service.save(data);if(epoch!==this.epoch)return;this.saved=data;this.editing=false;this.clear();this.message('Nice! Your preference is saved. It hasn’t been verified by PayPal or Venmo.');}
  catch{if(epoch===this.epoch)this.message('Save wasn’t confirmed. Check your connection and try again.');}
  finally{if(epoch===this.epoch){this.busy=false;this.draw();}}
 }
 async remove(){if(this.busy||!this.saved||!this.service)return;const epoch=this.epoch;this.busy=true;this.draw();
  try{await this.service.remove();if(epoch!==this.epoch)return;this.saved=null;this.clear();this.message('Payout details removed. You can add a method anytime.');}
  catch{if(epoch===this.epoch)this.message('Removal wasn’t confirmed. Please try again.');}
  finally{if(epoch===this.epoch){this.busy=false;this.draw();}}
 }
}
export function payoutService(user,db,sdk){const ref=sdk.doc(db,'payoutPreferences',user.uid);return {
 load:async()=>{const s=await sdk.getDocFromServer(ref);return s.exists()?s.data():null;},
 save:data=>sdk.setDoc(ref,{...data,updatedAt:sdk.serverTimestamp()}),
 remove:()=>sdk.deleteDoc(ref)
};}
