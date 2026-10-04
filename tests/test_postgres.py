import os
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import connect

@unittest.skipUnless(os.getenv('DATABASE_URL'),'PostgreSQL integration requires an isolated DATABASE_URL')
class PostgreSQLTests(unittest.TestCase):
    def test_rls_enabled_and_data_api_denied(self):
        with TestClient(app),connect() as c:
            tables=c.execute('SELECT tablename,rowsecurity FROM pg_tables WHERE schemaname=?',(c.schema,)).fetchall()
            self.assertGreater(len(tables),15)
            self.assertTrue(all(row['rowsecurity'] for row in tables))
            for role in ['anon','authenticated']:
                self.assertFalse(c.execute('SELECT has_schema_privilege(?, ?, ?)',(role,c.schema,'USAGE')).fetchone()[0])

    def test_reconnect_retains_records(self):
        from uuid import uuid4
        session=uuid4().hex
        with TestClient(app) as client:
            first=client.get('/api/v1/patients/me',headers={'X-Derma-Session':session}).json()['patient']['id']
        with TestClient(app) as client:
            second=client.get('/api/v1/patients/me',headers={'X-Derma-Session':session}).json()['patient']['id']
        self.assertEqual(first,second)
