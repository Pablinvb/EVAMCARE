# Cuentas y acceso profesional — prototipo SQLite

Se conserva el escáner y el diseño existentes. `backend/accounts.py` incorpora autenticación local (scrypt), sesiones opacas de 8 horas e invitaciones de un solo uso de 48 horas. Solo se persisten hashes de tokens. Las cuentas inactivas pierden acceso inmediatamente. Admin administra cuentas pero necesita un rol evaluador y una asignación explícita para consultar resultados de pacientes.

## Configuración

Configurar únicamente en el backend `DERMASCAN_BOOTSTRAP_ADMIN_EMAIL` y `DERMASCAN_BOOTSTRAP_ADMIN_PASSWORD` (mínimo 12 caracteres). Se crea el primer administrador solo si no hay cuentas. Retirar ambas variables después de crearlo. No colocar contraseñas en config.js o GitHub Pages.

Las tablas de `migrations/0003_accounts.sql` se crean automáticamente en el arranque, después de la migración de pacientes. Los datos existentes se conservan. Usar disco persistente: SQLite en el filesystem efímero de Render pierde cambios al redesplegar. No usar datos reales en una demostración sin persistencia configurada.

## Demostración

1. Configurar el administrador y reiniciar FastAPI. Abrir «Mi cuenta» e iniciar sesión.
2. Crear cuentas ficticias de evaluador, profesional y paciente con correos únicos. Entregar el token de invitación por un canal privado. Activar cada cuenta con una contraseña propia en «Activar cuenta».
3. En Gestión de usuarios, usar «Autorizar evaluador para paciente» con los IDs internos devueltos al crear las invitaciones. También está disponible POST `/api/v1/accounts/assignments`.
4. Iniciar sesión como evaluador, buscar al paciente, pulsar Nueva evaluación y usar el escáner existente con consentimiento y guardado de historial.
5. Iniciar sesión como paciente, consultar el expediente y autorizar al profesional, seleccionando alcance y duración.
6. Iniciar sesión como profesional, abrir el expediente y añadir una nota privada.
7. Reevaluar con el evaluador y verificar historial. Revocar desde paciente; la API niega acceso profesional inmediatamente.

## Verificación y límites

La prueba test_accounts verifica activación de un solo uso, autenticación, separación de roles, asignación, alcance del permiso y revocación incluyendo notas. Los tests existentes cubren el pipeline y persistencia del escáner. La nueva interfaz debe comprobarse en navegador antes de afirmar validación visual completa.

No hay Supabase configurado: SQLite no tiene RLS. La autorización se implementa en FastAPI; RLS, Supabase Auth y storage privado requieren provisionar un proyecto y migrar el proveedor/base de datos. No se guardan fotografías y no se ofrece acceso a ellas. La demo anónima antigua sigue aislada con demo=1; las cuentas nuevas crean expedientes demo=0 sin historial sintético. Para demostraciones de cuentas usar una base de datos separada de producción y datos claramente ficticios.

La interfaz permite asignar evaluadores y editar múltiples roles. Login tiene límite por IP y correo en memoria (un proceso). Pendiente: filtros de seguimiento profesional, entrega automática de invitaciones, recuperación de contraseña, limitador distribuido, integración Supabase/RLS y almacenamiento privado. El expediente profesional inicialmente muestra datos estructurados; el dashboard de paciente existente se actualiza al iniciar sesión. No se afirma que esta entrega sea una plataforma terminada para pacientes reales.

## Publicación

GitHub Pages publica assets/accounts.js junto con index.html. Docker copia assets automáticamente. Render debe desplegar el mismo commit, configurar las variables del administrador y conservar DERMASCAN_CORS_ORIGINS=https://pablinvb.github.io. No publicar claves administrativas ni tokens de invitación.
