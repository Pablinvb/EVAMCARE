# Programa de centros aliados - MVP

## Objetivo

DermaScan permite que una persona solicite voluntariamente contacto de un
centro cercano después de su análisis. No vende ni transmite leads de forma
automática y no comparte fotografías.

## Verificación previa del centro

Antes de cambiar `demo=true` por un perfil real deben archivarse:

1. Razón social, RUC y representante autorizado.
2. Permiso de funcionamiento vigente.
3. Profesionales responsables y títulos verificables.
4. Dirección, coordenadas, horarios y canales oficiales.
5. Servicios dermatológicos efectivamente ofrecidos.
6. Contrato comercial y acuerdo de tratamiento de datos.
7. Responsable de privacidad y mecanismo para atender eliminaciones.
8. Tiempo objetivo de respuesta y proceso para cerrar una cita.

## Datos recibidos por el centro

Solo después de tres consentimientos explícitos:

- Nombre, teléfono y correo opcional.
- Canal y horario de contacto preferidos.
- Ubicación aproximada, redondeada a tres decimales.
- Distancia calculada al centro.
- Resumen firmado del escaneo: puntaje, tipo estimado, confianza y tres
  prioridades visuales.

Nunca se incluye la fotografía facial en el lead.

## API para socios

`GET /api/v1/partner/leads?clinic_id={id}`

Cabecera requerida:

`X-Partner-Key: {credencial privada}`

La credencial de desarrollo debe reemplazarse antes de desplegar. La fase
siguiente debe incorporar cuentas por centro, roles, rotación de credenciales,
auditoría y actualización de estados del lead.

## Estados propuestos

- `new`: recibido.
- `contacted`: se intentó contacto.
- `scheduled`: cita confirmada.
- `attended`: cita atendida.
- `closed`: cerrado sin cita.

El MVP crea leads en estado `new`. La gestión completa de estados corresponde a
la siguiente iteración del panel B2B.
