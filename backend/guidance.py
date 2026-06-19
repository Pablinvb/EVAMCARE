from __future__ import annotations

from typing import Any


URGENT_FLAGS = {
    "rapidlyWorsening": "Empeoramiento rápido",
    "feverOrUnwell": "Fiebre o malestar general",
    "pusWarmthSwelling": "Secreción, calor o hinchazón",
    "eyesMouthBlisters": "Ampollas o afectación de ojos o boca",
}

DERMATOLOGY_FLAGS = {
    "changingBleedingSpot": "Mancha o lesión nueva, cambiante o con sangrado",
    "notHealing": "Lesión que no cicatriza",
    "deepPainfulLesions": "Lesiones profundas o dolorosas",
    "scarring": "Cicatrices o marcas persistentes",
    "persistentConcern": "Problema persistente o que causa preocupación",
}


def evaluate_guidance(
    summary: dict[str, Any], answers: dict[str, bool]
) -> dict[str, Any]:
    urgent_reasons = [
        label for key, label in URGENT_FLAGS.items() if answers.get(key, False)
    ]
    dermatology_reasons = [
        label for key, label in DERMATOLOGY_FLAGS.items() if answers.get(key, False)
    ]
    metrics = summary.get("metrics", {})
    imperfection_score = metrics.get("Imperfecciones", 100)
    redness_score = metrics.get("Enrojecimiento", 100)
    confidence = summary.get("confidence", 0)

    visual_reasons: list[str] = []
    if imperfection_score <= 35 and summary.get("attentionZoneCount", 0) >= 3:
        visual_reasons.append(
            "Se observaron múltiples variaciones visibles asociadas a imperfecciones"
        )
    if redness_score <= 30 and summary.get("attentionZoneCount", 0) >= 4:
        visual_reasons.append("Se observó enrojecimiento visual extendido")

    if urgent_reasons:
        return {
            "route": "urgent-care",
            "priority": "prompt",
            "reasons": urgent_reasons,
            "title": "Busca valoración médica pronta",
            "message": (
                "Tus respuestas incluyen señales que no deben orientarse únicamente "
                "con productos cosméticos. Busca atención médica pronta; si presentas "
                "dificultad para respirar o hinchazón de labios o lengua, utiliza "
                "servicios de emergencia."
            ),
            "allowProducts": False,
            "allowDermatologyBooking": True,
        }

    if dermatology_reasons or visual_reasons:
        return {
            "route": "dermatology",
            "priority": "recommended",
            "reasons": dermatology_reasons + visual_reasons,
            "title": "Te conviene consultar con dermatología",
            "message": (
                "La recomendación se basa en tus respuestas y señales visibles; "
                "no constituye un diagnóstico. Puedes revisar centros cercanos "
                "y solicitar una cita."
            ),
            "allowProducts": False,
            "allowDermatologyBooking": True,
        }

    if confidence < 45:
        return {
            "route": "repeat-scan",
            "priority": "quality",
            "reasons": ["La fotografía no tuvo confianza suficiente"],
            "title": "Repite el escaneo",
            "message": (
                "La calidad no permite orientar productos ni consulta con suficiente "
                "consistencia. Repite la captura con luz frontal y mayor nitidez."
            ),
            "allowProducts": False,
            "allowDermatologyBooking": True,
        }

    cosmetic_priorities = [
        item["name"]
        for item in summary.get("priorities", [])
        if item["name"] in {
            "Hidratación",
            "Textura",
            "Poros",
            "Pigmentación",
            "Líneas visibles",
            "Balance sebáceo",
        }
    ]
    return {
        "route": "cosmetic-care",
        "priority": "routine",
        "reasons": cosmetic_priorities or ["Mantenimiento cosmético general"],
        "title": "Puedes empezar con una rutina cosmética",
        "message": (
            "No indicaste señales de alerta. Puedes explorar una rutina sencilla "
            "y productos cosméticos cercanos. Consulta si aparece dolor, sangrado, "
            "cambio rápido o si el problema persiste."
        ),
        "allowProducts": True,
        "allowDermatologyBooking": False,
    }


def recommend_products(
    summary: dict[str, Any], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    metrics = summary.get("metrics", {})
    concerns: list[str] = []
    mapping = {
        "Hidratación": "hydration",
        "Textura": "texture",
        "Poros": "pores",
        "Pigmentación": "tone",
        "Líneas visibles": "fine-lines",
        "Balance sebáceo": "oil-balance",
    }
    for metric, concern in mapping.items():
        if metrics.get(metric, 100) < 75:
            concerns.append(concern)
    concerns.extend(["gentle-care", "sun-protection"])

    ranked = []
    for product in products:
        matches = [concern for concern in product["concerns"] if concern in concerns]
        score = len(matches) * 10
        if product["category"] == "sunscreen":
            score += 12
        if product["category"] == "moisturizer":
            score += 7
        ranked.append(
            {
                **product,
                "matchScore": score,
                "matchedConcerns": matches,
                "reason": _product_reason(product, matches),
            }
        )
    ranked.sort(key=lambda item: (-item["matchScore"], item["price"]))
    return ranked[:4]


def _product_reason(product: dict[str, Any], matches: list[str]) -> str:
    if product["category"] == "sunscreen":
        return "La protección solar complementa cualquier rutina cosmética."
    if "hydration" in matches:
        return "Compatible con la prioridad visual de hidratación."
    if "oil-balance" in matches or "pores" in matches:
        return "Pensado para una rutina ligera y balance de brillo aparente."
    if "tone" in matches:
        return "Complementa una rutina orientada a uniformidad visual del tono."
    if "texture" in matches:
        return "Complementa una rutina cosmética de textura."
    return "Opción suave para una rutina básica."
