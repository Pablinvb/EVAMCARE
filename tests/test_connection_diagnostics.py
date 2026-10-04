import unittest
from unittest.mock import patch
from backend.postgres import connection_diagnostic, validate_staging_connection

class ConnectionDiagnosticTests(unittest.TestCase):
    def test_categories_do_not_echo_private_text(self):
        for marker,category in [('password authentication failed','DB_AUTH'),('could not translate host','DB_DNS'),('certificate verify failed','DB_TLS'),('Network is unreachable','DB_NETWORK'),('connection timeout expired','DB_CONNECT'),('invalid percent encoding','DB_FORMAT')]:
            result=connection_diagnostic(Exception(marker+' SECRET-TEST postgres://private-host'))
            self.assertTrue(result.startswith(category),result)
            self.assertNotIn('SECRET-TEST',result)
            self.assertNotIn('private-host',result)
    def test_pooler_port_and_username(self):
        with patch.dict('os.environ',{'DERMASCAN_POSTGRES_SCHEMA':'evamcare_staging'}):
            uri='postgresql://postgres.inshzjzlcwklaxpxcpve:fictional%40password@aws-0-sa-east-1.pooler.supabase.com:5432/postgres'
            self.assertEqual(validate_staging_connection(uri)['password'],'fictional@password')
            for value,code in [(uri.replace(':5432/',':6543/'),'DB_PORT'),(uri.replace('postgres.inshzjzlcwklaxpxcpve:','postgres:'),'DB_USER')]:
                with self.assertRaisesRegex(RuntimeError,code):validate_staging_connection(value)
