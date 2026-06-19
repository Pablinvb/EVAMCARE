# DermaScan AI

MVP cliente-servidor de evaluación cosmética facial orientativa. Permite usar
la cámara o cargar una fotografía; el backend valida la imagen, detecta el
rostro y estima ocho indicadores visibles.

## Ejecutar

Instala las dependencias y ejecuta el backend:

```powershell
python -m pip install -r requirements.txt
.\run_backend.ps1
```

Después abre `http://127.0.0.1:8000`.

La documentación interactiva de la API está disponible en
`http://127.0.0.1:8000/docs`.

## Ejecutar con Docker Compose

Prepara la configuración local y levanta el servicio:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Los resultados opcionales del historial quedan en el volumen persistente
`dermascan_data`. El archivo `.env` no se publica en Git.

Las variables disponibles y sus valores seguros de ejemplo están documentados
en `.env.example`.

## Alcance del MVP

- Backend FastAPI con OpenCV y SQLite.
- Captura WebRTC y carga JPG/PNG/WebP de hasta 10 MB.
- Detección del rostro y validación de iluminación, nitidez, contraste y encuadre.
- Estimaciones de hidratación, textura, poros, imperfecciones, pigmentación,
  líneas visibles, enrojecimiento y balance sebáceo.
- Clasificación cosmética orientativa del tipo de piel.
- Mapa facial, prioridades y rutina inicial.
- Historial opcional por sesión; guarda resultados, nunca fotografías.
- Límites de resolución y frecuencia, respuestas estructuradas y CORS.

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/clinical-status`
- `POST /api/v1/analyze`
- `GET /api/v1/history`
- `DELETE /api/v1/history/{analysis_id}`
- `DELETE /api/v1/history`

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Limitaciones

Este prototipo usa detección facial Haar y análisis clásico de píxeles por
regiones. No incluye todavía un modelo clínicamente validado, landmarks densos
ni un dataset dermatológico latinoamericano. Sus resultados no son diagnósticos
médicos ni deben utilizarse para decidir tratamientos.

El camino controlado hacia una versión médica está documentado en
[`docs/CLINICAL_VALIDATION_PLAN.md`](docs/CLINICAL_VALIDATION_PLAN.md). El
backend expone el estado `research_only` y no permite representar esta versión
como clínicamente validada mientras existan requisitos clínicos abiertos.

## Próxima fase recomendada

1. Integrar MediaPipe Face Landmarker y segmentación real de piel.
2. Crear un protocolo de captura estandarizado y calibración de color.
3. Entrenar y validar cada modelo con datos consentidos y representativos de
   fototipos latinoamericanos.
4. Medir sensibilidad, especificidad, sesgo por fototipo y repetibilidad.
5. Añadir autenticación, cifrado y políticas verificables de retención.
