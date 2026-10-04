# Invitaciones de EVAMCARE

Crear una cuenta genera una invitación de 48 horas y deja el usuario pendiente.
La respuesta distingue correo no configurado, envío fallido y aceptación por el
proveedor. Aceptación no garantiza llegada a bandeja de entrada.

Render gratuito bloquea SMTP 25/465/587. Se usa la API HTTPS de Resend.
Configurar directamente en Render producción, nunca en GitHub ni el chat:

- `DERMASCAN_RESEND_API_KEY`: clave restringida a envío del proveedor.
- `DERMASCAN_EMAIL_FROM`: remitente autorizado de un dominio verificado.
- `DERMASCAN_PUBLIC_APP_URL`: `https://pablinvb.github.io/EVAMCARE/`.

No crear servicios de pago. El remitente de pruebas de Resend puede restringir
los destinatarios: para pacientes distintos se requiere dominio autorizado.
No se incluyen resultados, fotos ni datos clínicos en los mensajes.

En Gestión de usuarios, buscar con Todos los estados. Las cuentas pendientes
ofrecen Regenerar / reenviar invitación. Solo administradores pueden hacerlo;
se invalida el enlace previo, se registra auditoría y se limita la frecuencia.
Si no hay correo configurado, Copiar enlace privado permite entrega manual.
No se muestra un mensaje de envío exitoso cuando falta configuración.

La recuperación de contraseña mantiene su mecanismo SMTP existente; esta
implementación no modifica ni declara operativa esa función en Render gratuito.
La entrega real debe probarse después de configurar el proveedor, sin registrar
tokens ni respuestas de error privadas.
