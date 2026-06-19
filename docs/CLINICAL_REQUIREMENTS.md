# Requisitos para la versión clínica

## Bloqueadores actuales

- CR-001: definir una finalidad médica única, población y usuario previsto.
- CR-002: sustituir las heurísticas por un modelo entrenado y versionado.
- CR-003: usar landmarks y segmentación de piel validados.
- CR-004: implementar protocolo de captura y rechazo automático.
- CR-005: disponer de referencia dermatológica adjudicada.
- CR-006: separar entrenamiento, calibración y prueba por paciente y centro.
- CR-007: medir desempeño e incertidumbre por subgrupo.
- CR-008: registrar versión de modelo, cámara y calidad en cada inferencia.
- CR-009: implementar autenticación clínica, auditoría y consentimiento.
- CR-010: impedir recomendaciones farmacológicas automatizadas.
- CR-011: completar gestión de riesgos, usabilidad y ciberseguridad.
- CR-012: obtener aprobación ética y autorización sanitaria aplicable.

## Criterio de estado

El backend debe devolver `research_only` mientras cualquiera de CR-001 a
CR-012 permanezca abierto. El valor no puede cambiarse mediante una variable de
entorno ni una edición de interfaz: requiere un artefacto de aprobación firmado
y verificable dentro del proceso de liberación.
