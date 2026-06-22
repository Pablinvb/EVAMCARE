from __future__ import annotations

from typing import Any


def evaluate_guidance(
    summary: dict[str, Any], answers: dict[str, Any]
) -> dict[str, Any]:
    """Return a transparent orientation score, not a medical diagnosis.

    The requested 60/25/15 architecture is preserved, but the unvalidated
    computer-vision component is capped so it cannot create a high-priority
    route by itself. Critical self-reported warning signs always override the
    numeric score.
    """

    critical_reasons = _critical_reasons(answers)
    symptom_reasons, symptom_score = _symptom_score(answers)
    history_reasons, history_score = _history_score(answers)
    visual_reasons, visual_score = _visual_score(summary)

    weighted = {
        "vision": round(visual_score * 0.60, 1),
        "symptoms": round(symptom_score * 0.25, 1),
        "history": round(history_score * 0.15, 1),
    }
    total = round(sum(weighted.values()), 1)

    # Prior skin cancer or immunosuppression lowers the consultation threshold,
    # but neither is labelled an emergency in isolation.
    elevated_history = answers.get("personalSkinCancer", False) or answers.get(
        "immunosuppressed", False
    )
    # Computer vision is supportive evidence only. A medical route always
    # requires at least one symptom/history signal or a critical override.
    has_clinical_context = (
        bool(critical_reasons) or symptom_score >= 20 or history_score > 0
    )

    if critical_reasons:
        route = "urgent-care"
        level = "high"
        title = "Consulta dermatológica prioritaria"
        message = (
            "Tus respuestas incluyen una señal de alerta que necesita valoración "
            "profesional pronta. Esta orientación no identifica la causa. Si hay "
            "dificultad para respirar o hinchazón de labios o lengua, utiliza los "
            "servicios de emergencia."
        )
    elif has_clinical_context and (
        total >= 65 or (elevated_history and symptom_score >= 35)
    ):
        route = "urgent-care"
        level = "high"
        title = "Consulta dermatológica prioritaria"
        message = (
            "La combinación de síntomas, antecedentes y señales visuales supera "
            "el umbral de prioridad. Solicita una valoración profesional pronta."
        )
    elif has_clinical_context and (
        total >= 35 or symptom_score >= 40 or elevated_history
    ):
        route = "dermatology"
        level = "medium"
        title = "Consulta dermatológica recomendada"
        message = (
            "La combinación de duración, molestias, antecedentes o señales "
            "visuales justifica una consulta. No significa que exista una "
            "enfermedad específica."
        )
    elif summary.get("confidence", 0) < 45:
        route = "repeat-scan"
        level = "quality"
        title = "Repite el escaneo"
        message = (
            "La captura no tiene calidad suficiente para orientar productos. "
            "Repítela con luz frontal y mayor nitidez."
        )
    else:
        route = "cosmetic-care"
        level = "low"
        title = "Rutina cosmética personalizada"
        if visual_score >= 45:
            message = (
                "La fotografía muestra variaciones visuales, pero no reportaste "
                "síntomas ni antecedentes que justifiquen una derivación. Puedes "
                "comenzar con autocuidado cosmético y vigilar la evolución. Consulta "
                "si aparecen cambios, dolor, sangrado, picazón o falta de mejoría."
            )
        else:
            message = (
                "No reportaste señales de alerta. Puedes comenzar con autocuidado "
                "cosmético y consultar si aparecen cambios, dolor, sangrado, "
                "picazón intensa o falta de mejoría."
            )

    reasons = critical_reasons or (
        symptom_reasons + history_reasons + visual_reasons
    )
    if not reasons:
        reasons = _cosmetic_priorities(summary)

    decision_score = max(total, 85.0) if critical_reasons else total
    return {
        "route": route,
        "riskLevel": level,
        "riskScore": decision_score,
        "baseScore": total,
        "components": {
            "vision": {
                "raw": round(visual_score, 1),
                "weight": 60,
                "contribution": weighted["vision"],
            },
            "symptoms": {
                "raw": round(symptom_score, 1),
                "weight": 25,
                "contribution": weighted["symptoms"],
            },
            "history": {
                "raw": round(history_score, 1),
                "weight": 15,
                "contribution": weighted["history"],
            },
        },
        "criticalOverride": bool(critical_reasons),
        "clinicalContextPresent": has_clinical_context,
        "reasons": reasons,
        "title": title,
        "message": message,
        "allowProducts": route == "cosmetic-care",
        "allowDermatologyBooking": route in {"dermatology", "urgent-care"},
        "method": "orientation-score-v2",
        "disclaimer": (
            "Puntuación orientativa no validada clínicamente; no diagnostica ni "
            "descarta enfermedades."
        ),
    }


