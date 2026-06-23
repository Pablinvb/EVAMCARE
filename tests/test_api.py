import io
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import delete_session_leads
from backend.referrals import create_referral_token


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
        clinic = next(
            item for item in clinics.json()["items"] if item["demo"]
        )
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

    def test_partner_can_manage_clinic_slots_and_appointments(self) -> None:
        partner_headers = {"X-Partner-Key": "development-partner-key"}
        clinic_id = f"partner-{uuid4().hex[:10]}"
        clinic_response = self.client.put(
            "/api/v1/partner/clinics",
            headers=partner_headers,
            json={
                "id": clinic_id,
                "name": "Centro Dermatológico de Prueba",
                "city": "Quito",
                "address": "Av. de Prueba 123",
                "latitude": -0.1807,
                "longitude": -78.4678,
                "phone": "+59320000000",
                "whatsapp": "+593990000000",
                "services": ["Dermatología general", "Acné"],
            },
        )
        self.assertEqual(clinic_response.status_code, 200, clinic_response.text)
        self.assertTrue(clinic_response.json()["clinic"]["verified"])
        self.assertFalse(clinic_response.json()["clinic"]["demo"])

        starts_at = datetime.now(timezone.utc) + timedelta(days=3)
        slots_response = self.client.post(
            f"/api/v1/partner/clinics/{clinic_id}/availability",
            headers=partner_headers,
            json={"startsAt": [starts_at.isoformat()]},
        )
        self.assertEqual(slots_response.status_code, 201, slots_response.text)
        slot = slots_response.json()["items"][0]

        token = self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"image": ("face.jpg", io.BytesIO(synthetic_image()), "image/jpeg")},
        ).json()["referralToken"]
        appointment = self.client.post(
            "/api/v1/appointments",
            headers=self.headers,
            json={
                "clinicId": clinic_id,
                "referralToken": token,
                "fullName": "Paciente de Prueba",
                "phone": "+593990000111",
                "email": None,
                "preferredChannel": "whatsapp",
                "preferredTime": None,
                "latitude": -0.1807,
                "longitude": -78.4678,
                "distanceKm": 0,
                "consentContact": True,
                "consentLocation": True,
                "consentResults": True,
                "slotId": slot["id"],
            },
        )
        self.assertEqual(appointment.status_code, 201, appointment.text)
        appointment_id = appointment.json()["appointmentId"]

        partner_appointments = self.client.get(
            "/api/v1/partner/appointments",
            headers=partner_headers,
            params={"clinic_id": clinic_id},
        )
        self.assertEqual(partner_appointments.status_code, 200)
        self.assertEqual(partner_appointments.json()["items"][0]["id"], appointment_id)

        confirmed = self.client.patch(
            f"/api/v1/partner/appointments/{appointment_id}",
            headers=partner_headers,
            params={"clinic_id": clinic_id},
            json={"status": "confirmed"},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")

    def test_guidance_routes_and_store_recommendations(self) -> None:
        analysis = self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"image": ("face.jpg", io.BytesIO(synthetic_image()), "image/jpeg")},
        ).json()
        token = analysis["referralToken"]

        # Even visually severe signals must not trigger medical referral when
        # the user reports no symptoms/history and image quality is adequate.
        severe_visual_result = {
            "overall": 35,
            "skinType": "Mixta",
            "confidence": 90,
            "attentionZones": [{"type": "redness"}] * 7,
            "engine": {"version": "0.5.0"},
            "metrics": [
                {"name": "Hidratación", "score": 70, "status": "Estable"},
                {"name": "Textura", "score": 45, "status": "Atención"},
                {"name": "Poros", "score": 40, "status": "Prioridad"},
                {"name": "Imperfecciones", "score": 5, "status": "Prioridad"},
                {"name": "Pigmentación", "score": 25, "status": "Prioridad"},
                {"name": "Líneas visibles", "score": 70, "status": "Estable"},
                {"name": "Enrojecimiento", "score": 5, "status": "Prioridad"},
                {"name": "Balance sebáceo", "score": 50, "status": "Atención"},
            ],
        }
        severe_visual_token = create_referral_token(severe_visual_result)
        no_answers = self.client.post(
            "/api/v1/guidance",
            json={"referralToken": severe_visual_token, "answers": {}},
        )
        self.assertEqual(no_answers.status_code, 200, no_answers.text)
        self.assertEqual(
            no_answers.json()["guidance"]["route"], "cosmetic-care"
        )
        self.assertFalse(
            no_answers.json()["guidance"]["clinicalContextPresent"]
        )
        self.assertTrue(no_answers.json()["guidance"]["allowProducts"])

        low_quality = self.client.post(
            "/api/v1/guidance",
            json={"referralToken": token, "answers": {}},
        )
        self.assertEqual(low_quality.status_code, 200)
        self.assertIn(
            low_quality.json()["guidance"]["route"],
            {"cosmetic-care", "repeat-scan"},
        )
        self.assertNotIn(
            low_quality.json()["guidance"]["route"],
            {"dermatology", "urgent-care"},
        )

        urgent = self.client.post(
            "/api/v1/guidance",
            json={
                "referralToken": token,
                "answers": {"feverOrUnwell": True, "rapidlyWorsening": True},
            },
        )
        self.assertEqual(urgent.status_code, 200, urgent.text)
        self.assertEqual(urgent.json()["guidance"]["route"], "urgent-care")
        self.assertFalse(urgent.json()["guidance"]["allowProducts"])

        safe_result = {
            "overall": 82,
            "skinType": "Seca",
            "confidence": 88,
            "attentionZones": [],
            "engine": {"version": "0.3.0"},
            "metrics": [
                {"name": "Hidratación", "score": 55, "status": "Atención"},
                {"name": "Textura", "score": 72, "status": "Estable"},
                {"name": "Poros", "score": 85, "status": "Óptimo"},
                {"name": "Imperfecciones", "score": 90, "status": "Óptimo"},
                {"name": "Pigmentación", "score": 84, "status": "Óptimo"},
                {"name": "Líneas visibles", "score": 80, "status": "Óptimo"},
                {"name": "Enrojecimiento", "score": 90, "status": "Óptimo"},
                {"name": "Balance sebáceo", "score": 80, "status": "Óptimo"},
            ],
        }
        safe_token = create_referral_token(safe_result)
        cosmetic = self.client.post(
            "/api/v1/guidance",
            json={"referralToken": safe_token, "answers": {}},
        )
        self.assertEqual(cosmetic.status_code, 200, cosmetic.text)
        self.assertEqual(cosmetic.json()["guidance"]["route"], "cosmetic-care")
        self.assertTrue(cosmetic.json()["guidance"]["allowProducts"])
        self.assertEqual(
            cosmetic.json()["guidance"]["components"]["vision"]["weight"], 60
        )
        self.assertEqual(
            cosmetic.json()["guidance"]["components"]["symptoms"]["weight"], 25
        )
        self.assertEqual(
            cosmetic.json()["guidance"]["components"]["history"]["weight"], 15
        )

        medium = self.client.post(
            "/api/v1/guidance",
            json={
                "referralToken": safe_token,
                "answers": {
                    "itchSeverity": "intense_persistent",
                    "duration": "over_6_weeks",
                    "painLevel": "mild",
                },
            },
        )
        self.assertEqual(medium.status_code, 200, medium.text)
        self.assertEqual(medium.json()["guidance"]["route"], "dermatology")
        self.assertEqual(medium.json()["guidance"]["riskLevel"], "medium")

        history_saved = self.client.post(
            "/api/v1/guidance",
            headers=self.headers,
            json={
                "referralToken": safe_token,
                "answers": {
                    "marksChangingOrUnexplained": False,
                    "familyMelanoma": True,
                },
                "saveHistory": True,
            },
        )
        self.assertEqual(history_saved.status_code, 200, history_saved.text)
        self.assertTrue(history_saved.json()["stored"])
        history = self.client.get(
            "/api/v1/guidance-history", headers=self.headers
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["items"]), 1)
        self.assertFalse(
            history.json()["items"][0]["answers"]["marksChangingOrUnexplained"]
        )

        stores = self.client.get(
            "/api/v1/stores",
            params={"latitude": -0.1807, "longitude": -78.4678},
        )
        self.assertEqual(stores.status_code, 200, stores.text)
        real_stores = [
            item for item in stores.json()["items"] if item.get("online")
        ]
        self.assertEqual(len(real_stores), 5)
        store = next(item for item in real_stores if item["id"] == "fybeca")
        recommendations = self.client.get(
            f"/api/v1/stores/{store['id']}/recommendations",
            params={"referral_token": safe_token},
        )
        self.assertEqual(recommendations.status_code, 200, recommendations.text)
        self.assertGreater(len(recommendations.json()["products"]), 0)
        self.assertEqual(
            recommendations.json()["routine"]["skinType"], "Seca"
        )
        steps = {
            product["routineStep"]
            for product in recommendations.json()["products"]
        }
        self.assertIn("moisturize", steps)
        for product in recommendations.json()["products"]:
            self.assertIn("Seca", product["skinTypes"])
            self.assertTrue(product["sourceUrl"].startswith("https://"))
            self.assertTrue(product["externalReference"])
        self.assertTrue(
            any(
                product["category"] == "sunscreen"
                for product in recommendations.json()["products"]
            )
        )

        # Every connected retailer must provide the three essential steps for
        # an equilibrated-skin routine before it is offered as a complete shop.
        balanced_result = dict(safe_result)
        balanced_result["skinType"] = "Equilibrada"
        balanced_token = create_referral_token(balanced_result)
        for retailer in real_stores:
            response = self.client.get(
                f"/api/v1/stores/{retailer['id']}/recommendations",
                params={"referral_token": balanced_token},
            )
            self.assertEqual(response.status_code, 200, response.text)
            retailer_steps = {
                product["routineStep"]
                for product in response.json()["products"]
            }
            self.assertTrue(
                {"cleanse", "moisturize", "protect"}.issubset(retailer_steps),
                f"{retailer['name']} no cubre la rutina esencial: {retailer_steps}",
            )

    def test_appointment_uses_available_slot(self) -> None:
        token = self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"image": ("face.jpg", io.BytesIO(synthetic_image()), "image/jpeg")},
        ).json()["referralToken"]
        clinics = self.client.get(
            "/api/v1/clinics",
            params={"latitude": -0.1807, "longitude": -78.4678},
        ).json()["items"]
        clinic = clinics[0]
        slots = self.client.get(
            f"/api/v1/clinics/{clinic['id']}/availability"
        ).json()["items"]
        self.assertGreater(len(slots), 0)
        request = {
            "clinicId": clinic["id"],
            "referralToken": token,
            "fullName": "Paciente Agenda",
            "phone": "+593990000222",
            "email": None,
            "preferredChannel": "phone",
            "preferredTime": None,
            "latitude": -0.1807,
            "longitude": -78.4678,
            "distanceKm": clinic["distanceKm"],
            "consentContact": True,
            "consentLocation": True,
            "consentResults": True,
            "slotId": slots[0]["id"],
        }
        appointment = self.client.post(
            "/api/v1/appointments", headers=self.headers, json=request
        )
        self.assertEqual(appointment.status_code, 201, appointment.text)
        self.assertEqual(appointment.json()["status"], "requested")
        remaining = self.client.get(
            f"/api/v1/clinics/{clinic['id']}/availability"
        ).json()["items"]
        self.assertNotIn(slots[0]["id"], [slot["id"] for slot in remaining])


if __name__ == "__main__":
    unittest.main()
