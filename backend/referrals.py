from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from .config import REFERRAL_TOKEN_SECRET, REFERRAL_TOKEN_TTL_SECONDS


def create_referral_token(result: dict[str, Any]) -> str:
    priorities = sorted(result["metrics"], key=lambda item: item["score"])[:3]
    payload = {
        "exp": int(time.time()) + REFERRAL_TOKEN_TTL_SECONDS,
        "summary": {
            "overall": result["overall"],
            "skinType": result["skinType"],
            "confidence": result["confidence"],
            "priorities": [
                {"name": item["name"], "score": item["score"], "status": item["status"]}
                for item in priorities
            ],
            "metrics": {
                item["name"]: item["score"]
                for item in result["metrics"]
            },
            "attentionZoneCount": len(result.get("attentionZones", [])),
            "engineVersion": result.get("engine", {}).get("version"),
        },
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        REFERRAL_TOKEN_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{encoded}.{_encode(signature)}"


def verify_referral_token(token: str) -> dict[str, Any]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(
            REFERRAL_TOKEN_SECRET.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_decode(supplied_signature), expected):
            raise ValueError("signature")
        payload = json.loads(_decode(encoded))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return payload["summary"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Token de derivación inválido o vencido.") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
