import os
import unittest
from unittest.mock import patch

from backend.staging_start import configure_neon


class NeonStagingTests(unittest.TestCase):
    def test_neon_sets_verified_connection_without_supabase_ca(self):
        url = 'postgresql://example@ep-example.neon.tech/example'
        with patch.dict(os.environ, {'NEON_DATABASE_URL': url, 'PGSSLROOTCERT': '/old-ca'}, clear=True):
            self.assertTrue(configure_neon())
            self.assertEqual(os.getenv('DATABASE_URL'), url)
            self.assertEqual(os.getenv('DERMASCAN_POSTGRES_SCHEMA'), 'evamcare_neon')
            self.assertEqual(os.getenv('DERMASCAN_POSTGRES_SSLMODE'), 'verify-full')
            self.assertTrue(os.path.isfile(os.environ['PGSSLROOTCERT']))

    def test_rejects_pooled_connection(self):
        with patch.dict(os.environ, {'NEON_DATABASE_URL': 'postgresql://ep-example-pooler.neon.tech/db'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'direct Neon'):
                configure_neon()

    def test_preserves_previous_configuration_without_override(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'previous'}, clear=True):
            self.assertFalse(configure_neon())
            self.assertEqual(os.getenv('DATABASE_URL'), 'previous')
