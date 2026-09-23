"""Loopback-only login preview; serves only files from web/, never the repo root."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'web'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def end_headers(self):
  self.send_header('Cache-Control','no-store')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Referrer-Policy','no-referrer')
  super().end_headers()
 def list_directory(self,path):self.send_error(404)
 def log_message(self,*args):pass
if __name__=='__main__':
 print('SignRush login preview: http://localhost:8088',flush=True)
 ThreadingHTTPServer(('127.0.0.1',8088),Handler).serve_forever()
