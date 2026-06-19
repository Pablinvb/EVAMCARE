from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class RegionStats:
    mean: float
    std: float
    red: float
    saturation: float
    dark_ratio: float
    highlight_ratio: float
    gradient: float


class SkinAnalyzer:
    """Experimental photographic skin-signal analyzer.

    The Haar detector finds the largest frontal face. The metrics use classical
    image statistics over conservative skin regions; they are not medical
    classifiers and intentionally avoid disease labels.
    """

    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_detector = cv2.CascadeClassifier(cascade_path)
        if self.face_detector.empty():
            raise RuntimeError("No se pudo cargar el detector facial de OpenCV.")

    def analyze(self, image_bgr: np.ndarray) -> dict[str, Any]:
        image_bgr = self._normalize_size(image_bgr)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_detector.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(100, 100),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        face_count = len(faces)
        if face_count:
            x, y, width, height = max(faces, key=lambda item: item[2] * item[3])
            x, y, width, height = self._expand_box(
                x, y, width, height, image_bgr.shape[1], image_bgr.shape[0]
            )
            face = image_bgr[y : y + height, x : x + width]
            detection_mode = "face-detected"
        else:
            face = self._center_face_crop(image_bgr)
            detection_mode = "guided-fallback"

        quality = self._quality(image_bgr, face)
        signals = self._skin_signals(face)
        metrics = self._metrics(signals)
        weights = [0.15, 0.20, 0.15, 0.20, 0.15, 0.15]
        overall = round(sum(item["score"] * weights[index] for index, item in enumerate(metrics[:6])))
        confidence = round(
            clamp(
                (
                    quality["light"]
                    + quality["contrast"]
                    + quality["sharpness"]
                    + quality["framing"]
                )
                / 4
                - (0 if face_count else 22)
            )
        )
        skin_type = self._skin_type(signals)

        warnings: list[str] = []
        if not face_count:
            warnings.append(
                "No se detectó automáticamente un rostro frontal; se usó el encuadre guiado."
            )
        if quality["light"] < 52:
            warnings.append("La iluminación puede reducir la consistencia del resultado.")
        if quality["sharpness"] < 38:
            warnings.append("La imagen presenta poca nitidez.")
        if face_count > 1:
            warnings.append("Se detectaron varios rostros; se analizó únicamente el más grande.")

        return {
            "overall": overall,
            "skinType": skin_type,
            "confidence": confidence,
            "metrics": metrics,
            "needs": {key: round(clamp(value)) for key, value in signals.items()},
            "quality": {key: round(value) for key, value in quality.items()},
            "face": {
                "detected": bool(face_count),
                "count": face_count,
                "mode": detection_mode,
            },
            "warnings": warnings,
            "engine": {
                "name": "DermaScan Classical Vision",
                "version": "0.2.0",
                "medicalDevice": False,
            },
        }

    @staticmethod
    def _normalize_size(image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        longest = max(height, width)
        if longest <= 1400:
            return image
        scale = 1400 / longest
        return cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _expand_box(
        x: int, y: int, width: int, height: int, image_width: int, image_height: int
    ) -> tuple[int, int, int, int]:
        horizontal = round(width * 0.08)
        top = round(height * 0.15)
        bottom = round(height * 0.08)
        x1 = max(0, x - horizontal)
        y1 = max(0, y - top)
        x2 = min(image_width, x + width + horizontal)
        y2 = min(image_height, y + height + bottom)
        return x1, y1, x2 - x1, y2 - y1

    @staticmethod
    def _center_face_crop(image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        x1, x2 = round(width * 0.20), round(width * 0.80)
        y1, y2 = round(height * 0.10), round(height * 0.78)
        return image[y1:y2, x1:x2]

    @staticmethod
    def _quality(image: np.ndarray, face: np.ndarray) -> dict[str, float]:
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        contrast_raw = float(np.std(gray))
        laplacian = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        image_area = image.shape[0] * image.shape[1]
        face_area = face.shape[0] * face.shape[1]
        face_ratio = face_area / max(1, image_area)
        return {
            "light": clamp(100 - abs(brightness - 145) * 1.3),
            "contrast": clamp(contrast_raw * 2.35),
            "sharpness": clamp(np.sqrt(max(0, laplacian)) * 4.2),
            "framing": clamp(100 - abs(face_ratio - 0.36) * 180),
            "brightness": brightness,
        }

    def _skin_signals(self, face: np.ndarray) -> dict[str, float]:
        forehead = self._region(face, 0.28, 0.14, 0.72, 0.31)
        left_cheek = self._region(face, 0.12, 0.43, 0.40, 0.69)
        right_cheek = self._region(face, 0.60, 0.43, 0.88, 0.69)
        t_zone = self._region(face, 0.41, 0.26, 0.59, 0.68)
        eye_band = self._region(face, 0.16, 0.31, 0.84, 0.45)
        whole_face = self._region(face, 0.10, 0.12, 0.90, 0.77)

        cheek_std = (left_cheek.std + right_cheek.std) / 2
        cheek_grad = (left_cheek.gradient + right_cheek.gradient) / 2
        cheek_red = (left_cheek.red + right_cheek.red) / 2
        cheek_dark = (left_cheek.dark_ratio + right_cheek.dark_ratio) / 2
        cheek_mean = (left_cheek.mean + right_cheek.mean) / 2

        hydration = clamp(
            (cheek_std - 18) * 2
            + (cheek_grad - 8) * 2.2
            + max(0, 115 - whole_face.mean) * 0.25
        )
        oil = clamp(t_zone.highlight_ratio * 620 + max(0, t_zone.mean - cheek_mean) * 1.4)
        texture = clamp((cheek_grad - 7) * 3.6 + (cheek_std - 15) * 1.5)
        pores = clamp((cheek_grad - 8) * 3.5 + cheek_dark * 240 + cheek_std - 18)
        imperfections = clamp((cheek_red - 8) * 5 + (whole_face.saturation - 0.22) * 80)
        redness = clamp((cheek_red - 5) * 4.2)
        pigmentation = clamp(cheek_dark * 300 + (cheek_std - 22) * 1.8)
        lines = clamp((eye_band.gradient - 9) * 3.4 + (forehead.gradient - 8) * 2.1)
        return {
            "hydrationNeed": hydration,
            "oilSignal": oil,
            "textureNeed": texture,
            "poreNeed": pores,
            "acneNeed": imperfections,
            "rednessNeed": redness,
            "pigmentationNeed": pigmentation,
            "lineNeed": lines,
        }

    @staticmethod
    def _region(
        image: np.ndarray, x0: float, y0: float, x1: float, y1: float
    ) -> RegionStats:
        height, width = image.shape[:2]
        region = image[
            round(height * y0) : max(round(height * y0) + 1, round(height * y1)),
            round(width * x0) : max(round(width * x0) + 1, round(width * x1)),
        ]
        rgb = cv2.cvtColor(region, cv2.COLOR_BGR2RGB).astype(np.float32)
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).astype(np.float32)
        red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        saturation = np.divide(
            maximum - minimum,
            maximum,
            out=np.zeros_like(maximum),
            where=maximum > 0,
        )
        gradient_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        gradient = np.sqrt(gradient_x**2 + gradient_y**2)
        return RegionStats(
            mean=float(gray.mean()),
            std=float(gray.std()),
            red=float(np.maximum(0, red - (green + blue) / 2).mean()),
            saturation=float(saturation.mean()),
            dark_ratio=float((gray < 75).mean()),
            highlight_ratio=float(((gray > 205) & ((maximum - minimum) < 38)).mean()),
            gradient=float(gradient.mean() / 4),
        )

    @staticmethod
    def _metric(name: str, icon: str, score: float, description: str, need: float) -> dict[str, Any]:
        normalized = round(clamp(score))
        status = (
            "Óptimo"
            if normalized >= 80
            else "Estable"
            if normalized >= 65
            else "Atención"
            if normalized >= 45
            else "Prioridad"
        )
        return {
            "name": name,
            "icon": icon,
            "score": normalized,
            "need": round(clamp(need)),
            "description": description,
            "status": status,
        }

    def _metrics(self, signal: dict[str, float]) -> list[dict[str, Any]]:
        return [
            self._metric("Hidratación", "◒", 100 - signal["hydrationNeed"], "Confort y apariencia de sequedad", signal["hydrationNeed"]),
            self._metric("Textura", "⌁", 100 - signal["textureNeed"], "Uniformidad visual de la superficie", signal["textureNeed"]),
            self._metric("Poros", "◌", 100 - signal["poreNeed"], "Visibilidad aparente en mejillas", signal["poreNeed"]),
            self._metric("Imperfecciones", "·", 100 - signal["acneNeed"], "Señales rojizas compatibles con brotes", signal["acneNeed"]),
            self._metric("Pigmentación", "◐", 100 - signal["pigmentationNeed"], "Uniformidad visible del tono", signal["pigmentationNeed"]),
            self._metric("Líneas visibles", "≋", 100 - signal["lineNeed"], "Contrastes finos en frente y contorno", signal["lineNeed"]),
            self._metric("Enrojecimiento", "●", 100 - signal["rednessNeed"], "Variación rojiza en mejillas", signal["rednessNeed"]),
            self._metric("Balance sebáceo", "✦", 100 - abs(signal["oilSignal"] - 32) * 1.4, "Brillo aparente en la zona T", signal["oilSignal"]),
        ]

    @staticmethod
    def _skin_type(signal: dict[str, float]) -> str:
        oil = signal["oilSignal"]
        hydration = signal["hydrationNeed"]
        if oil > 58 and hydration > 52:
            return "Mixta deshidratada"
        if oil > 58:
            return "Grasa"
        if hydration > 58:
            return "Seca"
        if oil > 38:
            return "Mixta"
        return "Equilibrada"
