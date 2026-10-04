import os
import unittest
import tempfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import connect

class AccountsTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.database_patch=patch('backend.database.DATABASE_PATH',Path(self.directory.name)/'accounts-test.db')
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.directory.cleanup()

    def test_roles_sharing_and_revocation(self):
        email=uuid4().hex+'@example.test'
        with TestClient(app) as client:
            from backend.accounts import password_hash, now
            import secrets
            uid=str(uuid4()); salt=secrets.token_hex(16)
            with connect() as c:
                c.execute('INSERT INTO user_profiles VALUES(?,?,?,?,?,?,?,?,?)',(uid,email,'Test Admin','active',password_hash('Strong-Test-Password-123',salt),salt,None,None,now()))
                c.execute("INSERT INTO user_roles VALUES(?,'admin')",(uid,))
            def login(address):
                r=client.post('/api/v1/accounts/login',json={'email':address,'password':'Strong-Test-Password-123'})
                self.assertEqual(r.status_code,200,r.text)
                return {'Authorization':'Bearer '+r.json()['token']}
            admin=login(email)
            self.assertEqual(client.get('/api/v1/accounts/users').status_code,401)
            def invite(role):
                address=uuid4().hex+'@example.test'
                r=client.post('/api/v1/accounts/invite',headers=admin,json={'name':'Fictional Test','email':address,'roles':[role]})
                self.assertEqual(r.status_code,201,r.text)
                data=r.json()
                activation=client.post('/api/v1/accounts/activate',json={'token':data['activationToken'],'password':'Strong-Test-Password-123'})
                self.assertEqual(activation.status_code,200,activation.text)
                self.assertEqual(client.post('/api/v1/accounts/activate',json={'token':data['activationToken'],'password':'Strong-Test-Password-123'}).status_code,400)
                return data,login(address)
            patient,ph=invite('patient'); professional,dh=invite('professional'); evaluator,eh=invite('evaluator')
            pid=patient['patientId']
            self.assertEqual(client.get(f'/api/v1/accounts/patients/{pid}/record',headers=admin).status_code,403)
            self.assertEqual(client.get(f'/api/v1/accounts/patients/{pid}/record',headers=eh).status_code,403)
            self.assertEqual(client.post('/api/v1/accounts/assignments',headers=admin,json={'evaluatorId':evaluator['id'],'patientId':pid}).status_code,200)
            self.assertEqual(client.get(f'/api/v1/accounts/patients/{pid}/record',headers=eh).status_code,200)
            headers={**eh,'X-Patient-ID':pid,'X-Derma-Session':uuid4().hex}
            self.assertEqual(client.get('/api/v1/patients/me',headers=headers).json()['patient']['id'],pid)
            self.assertEqual(client.get('/api/v1/patients/me',headers={**admin,'X-Patient-ID':pid}).status_code,403)
            g=client.post('/api/v1/accounts/grants',headers=ph,json={'professionalId':professional['id'],'scopes':['recommendations'],'hours':1})
            self.assertEqual(g.status_code,201,g.text)
            record=client.get(f'/api/v1/accounts/patients/{pid}/record',headers=dh)
            self.assertEqual(record.status_code,200,record.text)
            self.assertNotIn('patient',record.json()); self.assertNotIn('scans',record.json())
            self.assertEqual(client.post(f'/api/v1/accounts/patients/{pid}/notes',headers=dh,json={'body':'Fictional follow-up'}).status_code,201)
            self.assertEqual(client.post('/api/v1/accounts/grants/'+g.json()['id']+'/revoke',headers=ph).status_code,200)
            self.assertEqual(client.get(f'/api/v1/accounts/patients/{pid}/record',headers=dh).status_code,403)
            self.assertEqual(client.get(f'/api/v1/accounts/patients/{pid}/notes',headers=dh).status_code,403)
            self.assertEqual(client.get('/api/v1/accounts/users',headers=ph).status_code,403)
            expired=client.post('/api/v1/accounts/grants',headers=ph,json={'professionalId':professional['id'],'scopes':['scans'],'hours':1}).json()['id']
            with connect() as c: c.execute("UPDATE professional_access_grants SET expires_at='2000-01-01' WHERE id=?",(expired,))
            self.assertEqual(client.get(f'/api/v1/accounts/patients/{pid}/record',headers=dh).status_code,403)
