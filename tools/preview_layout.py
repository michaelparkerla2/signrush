"""Loopback-only synthetic layout harness. No Firebase/auth/payment/media writes.

Open http://localhost:8089/?width=390&mode=home. Modes: landing, home,
sign, review, arena, payout, wallet, avatar. Never deploy this harness.
"""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import json
ROOT=Path(__file__).resolve().parents[1]/'web'
MODES={'landing','home','sign','review','arena','payout','wallet','avatar'}
SCRIPT='''
import {Game} from '/game.mjs';
import {Home} from '/home.mjs';
const el=id=>document.getElementById(id),mode=MODE;
if(mode!=='landing'){
 document.body.classList.add('player-ready');el('account-panel').hidden=true;
 for(const id of ['payout-nav','account-toggle','task-modes'])el(id).hidden=false;
 const game=new Game(document);
 await game.connect({board:n=>{n(['Sprout','Comet','Nova','Ripple'].map((alias,i)=>({alias,avatar:['sprout','comet','nova','ripple'][i],points:5000-i*1000})));return()=>{};},points:n=>{n(250);return()=>{};},load:async()=>({alias:'Synthetic player',avatar:'sprout',listed:false}),save:async()=>{},sync:async()=>{}});
 const home=new Home(el('home'),el('payout-dialog'));
 home.connect({tasks:n=>{n({signAvailable:1,reviewAvailable:1,submitted:8,pending:3,approved:5});return()=>{};},points:n=>{n(250);return()=>{};},payout:{load:async()=>null,save:async()=>{},remove:async()=>{}}});
 el('home').hidden=!['home','payout','wallet','avatar'].includes(mode);
 el('signing').hidden=mode!=='sign';el('reviewing').hidden=mode!=='review';el('arena').hidden=mode!=='arena';
 if(mode==='sign'){for(const id of ['capture-surface','phrase-panel','open-camera'])el(id).hidden=false;el('phrase-text').textContent='A synthetic phrase for layout review.';el('get-phrase').hidden=true;}
 if(mode==='review'){el('review-form').hidden=false;el('review-player').hidden=false;el('review-status').textContent='Synthetic layout only. No participant video loaded.';}
 if(mode==='payout'){el('payout-summary').hidden=true;el('payout-form').hidden=false;el('payout-dialog').showModal();}
 if(mode==='wallet')el('cash-wallet').showModal();
 if(mode==='avatar')game.edit();
}
'''
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def send_html(self,value):
  data=value.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  u=urlsplit(self.path);q=parse_qs(u.query);mode=q.get('mode',['home'])[0]
  if mode not in MODES:self.send_error(400);return
  if u.path=='/':
   width=int(q.get('width',['390'])[0]);width=max(320,min(width,1200))
   links=' '.join(f'<a href="/?width={width}&mode={m}">{m}</a>' for m in sorted(MODES))
   self.send_html(f'<title>SignRush synthetic layout QA</title><p>LOCAL SYNTHETIC QA · No real accounts or writes</p><nav>{links}</nav><iframe title="Layout preview" src="/fixture?mode={mode}" style="display:block;width:{width}px;height:1000px;border:0"></iframe>');return
  if u.path=='/fixture':
   source=(ROOT/'index.html').read_text().replace('<script type="module" src="login.js"></script>','<script type="module">'+SCRIPT.replace('MODE',json.dumps(mode))+'</script>')
   self.send_html(source);return
  super().do_GET()
 def list_directory(self,path):self.send_error(404)
 def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8089),Handler).serve_forever()
