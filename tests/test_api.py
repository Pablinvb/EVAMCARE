import io
import unittest
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app


def synthetic_image() -> bytes:
    image = np.full((900, 720, 3), (188, 209, 197), dtype=np.uint8)
    cv2.ellipse(image, (360, 420), (185, 245), 0, 0, 360, (115, 164, 204), -1)
    cv2.circle(image, (300, 390), 15, (35, 40, 48), -1)
    cv2.circle(image, (420, 390), 15, (35, 40, 48), -1)
    cv2.line(image, (315, 550), (405, 550), (65, 70, 115), 8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.session = uuid4().hex
        self.headers = {"X-Derma-Session": self.session}

    def tearDown(self) -> None:
        self.client.delete("/api/v1/history", headers=self.headers)
        self.client_context.__exit__(None, None, None)

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["storesImages"])
        self.assertEqual(response.json()["clinicalStatus"], "research_only")
        self.assertEqual(self.client.get("/data/dermascan.db").status_code, 404)

    def test_clinical_claim_is_blocked(self) -> None:
        response = self.client.get("/api/v1/clinical-status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["clinicallyValidated"])
        self.assertEqual(body["status"], "research_only")
        self.assertGreater(len(body["blockers"]), 0)

    def test_analysis_and_history_lifecycle(self) -> None:
        response = self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"image": ("face.jpg", io.BytesIO(synthetic_image()), "image/jpeg")},
            data={"save_history": "true"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["imageStored"])
        self.assertEqual(len(body["result"]["metrics"]), 8)
        self.assertIsNotNone(body["analysisId"])

        history = self.client.get("/api/v1/history", headers=self.headers)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["items"]), 1)

        deleted = self.client.delete(
            f"/api/v1/history/{body['analysisId']}", headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)

    def test_rejects_invalid_type(self) -> None:
        response = self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"image": ("notes.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)


if __name__ == "__main__":
    unittest.main()
