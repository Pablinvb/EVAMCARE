import unittest
from datetime import datetime,timezone
from backend.retention import eligible

class RetentionTests(unittest.TestCase):
    def test_minimum_year_and_three_months(self):
        at=datetime(2026,10,4,tzinfo=timezone.utc)
        self.assertFalse(eligible('2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00',at))
        self.assertFalse(eligible('2025-01-01T00:00:00+00:00','2026-08-01T00:00:00+00:00',at))
        self.assertTrue(eligible('2025-01-01T00:00:00+00:00','2026-07-04T00:00:00+00:00',at))
