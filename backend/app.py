"""Private pilot API. Production wiring requires Firebase, PostgreSQL and ADC.

Identity and storage adapters are injected for isolated tests; the default factory
never accepts test headers, unverified JWTs, arbitrary buckets, or query tokens.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
import tempfile
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, StrictBool
import psycopg
from psycopg import sql
from starlette.concurrency import run_in_threadpool

MAX_BYTES = 20 * 1024 * 1024
BUCKET = 'umi-signrush-raw'
TERMS = 'pilot-v1'
DISCLOSURE = 'training-v1'


@dataclass(frozen=True)
class Settings:
    database_url: str
    firebase_project: str
    pilot_subjects: frozenset[str]

    @classmethod
    def environment(cls):
        result = cls(os.environ['DATABASE_URL'], os.environ['FIREBASE_PROJECT_ID'],
                     frozenset(x.strip() for x in os.environ['SIGNRUSH_PILOT_UIDS'].split(',') if x.strip()))
        if result.firebase_project != 'signrush-login' or not result.pilot_subjects:
            raise RuntimeError('Explicit SignRush project and pilot Firebase UIDs required')
        return result


class FirebaseIdentity:
    def __init__(self, project):
        import firebase_admin
        from firebase_admin import auth
        self.auth = auth
        self.app = firebase_admin.initialize_app(options={'projectId': project}, name='signrush-api')

    def verify(self, token):
        try:
            claims = self.auth.verify_id_token(token, app=self.app, check_revoked=True)
        except Exception:
            # Fail closed for invalid, revoked, disabled or unverifiable users.
            raise HTTPException(401, 'Sign in again') from None
        if not claims.get('email_verified') or not claims.get('uid'):
            raise HTTPException(403, 'A verified email is required')
        return claims['uid']


class Database:
    ALLOWED = frozenset({'api_enroll','api_consent','api_signing_next','api_reserve_upload',
                        'api_finish_upload','api_review_next','api_review_media','api_answer'})

    def __init__(self, dsn):
        self.dsn = dsn
        # Refuse accidental deployment with the migration owner's credentials.
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            privileged = conn.execute("""
                SELECT r.rolsuper OR r.rolcreaterole OR r.rolbypassrls
                  OR has_schema_privilege(current_user,'signrush','CREATE')
                  OR has_table_privilege(current_user,'signrush.phrase_versions','SELECT')
                  OR has_function_privilege(current_user,'signrush.training_manifest()','EXECUTE')
                FROM pg_roles r WHERE r.rolname=current_user
            """).fetchone()[0]
            if privileged:
                raise RuntimeError('Use the restricted participant database login')

    def call(self, name, *args):
        if name not in self.ALLOWED:
            raise ValueError('Function not exposed')
        try:
            with psycopg.connect(self.dsn, connect_timeout=5, options='-c statement_timeout=10000') as conn:
                # The configured login must have only signrush_api membership.
                with conn.cursor() as cursor:
                    cursor.execute(sql.SQL('SELECT signrush.{}({})').format(
                        sql.Identifier(name), sql.SQL(',').join(sql.Placeholder() for _ in args)), args)
                    return cursor.fetchone()[0]
        except (psycopg.errors.RaiseException, psycopg.IntegrityError):
            # Never serialize SQL details, prompts, submitted answers or object paths.
            raise HTTPException(409, 'Task unavailable or current consent required') from None
        except psycopg.Error:
            raise HTTPException(503, 'Service temporarily unavailable') from None


class CloudStorage:
    def __init__(self):
        from google.cloud import storage
        self.client = storage.Client(project='signrush')

    def upload(self, key, file, mime):
        if not key.startswith('pilot/uploads/'):
            raise ValueError('Invalid upload destination')
        blob = self.client.bucket(BUCKET).blob(key)
        blob.upload_from_file(file, content_type=mime, if_generation_match=0, timeout=60)
        return str(blob.generation)

    def metadata(self, media):
        self._validate(media)
        blob = self.client.bucket(BUCKET).blob(media['object_key'], generation=int(media['generation']))
        blob.reload(timeout=20)
        if blob.content_type != 'video/mp4' or not 0 < blob.size <= MAX_BYTES:
            raise ValueError('Unexpected playback media')
        return blob.size

    def read(self, media, start, end):
        self._validate(media)
        blob = self.client.bucket(BUCKET).blob(media['object_key'], generation=int(media['generation']))
        return blob.download_as_bytes(start=start, end=end, if_generation_match=int(media['generation']), timeout=30)

    @staticmethod
    def _validate(media):
        # No endpoint or adapter accepts a client-provided storage locator.
        if media['bucket'] != BUCKET or not media['object_key'].startswith('pilot/playback/'):
            raise ValueError('Playback outside approved prefix')
        if not str(media['generation']).isdigit():
            raise ValueError('Unpinned playback media')


class Consent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    accept: StrictBool
    terms_version: Literal['pilot-v1']
    disclosure_version: Literal['training-v1']


class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid', str_min_length=1, str_max_length=4000)
    text: str


def byte_range(header, size):
    if header is None:
        return 0, size-1, 200
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
    if not match or not any(match.groups()):
        raise HTTPException(416, 'Invalid range', headers={'Content-Range': f'bytes */{size}'})
    left, right = match.groups()
    if left:
        start, end = int(left), min(int(right), size-1) if right else size-1
    else:
        start, end = max(0, size-int(right)), size-1
    if start >= size or start > end:
        raise HTTPException(416, 'Invalid range', headers={'Content-Range': f'bytes */{size}'})
    return start, end, 206


def create_app(settings=None, *, identity=None, database=None, storage=None):
    settings = settings or Settings.environment()
    identity = identity or FirebaseIdentity(settings.firebase_project)
    database = database or Database(settings.database_url)
    storage = storage or CloudStorage()
    app = FastAPI(title='SignRush private pilot', docs_url=None, redoc_url=None, openapi_url=None)
    bearer = HTTPBearer(auto_error=False)

    # Serve only these public assets, on the API's own origin. Never mount the repo.
    web_root = Path(__file__).resolve().parents[1] / 'web'
    def asset_handler(filename):
        def serve():
            return FileResponse(web_root / filename)
        return serve
    for route, filename in {'/':'index.html','/styles.css':'styles.css',
                            '/login.js':'login.js','/firebase-config.js':'firebase-config.js',
                            '/onboarding.mjs':'onboarding.mjs','/signing.mjs':'signing.mjs','/review.mjs':'review.mjs','/home.mjs':'home.mjs',
                            '/firestore-registration.mjs':'firestore-registration.mjs',
                            '/pilot-disclosure.mjs':'pilot-disclosure.mjs'}.items():
        app.add_api_route(route, asset_handler(filename), methods=['GET'], include_in_schema=False)

    @app.middleware('http')
    async def private_headers(request, call_next):
        result = await call_next(request)
        result.headers['Cache-Control'] = 'no-store, private'
        result.headers['X-Content-Type-Options'] = 'nosniff'
        result.headers['Referrer-Policy'] = 'no-referrer'
        return result

    def subject(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials or credentials.scheme.lower() != 'bearer' or len(credentials.credentials)>16384:
            raise HTTPException(401, 'Sign in required')
        uid = identity.verify(credentials.credentials)
        if uid not in settings.pilot_subjects:
            raise HTTPException(403, 'This pilot is invitation-only')
        return uid

    @app.exception_handler(Exception)
    async def unavailable(request, error):
        return JSONResponse({'detail': 'Service temporarily unavailable'}, status_code=503,
                            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/health')
    def health():
        return {'status':'ok','mode':'test'}

    @app.post('/v1/account')
    def enroll(uid=Depends(subject)):
        return database.call('api_enroll',uid)

    @app.get('/v1/consent')
    def disclosure(uid=Depends(subject)):
        return {'terms_version':TERMS,'disclosure_version':DISCLOSURE,
                'notice':'UMI will retain your signing videos, prompts, interpretations and review results, '
                         'including failed attempts, for research, AI model training and evaluation. '
                         'Your face and signing may identify you. This pilot awards test points with no cash value. '
                         'You can withdraw consent to stop further participation and future eligible exports. '
                         'Copies already exported cannot automatically be recalled.',
                'rules':['Use good lighting. Keep your face, shoulders, arms and hands visible.',
                         'Sign the assigned meaning accurately. Review videos independently.',
                         'Do not share prompts, answers or accounts.']}

    @app.post('/v1/consent')
    def consent(body: Consent, uid=Depends(subject)):
        database.call('api_consent',uid,body.accept)
        return {'accepted':body.accept}

    @app.post('/v1/signing/next')
    def signing(uid=Depends(subject)):
        return {'task':database.call('api_signing_next',uid)}

    @app.put('/v1/signing/{assignment}/video',status_code=202)
    async def upload(assignment: UUID, request: Request, uid=Depends(subject)):
        mime = request.headers.get('content-type','').split(';')[0].strip()
        length = request.headers.get('content-length','')
        if mime not in ('video/mp4','video/webm'):
            raise HTTPException(415,'Use MP4 or WebM')
        if not length.isdigit() or not 0<int(length)<=MAX_BYTES:
            raise HTTPException(413,'A Content-Length of 1 to 20 MiB is required')
        ticket = await run_in_threadpool(database.call,'api_reserve_upload',uid,assignment,mime)
        size, digest = 0, sha256()
        # In deployment this is bounded, ephemeral cloud disk; never a dataset sync.
        with tempfile.TemporaryFile() as file:
            async for chunk in request.stream():
                size += len(chunk)
                if size>int(length) or size>MAX_BYTES:
                    raise HTTPException(413,'Upload exceeds declared size')
                digest.update(chunk)
                file.write(chunk)
            if size != int(length):
                raise HTTPException(400,'Incomplete upload')
            file.seek(0)
            generation = await run_in_threadpool(storage.upload,ticket['object_key'],file,mime)
        return await run_in_threadpool(database.call,'api_finish_upload',uid,UUID(ticket['ticket_id']),generation,digest.hexdigest(),size)

    @app.post('/v1/reviews/next')
    def review(uid=Depends(subject)):
        task = database.call('api_review_next',uid)
        if task:
            task['playback_path'] = f"/v1/reviews/{task['assignment_id']}/video"
        return {'task':task}

    @app.get('/v1/reviews/{assignment}/video')
    def playback(assignment: UUID, request: Request, uid=Depends(subject)):
        media = database.call('api_review_media',uid,assignment)
        size = storage.metadata(media)
        start,end,status = byte_range(request.headers.get('range'),size)
        data = storage.read(media,start,end)
        if len(data)!=end-start+1:
            raise HTTPException(503,'Video temporarily unavailable')
        headers={'Accept-Ranges':'bytes','Content-Length':str(len(data))}
        if status==206:
            headers['Content-Range']=f'bytes {start}-{end}/{size}'
        return Response(data,status_code=status,media_type='video/mp4',headers=headers)

    @app.post('/v1/reviews/{assignment}/answer')
    def answer(assignment: UUID, body: Answer, uid=Depends(subject)):
        if not body.text.strip():
            raise HTTPException(422,'Write the meaning of the signing')
        return database.call('api_answer',uid,assignment,body.text)

    return app
