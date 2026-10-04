import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app


class PatientPlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.session = uuid4().hex
        self.headers = {"X-Derma-Session": self.session}

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_demo_patient_dashboard_and_timeline(self) -> None:
        response = self.client.get(
            "/api/v1/patients/me/dashboard", headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertRegex(body["patient"]["patientCode"], r"^DS-[A-Z0-9]{7}$")
        self.assertEqual(body["scanCount"], 4)
        self.assertEqual(body["currentSkinScore"], 78)

        timeline = self.client.get(
            "/api/v1/patients/me/timeline", headers=self.headers
        )
        self.assertEqual(timeline.status_code, 200, timeline.text)
        self.assertGreaterEqual(len(timeline.json()["changes"]), 3)
        hydration = next(
            item
            for item in timeline.json()["changes"]
            if item["key"] == "hydration"
        )
        self.assertEqual(hydration["initial"], 41)
        self.assertEqual(hydration["current"], 71)
        self.assertEqual(hydration["change"], 30)

    def test_scan_comparison_and_recommendations(self) -> None:
        scans = self.client.get(
            "/api/v1/patients/me/scans", headers=self.headers
        ).json()["items"]
        self.assertEqual(len(scans), 4)
        first = scans[-1]["id"]
        latest = scans[0]["id"]
        comparison = self.client.get(
            "/api/v1/patients/me/compare",
            headers=self.headers,
            params={"scan_a": first, "scan_b": latest},
        )
        self.assertEqual(comparison.status_code, 200, comparison.text)
        self.assertEqual(comparison.json()["scanA"]["id"], first)
        self.assertEqual(comparison.json()["scanB"]["id"], latest)
        self.assertGreater(len(comparison.json()["metrics"]), 0)

        recommendations = self.client.get(
            "/api/v1/patients/me/recommendations", headers=self.headers
        )
        self.assertEqual(recommendations.status_code, 200)
        self.assertGreater(len(recommendations.json()["items"]), 0)

    def test_secure_share_creation_and_revocation(self) -> None:
        created = self.client.post(
            "/api/v1/patients/me/share",
            headers=self.headers,
            json={
                "recipientType": "dermatologist",
                "permissions": ["profile", "scans", "evolution"],
                "expiresInHours": 24,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        share = created.json()["share"]
        self.assertIn("token", share)
        self.assertEqual(share["recipientType"], "dermatologist")

        listed = self.client.get("/api/v1/patients/me/shares", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["items"]), 1)

        revoked = self.client.post(
            f"/api/v1/shares/{share['id']}/revoke", headers=self.headers
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        relisted = self.client.get("/api/v1/patients/me/shares", headers=self.headers)
        self.assertIsNotNone(relisted.json()["items"][0]["revokedAt"])


if __name__ == "__main__":
    unittest.main()
