import os
import secrets
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.accounts import initialize_accounts, password_matches, login_attempts
from backend.database import connect
from backend.sqlite_backup import backup
from backend.export_supabase import export

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'test.db'
        self.db_patch=patch('backend.database.DATABASE_PATH',self.path);self.db_patch.start()
        self.env_patch=patch.dict(os.environ,{'DERMASCAN_BOOTSTRAP_ADMIN_EMAIL':'admin@example.test','DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD':'Initial-Password-123!'});self.env_patch.start()
        login_attempts.clear()

    def tearDown(self):
        self.env_patch.stop();self.db_patch.stop();self.temp.cleanup()

    def test_bootstrap_idempotence_and_removal(self):
        with TestClient(app) as client:
            with connect() as c: original=dict(c.execute('SELECT * FROM user_profiles').fetchone())
            self.assertNotEqual(original['password_hash'],'Initial-Password-123!')
            self.assertTrue(password_matches('Initial-Password-123!',original['salt'],original['password_hash']))
            os.environ['DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD']='Changed-Environment-123!'
            initialize_accounts()
            with connect() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM user_profiles').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT password_hash FROM user_profiles').fetchone()[0],original['password_hash'])
            os.environ.pop('DERMASCAN_BOOTSTRAP_ADMIN_EMAIL');os.environ.pop('DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD')
            initialize_accounts()
            self.assertEqual(client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'Initial-Password-123!'}).status_code,200)

    def test_reset_single_use_revokes_sessions_and_does_not_echo_secrets(self):
        settings={k:'test' for k in ['DERMASCAN_SMTP_HOST','DERMASCAN_SMTP_FROM','DERMASCAN_SMTP_USER','DERMASCAN_SMTP_PASSWORD']}
        settings['DERMASCAN_RECOVERY_URL']='https://pablinvb.github.io/EVAMCARE/'
        with TestClient(app) as client,patch.dict(os.environ,settings),patch('backend.password_recovery.send_recovery_email') as send:
            session=client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'Initial-Password-123!'}).json()['token']
            known=client.post('/api/v1/accounts/password-recovery',json={'email':'admin@example.test'})
            raw=send.call_args.args[1]
            unknown=client.post('/api/v1/accounts/password-recovery',json={'email':'missing@example.test'})
            self.assertEqual(known.json(),unknown.json());self.assertNotIn(raw,known.text)
            with connect() as c:
                self.assertFalse(c.execute('SELECT 1 FROM account_tokens WHERE hash=?',(raw,)).fetchone())
            self.assertEqual(client.post('/api/v1/accounts/password-reset',json={'token':raw,'password':'Replacement-Password-456!'}).status_code,200)
            self.assertEqual(client.post('/api/v1/accounts/password-reset',json={'token':raw,'password':'Replacement-Password-456!'}).status_code,400)
            self.assertEqual(client.get('/api/v1/accounts/me',headers={'Authorization':'Bearer '+session}).status_code,401)
            self.assertEqual(client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'Initial-Password-123!'}).status_code,401)
            self.assertEqual(client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'Replacement-Password-456!'}).status_code,200)
            error=client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'SECRET'})
            self.assertNotIn('SECRET',error.text)

    def test_expired_reset_inactive_account_and_email_failure(self):
        settings={k:'test' for k in ['DERMASCAN_SMTP_HOST','DERMASCAN_SMTP_FROM','DERMASCAN_SMTP_USER','DERMASCAN_SMTP_PASSWORD']};settings['DERMASCAN_RECOVERY_URL']='https://example.test/'
        with TestClient(app) as client,patch.dict(os.environ,settings),patch('backend.password_recovery.send_recovery_email') as send:
            client.post('/api/v1/accounts/password-recovery',json={'email':'admin@example.test'})
            token=send.call_args.args[1]
            with connect() as c:c.execute("UPDATE account_tokens SET expires_at='2000-01-01' WHERE kind='reset'")
            self.assertEqual(client.post('/api/v1/accounts/password-reset',json={'token':token,'password':'Replacement-Password-456!'}).status_code,400)
            send.side_effect=RuntimeError('SMTP-sensitive-details')
            r=client.post('/api/v1/accounts/password-recovery',json={'email':'admin@example.test'})
            self.assertNotIn('SMTP-sensitive-details',r.text)
            with connect() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM account_tokens WHERE kind='reset'").fetchone()[0],0)
            with connect() as c:c.execute("UPDATE user_profiles SET status='inactive'")
            self.assertEqual(client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'Initial-Password-123!'}).status_code,401)

    def test_backup_never_overwrites(self):
        with closing(sqlite3.connect(self.path)) as c:
            c.execute('CREATE TABLE sentinel(value TEXT)');c.execute("INSERT INTO sentinel VALUES('preserved')");c.commit()
        target=Path(self.temp.name)/'backup.db'
        backup(self.path,target)
        with closing(sqlite3.connect(target)) as c:self.assertEqual(c.execute('SELECT value FROM sentinel').fetchone()[0],'preserved')
        with self.assertRaises(FileExistsError):backup(self.path,target)
        with closing(sqlite3.connect(self.path)) as c:self.assertEqual(c.execute('SELECT value FROM sentinel').fetchone()[0],'preserved')

    def test_missing_persistent_database_fails_closed(self):
        from backend.database import initialize_database
        with patch.dict(os.environ,{'DERMASCAN_REQUIRE_EXISTING_DATABASE':'1'}):
            with self.assertRaises(RuntimeError):initialize_database()
        self.assertFalse(self.path.exists())

    def test_private_photo_scope_and_immediate_revocation(self):
        from test_api import synthetic_image
        from backend.patient_platform import save_patient_scan
        with TestClient(app) as client:
            admin_token=client.post('/api/v1/accounts/login',json={'email':'admin@example.test','password':'Initial-Password-123!'}).json()['token']
            admin={'Authorization':'Bearer '+admin_token}
            identities=[]
            for role in ['patient','professional']:
                invite=client.post('/api/v1/accounts/invite',headers=admin,json={'name':'Fictional Photo Test','email':role+'@example.test','roles':[role]}).json()
                client.post('/api/v1/accounts/activate',json={'token':invite['activationToken'],'password':'Photo-Test-Password-123!'})
                token=client.post('/api/v1/accounts/login',json={'email':role+'@example.test','password':'Photo-Test-Password-123!'}).json()['token']
                identities.append((invite,{'Authorization':'Bearer '+token}))
            patient,ph=identities[0];professional,dh=identities[1];pid=patient['patientId']
            with connect() as c: session=c.execute('SELECT session_id FROM patients WHERE id=?',(pid,)).fetchone()[0]
            sid,_=save_patient_scan(session,{'overallScore':60,'metrics':[]},capture_source='upload')
            path=f'/api/v1/accounts/patients/{pid}/scans/{sid}/photo'
            with patch('backend.private_photos.ensure_bucket'),patch('backend.private_photos.storage_request',return_value=b'private-jpeg'):
                self.assertEqual(client.post(path,headers=ph,files={'image':('face.jpg',synthetic_image(),'image/jpeg')}).status_code,400)
                response=client.post(path,headers=ph,data={'consent':'true'},files={'image':('face.jpg',synthetic_image(),'image/jpeg')})
                self.assertEqual(response.status_code,201,response.text)
                iid=response.json()['id'];photo=f'/api/v1/accounts/patients/{pid}/photos/{iid}'
                self.assertEqual(client.get(photo,headers=admin).status_code,403)
                self.assertEqual(client.get(photo,headers=dh).status_code,403)
                grant=client.post('/api/v1/accounts/grants',headers=ph,json={'professionalId':professional['id'],'scopes':['photographs'],'hours':1}).json()['id']
                download=client.get(photo,headers=dh)
                self.assertEqual(download.status_code,200,download.text)
                self.assertEqual(download.headers['Cache-Control'],'no-store')
                client.post('/api/v1/accounts/grants/'+grant+'/revoke',headers=ph)
                self.assertEqual(client.get(photo,headers=dh).status_code,403)

    def test_export_excludes_secrets_demo_and_preserves_identity(self):
        with TestClient(app):
            with connect() as c:
                c.execute("INSERT INTO patients(id,patient_code,session_id,first_name,skin_goals_json,demo,created_at,updated_at) VALUES('real-p','DS-TEST','PRIVATE-SESSION','O''Brien','[]',0,'2026-01-01','2026-01-01')")
                c.execute("INSERT INTO patients(id,patient_code,session_id,first_name,skin_goals_json,demo,created_at,updated_at) VALUES('demo-p','DS-DEMO','DEMO-SESSION','Fictional demo','[]',1,'2026-01-01','2026-01-01')")
            target=Path(self.temp.name)/'export.sql';export(self.path,target)
            sql=target.read_text(encoding='utf-8')
            for secret in ['PRIVATE-SESSION','DEMO-SESSION','password_hash','salt','account_tokens','demo-p']:
                self.assertNotIn(secret,sql)
            self.assertIn("'real-p'",sql);self.assertIn("'O''Brien'",sql)
            with self.assertRaises(FileExistsError):export(self.path,target)
