# EVAMCARE: seguridad, persistencia y preparación de Supabase

## Estado de esta entrega

Implementado y probado localmente: bootstrap idempotente con bloqueo transaccional, hashes scrypt versionados (N=32768,r=8,p=1 y sal aleatoria por contraseña), compatibilidad con hashes anteriores, recuperación de un solo uso y revocación de sesiones, errores sin valores enviados, copia consistente de SQLite y autorización de los cuatro roles.

Preparado, no activado: disco persistente en Render, esquema PostgreSQL y RLS, bucket privado y exportación offline. La aplicación continúa usando SQLite y autenticación local. Configurar SUPABASE_URL no cambia el proveedor. Falta implementar el adaptador PostgreSQL/Supabase Auth en FastAPI y el flujo Auth del frontend antes de cambiar producción. No se ejecutaron políticas RLS en un proyecto Supabase porque no se proporcionó uno.

La versión pública anterior sigue en 0.9.0. **No redesplegar ni cambiar el plan/ruta de DB antes de obtener y verificar un respaldo de la instancia viva.** Render Free tiene filesystem efímero; el redeploy puede perder datos y crear una base vacía. El repositorio declara /app/data/dermascan.db sin disk. No se modificaron datos de producción ni se contrató un plan.

## Administrador

1. Después de asegurar persistencia, configurar en Render, exclusivamente en Environment, DERMASCAN_BOOTSTRAP_ADMIN_EMAIL y DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD (12–256 caracteres). No escribirlos en archivos versionados, comandos, mensajes o registros.
2. Reiniciar/desplegar. El bootstrap se ejecuta solo cuando user_profiles está vacío. Si ya hay cuentas, no modifica contraseñas ni eleva privilegios. Una transacción BEGIN IMMEDIATE serializa la comprobación y creación.
3. Iniciar sesión con esa cuenta. Retirar ambas variables y reiniciar; comprobar el mismo acceso. La credencial reside como hash y sal en la DB, no depende de las variables una vez creada.
4. Si ya hay cuentas pero ningún administrador, no vaciar tablas ni activar bootstrap artificialmente: revisar y asignar el rol mediante una operación administrativa controlada sobre un respaldo. Si la DB desaparece por un redeploy efímero, retirar variables no puede conservar la cuenta.

## SQLite persistente en Render, conservando datos

1. Detener temporalmente evaluaciones y creación de cuentas, desactivar auto-deploy en Render y conservar el servicio actual sin reiniciarlo. Obtener una copia de la **DB viva**, no la DB del ordenador local. Si Render Free no ofrece shell/SSH, resolver primero un mecanismo de exportación con soporte/acceso administrativo: no cambiar plan ni reiniciar suponiendo que la DB sobrevivirá.
2. Con acceso al contenedor vivo, ejecutar el módulo de backup (cuando esté disponible en ese contenedor):

   `python -m backend.sqlite_backup --source /app/data/dermascan.db --destination /tmp/evamcare-backup.db`

   La copia usa SQLite backup API e integrity_check. Si el destino existe, falla sin sobrescribir. Transferir por un canal privado a almacenamiento fuera del contenedor y verificar tamaño/hash e integrity_check. No subir el respaldo a GitHub ni a un enlace público. El nuevo módulo todavía no existe en la imagen pública: para la imagen antigua se requiere la misma operación sqlite3.backup mediante shell o soporte, antes de desplegar.
3. Solo después del respaldo, autorizar el cambio a un plan compatible con disco (tiene coste). Usar como referencia deploy/render-persistent.yaml; no sincronizarlo automáticamente con el Blueprint actual. Montar /var/data/evamcare. Evitar montar sobre /app/data porque ocultaría archivos existentes.
4. Con el disco vacío, restaurar **desde el respaldo verificado externo**, creando /var/data/evamcare/dermascan.db exclusivamente si no existe. Se puede usar el módulo de backup con source igual al archivo transferido y destination igual a la ruta persistente: también impide sobrescribir una DB ya existente. No usar cp -f ni borrar bases anteriores.
5. Configurar DERMASCAN_DATABASE_PATH=/var/data/evamcare/dermascan.db y DERMASCAN_REQUIRE_EXISTING_DATABASE=1 después de restaurar. Esta última variable impide crear silenciosamente una base vacía si la ruta es incorrecta. Mantener secretos existentes y DERMASCAN_CORS_ORIGINS=https://pablinvb.github.io. Desplegar manualmente un solo servicio/worker mientras se usa SQLite.
6. Comparar conteos de patients, skin_scans, user_profiles, grants y notes con el respaldo. Verificar login, historial y permisos. Reiniciar y confirmar persistencia. Conservar el respaldo externo hasta completar todas las verificaciones. Las migraciones SQLite crean tablas sin reemplazar tablas existentes.

## Recuperación por correo

