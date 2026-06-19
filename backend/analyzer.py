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
        image_height, image_width = image_bgr.shape[:2]
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
            x, y, width, height = self._center_face_box(image_bgr)
            face = image_bgr[y : y + height, x : x + width]
            detection_mode = "guided-fallback"

        quality = self._quality(image_bgr, face)
        signals = self._skin_signals(face)
        attention_zones = self._attention_zones(
            face,
            (x, y, width, height),
            (image_width, image_height),
        )
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
                "box": {
                    "x": round(x / image_width, 4),
                    "y": round(y / image_height, 4),
                    "width": round(width / image_width, 4),
                    "height": round(height / image_height, 4),
                },
            },
            "attentionZones": attention_zones,
            "attentionMap": {
                "derivedFromImage": True,
                "coordinateSpace": "normalized-original-image",
                "method": "local-color-and-microcontrast-v1",
                "zoneCount": len(attention_zones),
            },
            "warnings": warnings,
            "engine": {
                "name": "DermaScan Classical Vision",
                "version": "0.4.0",
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
    def _center_face_box(image: np.ndarray) -> tuple[int, int, int, int]:
        height, width = image.shape[:2]
        x1, x2 = round(width * 0.20), round(width * 0.80)
        y1, y2 = round(height * 0.10), round(height * 0.78)
        return x1, y1, x2 - x1, y2 - y1

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

    def _attention_zones(
        self,
        face: np.ndarray,
        face_box: tuple[int, int, int, int],
        image_size: tuple[int, int],
    ) -> list[dict[str, Any]]:
        """Locate visible pixel anomalies and return their real image positions.

        These detections describe photographic signals (relative redness,
        localized darkness and microcontrast). They do not identify lesions or
        diseases. Every returned point comes from a connected component in the
        submitted image; no template coordinates are used.
        """
        face_height, face_width = face.shape[:2]
        if face_height < 80 or face_width < 80:
            return []

        mask = self._facial_skin_mask(face_width, face_height)
        lab = cv2.cvtColor(face, cv2.COLOR_BGR2LAB).astype(np.float32)
        lightness, red_green, _ = cv2.split(lab)
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY).astype(np.float32)

        blur_size = self._odd_kernel(max(21, round(min(face_width, face_height) * 0.11)))
        local_light = cv2.GaussianBlur(lightness, (blur_size, blur_size), 0)
        local_red = cv2.GaussianBlur(red_green, (blur_size, blur_size), 0)
        local_gray = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

        relative_redness = red_green - local_red
        localized_darkness = local_light - lightness
        microcontrast = cv2.absdiff(gray, local_gray)

        maps = [
            {
                "type": "redness",
                "label": "Enrojecimiento visible",
                "color": "#e96f61",
                "map": relative_redness,
                "percentile": 94.5,
                "absolute": 3.5,
                "min_area": 8,
                "max_area_ratio": 0.06,
                "evidence": "Variación rojiza localizada respecto a la piel cercana",
            },
            {
                "type": "pigmentation",
                "label": "Variación de tono",
                "color": "#9574cf",
                "map": localized_darkness,
                "percentile": 95.0,
                "absolute": 7.0,
                "min_area": 10,
                "max_area_ratio": 0.08,
                "evidence": "Zona más oscura que su entorno inmediato",
            },
            {
                "type": "texture",
                "label": "Microtextura visible",
                "color": "#e4b648",
                "map": microcontrast,
                "percentile": 96.0,
                "absolute": 9.0,
                "min_area": 6,
                "max_area_ratio": 0.035,
                "evidence": "Contraste fino localizado en la superficie visible",
            },
        ]

        zones: list[dict[str, Any]] = []
        for definition in maps:
            zones.extend(
                self._extract_hotspots(
                    definition,
                    mask,
                    face_box,
                    image_size,
                    max_zones=3,
                )
            )

        zones.sort(key=lambda item: item["severity"], reverse=True)
        return self._deduplicate_zones(zones, maximum=8)

    @staticmethod
    def _facial_skin_mask(width: int, height: int) -> np.ndarray:
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.ellipse(
            mask,
            (round(width * 0.50), round(height * 0.48)),
            (round(width * 0.41), round(height * 0.43)),
            0,
            0,
            360,
            255,
            -1,
        )
        # Exclude eyes, eyebrows, nostrils and lips: their natural contrast
        # should not become a skin finding.
        for center, axes in [
            ((0.31, 0.38), (0.16, 0.09)),
            ((0.69, 0.38), (0.16, 0.09)),
            ((0.50, 0.57), (0.10, 0.08)),
            ((0.50, 0.72), (0.20, 0.09)),
        ]:
            cv2.ellipse(
                mask,
                (round(width * center[0]), round(height * center[1])),
                (round(width * axes[0]), round(height * axes[1])),
                0,
                0,
                360,
                0,
                -1,
            )
        mask[: round(height * 0.10), :] = 0
        mask[round(height * 0.84) :, :] = 0
        return mask

    @staticmethod
    def _odd_kernel(value: int) -> int:
        return value if value % 2 else value + 1

    def _extract_hotspots(
        self,
        definition: dict[str, Any],
        mask: np.ndarray,
        face_box: tuple[int, int, int, int],
        image_size: tuple[int, int],
        max_zones: int,
    ) -> list[dict[str, Any]]:
        score_map = definition["map"]
        valid_values = score_map[mask > 0]
        if valid_values.size < 100:
            return []
        threshold = max(
            float(definition["absolute"]),
            float(np.percentile(valid_values, definition["percentile"])),
        )
        binary = ((score_map >= threshold) & (mask > 0)).astype(np.uint8) * 255
        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
        )
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
        face_area = mask.shape[0] * mask.shape[1]
        max_area = face_area * definition["max_area_ratio"]
        x0, y0, face_width, face_height = face_box
        image_width, image_height = image_size
        candidates: list[dict[str, Any]] = []

        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < definition["min_area"] or area > max_area:
                continue
            component_values = score_map[labels == component]
            peak = float(np.percentile(component_values, 90))
            severity = round(clamp(35 + (peak - threshold) * 6 + np.sqrt(area) * 1.8))
            cx, cy = centroids[component]
            component_width = int(stats[component, cv2.CC_STAT_WIDTH])
            component_height = int(stats[component, cv2.CC_STAT_HEIGHT])
            # Long thin components usually represent the jaw/hair boundary,
            # compression seams or shadows, rather than localized skin signals.
            if (
                component_width > face_width * 0.28
                or component_height > face_height * 0.28
            ):
                continue
            radius_pixels = max(7.0, max(component_width, component_height) * 0.65)
            absolute_x = x0 + float(cx)
            absolute_y = y0 + float(cy)
            candidates.append(
                {
                    "type": definition["type"],
                    "label": definition["label"],
                    "color": definition["color"],
                    "x": round(absolute_x / image_width, 4),
                    "y": round(absolute_y / image_height, 4),
                    "radius": round(radius_pixels / max(image_width, image_height), 4),
                    "severity": severity,
                    "level": (
                        "alta" if severity >= 75 else "media" if severity >= 50 else "leve"
                    ),
                    "facialRegion": self._facial_region(float(cx), float(cy), face_width, face_height),
                    "evidence": definition["evidence"],
                }
            )
        candidates.sort(key=lambda item: item["severity"], reverse=True)
        return candidates[:max_zones]

    @staticmethod
    def _deduplicate_zones(
        zones: list[dict[str, Any]], maximum: int
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for zone in zones:
            overlaps = any(
                np.hypot(zone["x"] - current["x"], zone["y"] - current["y"])
                < max(zone["radius"], current["radius"]) * 1.35
                for current in selected
            )
            if not overlaps:
                selected.append(zone)
            if len(selected) == maximum:
                break
        return selected

    @staticmethod
    def _facial_region(x: float, y: float, width: int, height: int) -> str:
        nx, ny = x / width, y / height
        if ny < 0.34:
            return "frente"
        if ny > 0.75:
            return "mentón"
        if nx < 0.42:
            return "mejilla izquierda"
        if nx > 0.58:
            return "mejilla derecha"
        return "zona central"

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
