# EvanCare / DermaScan 2.0 Patient Skin Record

## Estado implementado en el MVP

La aplicación evoluciona de `scan -> resultado` a un flujo persistente:

`paciente -> expediente -> scans -> historial -> evolución -> recomendaciones -> share revocable`.

La implementación actual conserva el scanner, FastAPI, OpenCV, SQLite, tiendas,
centros dermatológicos, leads y agenda existentes.

## Persistencia

El MVP usa SQLite porque el repositorio no tiene Supabase configurado todavía.
Las tablas nuevas se inicializan de forma segura al arrancar la API y también
quedan documentadas en `migrations/0002_patient_skin_record_platform.sql`.

Tablas nuevas:

- `patients`
- `skin_scans`
- `scan_images`
- `recommendations`
- `shared_records`
- `consents`
- `audit_logs`

## Seguridad y privacidad

- La identidad de demo se basa en `X-Derma-Session`.
- Cada paciente tiene un UUID interno y un `patient_code` tipo `DS-8F42K29`.
- Las imágenes no se guardan en SQLite ni se exponen públicamente.
- Los shares usan token efímero y se almacena solo hash del token.
- El share es revocable.
- No se exponen credenciales de backend en el frontend.

## Supabase/RLS

Supabase no está configurado en el proyecto actual. Para producción, migrar estas
tablas a PostgreSQL/Supabase y habilitar:

- Supabase Auth.
- Row Level Security por `auth.uid()`.
- Buckets privados para imágenes.
- URLs firmadas y de corta duración.
- Service role solo en backend.

## Vision Pro

Implementado como arquitectura y UI `Vision Pro Ready`:

- `GET /api/v1/capture-providers`
- `capture_source = vision_pro`
- UI de Spatial Scan demo.

No se afirma conexión real con Apple Vision Pro ni telemetría espacial real.

## Posicionamiento médico

La plataforma mantiene lenguaje de análisis cosmético/asistido por IA. No emite
diagnósticos médicos ni afirma validación clínica regulatoria.
