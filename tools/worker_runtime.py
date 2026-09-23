"""Bounded operator sessions on an existing host; not an always-on service."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import signal
import threading
import time

@contextmanager
def session_lock(path):
    """One upgraded worker per host/user, released by the OS after any exit."""
    path=Path(path).expanduser()
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('A SignRush worker is already running on this host.')
        yield
    finally:os.close(fd)

def run_loop(worker,seconds,stop,*,clock=time.monotonic,report=print):
    end=clock()+seconds
    failures=0
    while not stop.is_set() and clock()<end:
        try:
            worker.tick();failures=0
        except Exception as exc:
            failures+=1
            # Exception strings can contain signed URLs. Log type only.
            report('Worker retry: '+type(exc).__name__,flush=True)
        delay=min(60,5*2**min(failures,4)) if failures else 5
        stop.wait(max(0,min(delay,end-clock())))

def main(factory):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=1800,help='Session length: 1–28800 seconds (default 1800)')
    parser.add_argument('--lock-file',default='~/.cache/signrush/worker.lock')
    args=parser.parse_args()
    if not 1<=args.seconds<=28800:parser.error('Session must be between 1 second and 8 hours')
    stop=threading.Event()
    def shutdown(*_):stop.set()
    with session_lock(args.lock_file):
        old={s:signal.signal(s,shutdown) for s in (signal.SIGINT,signal.SIGTERM)}
        try:
            worker=factory()
            print('SignRush worker session ready. Host must remain available.',flush=True)
            run_loop(worker,args.seconds,stop)
        finally:
            for s,handler in old.items():signal.signal(s,handler)
    print('SignRush worker session stopped.',flush=True)
