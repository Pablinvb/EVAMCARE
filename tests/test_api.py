import io
import unittest
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import delete_session_leads


def synthetic_image() -> bytes:
    image = np.full((900, 720, 3), (188, 209, 197), dtype=np.uint8)
    cv2.ellipse(image, (360, 420), (185, 245), 0, 0, 360, (115, 164, 204), -1)
    cv2.circle(image, (300, 390), 15, (35, 40, 48), -1)
    cv2.circle(image, (420, 390), 15, (35, 40, 48), -1)
    cv2.line(image, (315, 550), (405, 550), (65, 70, 115), 8)
    cv2.circle(image, (275, 500), 18, (65, 75, 235), -1)
    cv2.circle(image, (445, 510), 15, (70, 80, 225), -1)
    cv2.circle(image, (420, 580), 22, (75, 105, 125), -1)
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
        delete_session_leads(self.session)
        self.client_context.__exit__(None, None, None)

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["storesImages"])
        self.assertEqual(response.json()["clinicalStatus"], "research_only")
        self.assertIn(response.json()["environment"], {"development", "staging", "production"})
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
        self.assertTrue(body["result"]["attentionMap"]["derivedFromImage"])
        self.assertEqual(
            body["result"]["attentionMap"]["zoneCount"],
            len(body["result"]["attentionZones"]),
        )
        self.assertGreater(len(body["result"]["attentionZones"]), 0)
        for zone in body["result"]["attentionZones"]:
            self.assertGreaterEqual(zone["x"], 0)
            self.assertLessEqual(zone["x"], 1)
            self.assertGreaterEqual(zone["y"], 0)
            self.assertLessEqual(zone["y"], 1)
            self.assertIn(zone["type"], {"redness", "pigmentation", "texture"})
        self.assertTrue(
            any(
                abs(zone["x"] - 0.38) < 0.07 and abs(zone["y"] - 0.55) < 0.07
                for zone in body["result"]["attentionZones"]
            ),
            "El mapa no localizó la variación controlada de la mejilla izquierda.",
        )
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

    def test_nearby_clinic_and_consented_lead(self) -> None:
        analysis = self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"image": ("face.jpg", io.BytesIO(synthetic_image()), "image/jpeg")},
        )
        self.assertEqual(analysis.status_code, 200, analysis.text)
        token = analysis.json()["referralToken"]

        clinics = self.client.get(
            "/api/v1/clinics",
            params={"latitude": -0.1807, "longitude": -78.4678, "radius_km": 50},
        )
        self.assertEqual(clinics.status_code, 200, clinics.text)
        clinic = clinics.json()["items"][0]
        self.assertTrue(clinic["demo"])
        self.assertNotIn("latitude", clinic)
        self.assertGreaterEqual(clinic["distanceKm"], 0)

        lead_request = {
            "clinicId": clinic["id"],
            "referralToken": token,
            "fullName": "Persona de Prueba",
            "phone": "+593990000000",
            "email": "persona@example.com",
            "preferredChannel": "whatsapp",
            "preferredTime": "Tardes",
            "latitude": -0.1807,
            "longitude": -78.4678,
            "distanceKm": clinic["distanceKm"],
            "consentContact": True,
            "consentLocation": True,
            "consentResults": True,
        }
        lead = self.client.post(
            "/api/v1/leads", headers=self.headers, json=lead_request
        )
        self.assertEqual(lead.status_code, 201, lead.text)
        self.assertFalse(lead.json()["imageShared"])

        partner = self.client.get(
            "/api/v1/partner/leads",
            params={"clinic_id": clinic["id"]},
            headers={"X-Partner-Key": "development-partner-key"},
        )
        self.assertEqual(partner.status_code, 200, partner.text)
        matching = [
            item for item in partner.json()["items"] if item["id"] == lead.json()["leadId"]
        ]
        self.assertEqual(len(matching), 1)
        self.assertNotIn("image", matching[0])

        deleted = self.client.delete(
            f"/api/v1/leads/{lead.json()['leadId']}", headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)

        lead_request["consentResults"] = False
        rejected = self.client.post(
            "/api/v1/leads", headers=self.headers, json=lead_request
        )
        self.assertEqual(rejected.status_code, 400)

    def test_partner_leads_requires_key(self) -> None:
        response = self.client.get(
            "/api/v1/partner/leads",
            params={"clinic_id": "demo-quito-norte"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
