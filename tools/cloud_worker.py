"""Private scheduled entry point for the existing worker (Cloud Run IAM required)."""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta, timezone
import secrets


def authorized(header, audience, caller, verify):
    if not header.startswith('Bearer ') or not audience or not caller:
        return False
    try:
        claims = verify(header[7:], audience)
        return claims.get('email_verified') is True and claims.get('email') == caller
    except Exception:
        return False


class Runner:
    def __init__(self, worker):
        self.worker = worker
        self.lock = threading.Lock()

    def tick(self):
        if not self.lock.acquire(blocking=False):
            return 409
        ref = self.worker.db.document('workerHealth/scheduled')
        token = secrets.token_hex(16)
        fs = self.worker.fs
        # Terminate the container before its lease can expire, even if an SDK call
        # hangs. Cloud Run restarts it; the next scheduled request can recover.
        watchdog = threading.Timer(450, lambda: os._exit(1))
        watchdog.daemon = True
        watchdog.start()
        try:
            @fs.transactional
            def acquire(tx):
                previous = ref.get(transaction=tx).to_dict() or {}
                now = datetime.now(timezone.utc)
                if previous.get('leaseUntil', now) > now:
                    return False
                tx.set(ref, {'leaseToken': token, 'leaseUntil': now + timedelta(minutes=10),
                             'startedAt': fs.SERVER_TIMESTAMP, 'state': 'running'}, merge=True)
                return True
            if not acquire(self.worker.db.transaction()):
                return 409
            try:
                self.worker.tick()
                status = 200
            except Exception as exc:
                # SDK errors may contain private URLs; do not log their messages.
                print('Scheduled worker failed:', type(exc).__name__, flush=True)
                status = 503
            @fs.transactional
            def finish(tx):
                previous = ref.get(transaction=tx).to_dict() or {}
                if previous.get('leaseToken') == token:
                    tx.update(ref, {'leaseToken': fs.DELETE_FIELD, 'leaseUntil': fs.DELETE_FIELD,
                                    'finishedAt': fs.SERVER_TIMESTAMP,
                                    'state': 'cycle_finished' if status == 200 else 'failed'})
            finish(self.worker.db.transaction())
            return status
        finally:
            watchdog.cancel()
            self.lock.release()


def handler(runner, audience, caller, verify):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code):
            self.send_response(code)
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            self.reply(200 if self.path == '/healthz' else 404)

        def do_POST(self):
            if self.path != '/tick':
                return self.reply(404)
            if not authorized(self.headers.get('Authorization', ''), audience, caller, verify):
                return self.reply(403)
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0':
                return self.reply(400)
            try:
                self.reply(runner.tick())
            except Exception as exc:
                print('Scheduled request failed:', type(exc).__name__, flush=True)
                self.reply(503)
    return Handler


def main():
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import verify_oauth2_token
    from consensus_worker import ConsensusWorker
    audience = os.environ['WORKER_AUDIENCE']
    caller = os.environ['WORKER_CALLER']
    if not audience.startswith('https://') or not caller.endswith('.iam.gserviceaccount.com'):
        raise ValueError('A private service audience and scheduler identity are required')
    verify = lambda token, aud: verify_oauth2_token(token, Request(), audience=aud)
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))),
                                handler(Runner(ConsensusWorker()), audience, caller, verify))
    server.serve_forever()


if __name__ == '__main__':
    main()
