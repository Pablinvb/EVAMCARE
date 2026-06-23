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
- Mapa facial basado en componentes visuales detectados en la fotografía:
  coordenadas reales de variaciones localizadas de rojez, tono y microtextura.
- Historial opcional por sesión; guarda resultados, nunca fotografías.
- Límites de resolución y frecuencia, respuestas estructuradas y CORS.
- Búsqueda consentida de centros por distancia.
- Leads con resumen firmado del escaneo, ubicación aproximada y consentimiento
  granular; la fotografía no se comparte.
- Bandeja de leads para socios protegida mediante credencial.
- Orientación posterior al escaneo mediante señales declaradas por el usuario,
  confianza fotográfica y hallazgos visuales.
- Puntuación explicable en tres componentes: visión 60%, síntomas 25% y
  antecedentes 15%, con alertas críticas que prevalecen sobre la suma.
- La visión artificial no puede generar por sí sola una derivación médica:
  requiere corroboración por síntomas, antecedentes o una alerta crítica.
- Historial opcional de orientaciones guardado únicamente con consentimiento.
- Ruta de autocuidado con tiendas demo y productos cosméticos compatibles.
- Catálogo de referencias oficiales de Dermasoft, Gloria Saltos, Dipaso,
  Mendieta Beauty y Fybeca.
- Rutinas completas adaptadas a piel seca, grasa, mixta, equilibrada, sensible
  y mixta deshidratada.
- Ruta dermatológica con disponibilidad y solicitud de horario.

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/clinical-status`
- `POST /api/v1/analyze`
- `GET /api/v1/history`
- `DELETE /api/v1/history/{analysis_id}`
- `DELETE /api/v1/history`
- `GET /api/v1/clinics`
- `POST /api/v1/leads`
- `DELETE /api/v1/leads/{lead_id}`
- `GET /api/v1/partner/leads`
- `PUT /api/v1/partner/clinics`
- `POST /api/v1/partner/clinics/{clinic_id}/availability`
- `GET /api/v1/partner/appointments`
- `PATCH /api/v1/partner/appointments/{appointment_id}`
- `POST /api/v1/guidance`
- `GET /api/v1/guidance-history`
- `GET /api/v1/stores`
- `GET /api/v1/stores/{store_id}/recommendations`
- `GET /api/v1/clinics/{clinic_id}/availability`
- `POST /api/v1/appointments`

Los centros incluidos inicialmente son perfiles demostrativos, no alianzas
comerciales verificadas. Deben reemplazarse o marcarse como verificados solo
después del proceso contractual y documental correspondiente.

Las recomendaciones de productos son cosméticas y no se muestran cuando el
cuestionario contiene señales de alerta. Las citas y catálogos incluidos son
demostrativos hasta integrar disponibilidad e inventario de socios reales.

## Actualizar referencias comerciales

Las fichas incluyen enlace oficial, precio observado y fecha de verificación.
Para intentar actualizar precio y disponibilidad desde Product JSON-LD:

```powershell
python scripts/sync_store_catalog.py
```

El sincronizador conserva el valor curado si una tienda no publica datos
estructurados. Precio y stock deben confirmarse siempre en la ficha oficial.

La arquitectura y reglas del catálogo están documentadas en
[`docs/RETAIL_CATALOG.md`](docs/RETAIL_CATALOG.md).

El proceso de incorporación está documentado en
[`docs/PARTNER_CLINICS.md`](docs/PARTNER_CLINICS.md).

El despliegue del backend y la conexión de GitHub Pages están documentados en
[`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md).

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