def _critical_reasons(answers: dict[str, Any]) -> list[str]:
    reasons = []
    if answers.get("changingBleedingSpot"):
        reasons.append("Lesión nueva o cambiante que sangra")
    if answers.get("notHealing"):
        reasons.append("Lesión que no cicatriza o reaparece")
    if answers.get("eyesMouthBlisters"):
        reasons.append("Ampollas o afectación de ojos o boca")
    if answers.get("rapidlyWorsening"):
        reasons.append("Empeoramiento rápido")
    if answers.get("feverOrUnwell") and (
        answers.get("inflammation")
        or answers.get("discharge")
        or answers.get("eyesMouthBlisters")
    ):
        reasons.append("Fiebre o malestar junto con manifestaciones cutáneas")
    return reasons


def _symptom_score(answers: dict[str, Any]) -> tuple[list[str], float]:
    points = 0.0
    reasons: list[str] = []

    itch = answers.get("itchSeverity", "none")
    if itch == "intense_persistent":
        points += 45
        reasons.append("Picazón intensa o persistente")
    elif itch == "mild":
        points += 12

    duration = answers.get("duration", "under_2_weeks")
    if duration == "over_6_weeks":
        points += 40
        reasons.append("Más de 6 semanas sin mejorar")
    elif duration == "2_to_6_weeks":
        points += 15

    pain = answers.get("painLevel", "none")
    if pain == "moderate_severe":
        points += 45
        reasons.append("Dolor moderado o intenso")
    elif pain == "mild":
        points += 12

    for key, label, value in [
        ("inflammation", "Inflamación importante", 25),
        ("discharge", "Secreción o pus", 40),
        (
            "marksChangingOrUnexplained",
            "Marcas recientes sin causa clara o que cambian/crecen/molestan",
            30,
        ),
        ("persistentConcern", "Problema que genera preocupación importante", 15),
    ]:
        if answers.get(key):
            points += value
            reasons.append(label)

    return reasons, min(100.0, points)


def _history_score(answers: dict[str, Any]) -> tuple[list[str], float]:
    points = 0.0
    reasons: list[str] = []
    if answers.get("personalSkinCancer"):
        points += 100
        reasons.append("Antecedente personal de cáncer o lesión precancerosa")
    if answers.get("familyMelanoma"):
        points += 40
        reasons.append("Antecedente familiar de melanoma o cáncer de piel")
    if answers.get("immunosuppressed"):
        points += 70
        reasons.append("Condición o tratamiento que afecta el sistema inmunológico")
    return reasons, min(100.0, points)


def _visual_score(summary: dict[str, Any]) -> tuple[list[str], float]:
    metrics = summary.get("metrics", {})
    imperfection_need = 100 - metrics.get("Imperfecciones", 100)
    redness_need = 100 - metrics.get("Enrojecimiento", 100)
    pigmentation_need = 100 - metrics.get("Pigmentación", 100)
    zones = min(100, summary.get("attentionZoneCount", 0) * 12)
    raw = (
        imperfection_need * 0.35
        + redness_need * 0.30
        + pigmentation_need * 0.15
        + zones * 0.20
    )
    # The current image model is not clinically validated. It can support a
    # recommendation but cannot independently create a high-risk route.
    score = min(50.0, raw)
    reasons = []
    if imperfection_need >= 65 and zones >= 36:
        reasons.append("Variaciones visibles compatibles con imperfecciones extensas")
    if redness_need >= 65 and zones >= 36:
        reasons.append("Enrojecimiento visual extendido")
    if pigmentation_need >= 65 and zones >= 24:
        reasons.append("Variación de tono localizada")
    return reasons, score


def _cosmetic_priorities(summary: dict[str, Any]) -> list[str]:
    allowed = {
        "Hidratación",
        "Textura",
        "Poros",
        "Pigmentación",
        "Líneas visibles",
        "Balance sebáceo",
    }
    priorities = [
        item["name"]
        for item in summary.get("priorities", [])
        if item["name"] in allowed
    ]
    return priorities or ["Mantenimiento cosmético general"]


def recommend_products(
    summary: dict[str, Any], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    metrics = summary.get("metrics", {})
    skin_type = summary.get("skinType", "Equilibrada")
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
        skin_types = product.get("skinTypes", [])
        skin_match = skin_type in skin_types or not skin_types
        if not skin_match:
            continue
        matches = [concern for concern in product["concerns"] if concern in concerns]
        score = len(matches) * 10 + 18
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
    ranked.sort(key=lambda item: (-item["matchScore"], item["price"] or 9999))

    # Build a minimal routine before adding optional treatment products.
    selected: list[dict[str, Any]] = []
    for step in ("cleanse", "moisturize", "protect"):
        candidate = next(
            (item for item in ranked if item.get("routineStep") == step),
            None,
        )
        if candidate:
            selected.append(candidate)
    treatment = next(
        (
            item
            for item in ranked
            if item.get("routineStep") == "treat" and item not in selected
        ),
        None,
    )
    if treatment:
        selected.insert(min(1, len(selected)), treatment)
    return selected[:4]


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
