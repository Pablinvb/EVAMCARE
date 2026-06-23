# Despliegue conectado

## 1. API en Render

El repositorio incluye `render.yaml`. En Render selecciona **New > Blueprint**,
conecta `Pablinvb/DERMASCAN-AI` y aplica el Blueprint. Render genera los secretos
del token de derivación y del portal de socios.

Comprueba:

```text
https://<servicio>.onrender.com/api/v1/health
https://<servicio>.onrender.com/docs
```

El plan gratuito puede suspenderse por inactividad y su disco es efímero. Sirve
para una demostración conectada, pero no para conservar datos clínicos, leads o
citas en producción. Antes de operar con pacientes se debe usar almacenamiento
persistente cifrado y controles de acceso por organización.

## 2. Conectar GitHub Pages

En GitHub abre **Settings > Secrets and variables > Actions > Variables** y crea:

```text
BACKEND_API_URL=https://<servicio>.onrender.com
```

Ejecuta nuevamente el workflow **Deploy static demo to GitHub Pages**. El
workflow genera `config.js`, y el frontend deja de usar el modo local.

## 3. Incorporar un centro real

La credencial `DERMASCAN_PARTNER_API_KEY` protege la administración del MVP.
Con ella se puede:

- `PUT /api/v1/partner/clinics`: crear o actualizar el perfil verificado.
- `POST /api/v1/partner/clinics/{id}/availability`: publicar horarios UTC.
- `GET /api/v1/partner/leads?clinic_id={id}`: consultar solicitudes.
- `GET /api/v1/partner/appointments?clinic_id={id}`: consultar citas.
- `PATCH /api/v1/partner/appointments/{id}?clinic_id={id}`: confirmar,
  completar, cancelar o marcar ausencia.

En una fase comercial, cada centro debe tener su propia cuenta y credenciales;
la clave global existe únicamente para el MVP.

## 4. Catálogos

El comando:

```bash
python scripts/sync_store_catalog.py
```

actualiza precio y disponibilidad cuando las tiendas publican datos
estructurados. Los enlaces siempre apuntan a la ficha oficial y no implican una
alianza. No se debe mostrar un precio como vigente cuando `verifiedAt` sea
antiguo; la confirmación final ocurre en el comercio.

## Estado médico

El motor ofrece orientación y triaje conservador. No es un diagnóstico ni una
validación médica. El estado público permanece `research_only` hasta completar
el protocolo clínico, la revisión ética y los requisitos regulatorios.