Configurar en Environment: DERMASCAN_SMTP_HOST, DERMASCAN_SMTP_PORT=587, DERMASCAN_SMTP_FROM, DERMASCAN_SMTP_USER, DERMASCAN_SMTP_PASSWORD y DERMASCAN_RECOVERY_URL=https://pablinvb.github.io/EVAMCARE/. El servidor usa STARTTLS obligatorio con validación de certificados; no habilitar debug SMTP.

POST /api/v1/accounts/password-recovery devuelve el mismo mensaje para correos conocidos/desconocidos. El token solo viaja por correo y permanece como hash en SQLite. El enlace usa fragmento, no query string, y el frontend lo retira de la URL. POST /api/v1/accounts/password-reset valida cuenta activa, vencimiento y un solo uso en una transacción; cambia hash/sal y revoca todos los tokens de la cuenta. Sin SMTP, la API devuelve 503, sin simular un envío. El límite de intentos sigue en memoria por proceso; para múltiples instancias se necesita Redis o equivalente. Probar envío real con una cuenta controlada antes de habilitar recuperación públicamente.

## Preparación de Supabase

1. Crear un proyecto de staging. Guardar credenciales administrativas únicamente en secretos del backend o herramientas locales protegidas. SQL Editor ejecuta supabase/migrations/202610040001_skin_records.sql una vez en un proyecto nuevo; la migración es transaccional y falla ante colisiones en vez de reemplazar datos. El esquema evamcare evita colisiones con tablas public.
2. Ejecutar supabase/tests/authorization.sql como postgres. La prueba usa cuentas ficticias y ROLLBACK: admin sin acceso clínico, paciente propietario, evaluador asignado, profesional por alcance, rechazo de autoasignación de roles, notas privadas, expiración y revocación. No afirmar RLS validado hasta que esta ejecución pase en staging.
3. Desde un respaldo offline, ejecutar `python -m backend.export_supabase --source /ruta/backup.db --destination /ruta/privada/import.sql`. El destino debe ser nuevo. El export contiene datos sensibles: custodiarlo fuera del repo. No incluye passwords, salts, sessions, account_tokens ni pacientes demo. Importar únicamente en un esquema destino vacío, en una transacción. Comparar conteos y referencias. Se conservan IDs internos. Los módulos comerciales/leads/agenda continúan en SQLite y no están incluidos en esta primera migración: conservar la copia completa y diseñar su migración antes del cambio definitivo.
4. Invitar usuarios mediante Supabase Auth (backend administrativo), sin importar ni entregar contraseñas antiguas. Mapear explícitamente user_profiles.auth_user_id al UUID de auth.users de cada invitación verificada. No enlazar cuentas arbitrariamente solo por un correo escrito por el cliente. Mantener cuentas sin mapa inaccesibles hasta completar activación.
5. En API Settings, exponer el esquema evamcare para la integración futura. Frontend usa únicamente URL y publishable/anon key; service_role/secret key y contraseña PostgreSQL jamás se publican. FastAPI deberá verificar JWT de Auth y usar identidad de usuario para lecturas con RLS. service_role bypassa RLS: sus operaciones administrativas necesitan autorización explícita del backend. No conectarlo al proveedor local actual sin implementar y probar ese adaptador.
6. RLS está activado en todas las tablas sensibles. No hay escrituras de roles/perfiles desde clientes; admin no hereda acceso clínico. Las recomendaciones, fotos y resultados requieren su propio alcance. Evolución se sirve mediante RPC de métricas, sin exponer payload completo. Los permisos usan hora de PostgreSQL y revocación en cada consulta.
7. Bucket evamcare-photos se crea privado, máximo 10 MB, JPEG/PNG/WebP. Antes de upload, backend autorizado crea scan_images con una ruta aleatoria y obtiene consentimiento photo_storage. RLS comprueba la ruta exacta, paciente y alcance photographs. No hay políticas de actualización/borrado cliente. La app actual sigue sin almacenar fotografías: implementar el uploader y entrega autenticada antes de habilitar este flujo. Evitar URLs firmadas persistentes: siguen vigentes hasta su TTL aunque se revoque el permiso. Para revocación inmediata usar descarga autenticada/proxy que revalide permisos en cada acceso.

## Despliegue y verificación

Docker ya copia backend/assets/migrations; el workflow Pages copia assets y publica config.js solo con URL de API. Supabase y SMTP secretos son backend-only. Los cambios de seguridad se conservan fuera de main hasta resolver el respaldo, para no disparar el auto-deploy actual. La configuración alternativa del disco no se aplica sola.

Después de persistencia y SMTP: desplegar backend y frontend del mismo commit, verificar /api/v1/health, activar administrador, retirar variables, probar reset real, y repetir la demostración de cuatro roles. La validación local no sustituye esa verificación de producción.

Fuentes consultadas: https://render.com/docs/free, https://render.com/docs/disks, https://supabase.com/docs/guides/storage/buckets/fundamentals, https://supabase.com/docs/guides/storage/security/access-control.
