from typing import Any


CLINICAL_BLOCKERS = [
    {"id": "CR-001", "status": "open", "title": "Finalidad médica y población no aprobadas"},
    {"id": "CR-002", "status": "open", "title": "Motor heurístico sin modelo clínico entrenado"},
    {"id": "CR-003", "status": "open", "title": "Segmentación cutánea no validada"},
    {"id": "CR-004", "status": "open", "title": "Protocolo de captura no validado"},
    {"id": "CR-005", "status": "open", "title": "Sin referencia dermatológica adjudicada"},
    {"id": "CR-006", "status": "open", "title": "Sin conjunto de prueba clínica externo"},
    {"id": "CR-007", "status": "open", "title": "Sin métricas de desempeño y equidad"},
    {"id": "CR-008", "status": "open", "title": "Sin registro regulado de modelos"},
    {"id": "CR-009", "status": "open", "title": "Sin controles de sistema clínico"},
    {"id": "CR-010", "status": "open", "title": "Recomendaciones aún no revisadas clínicamente"},
    {"id": "CR-011", "status": "open", "title": "Expediente de riesgos y usabilidad incompleto"},
    {"id": "CR-012", "status": "open", "title": "Sin aprobación ética ni autorización sanitaria"},
]


def get_clinical_status() -> dict[str, Any]:
    completed = sum(item["status"] == "closed" for item in CLINICAL_BLOCKERS)
    return {
        "status": "research_only",
        "clinicallyValidated": False,
        "medicalDeviceAuthorized": False,
        "completedRequirements": completed,
        "totalRequirements": len(CLINICAL_BLOCKERS),
        "blockers": CLINICAL_BLOCKERS,
        "intendedUseDraft": (
            "Apoyo profesional para cuantificar severidad visible del acné "
            "facial en adultos; finalidad pendiente de aprobación."
        ),
    }
