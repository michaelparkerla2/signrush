import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from worker_runtime import session_lock,run_loop
class Runtime(unittest.TestCase):
 def test_duplicate_session_and_crash_release(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'worker.lock'
   with self.assertRaises(ValueError):
    with session_lock(path):
     with self.assertRaises(SystemExit):
      with session_lock(path):pass
     raise ValueError('synthetic crash')
   with session_lock(path):pass
 def test_bounded_retries_and_no_private_error_content(self):
  class Stop:
   now=0
   def is_set(self):return False
   def wait(self,n):self.now+=n
  class Worker:
   def tick(self):raise ValueError('SECRET signed URL')
  stop=Stop();messages=[]
  run_loop(Worker(),41,stop,clock=lambda:stop.now,report=lambda s,**kw:messages.append(s))
  self.assertEqual(stop.now,41)
  self.assertEqual(messages,['Worker retry: ValueError']*3)
 def test_shutdown_stops_new_work(self):
  class Stop:
   done=False
   def is_set(self):return self.done
   def wait(self,n):self.done=True
  class Worker:
   calls=0
   def tick(self):self.calls+=1
  worker=Worker();run_loop(worker,28800,Stop())
  self.assertEqual(worker.calls,1)
if __name__=='__main__':unittest.main()
