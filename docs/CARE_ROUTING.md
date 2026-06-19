# Enrutamiento posterior al escaneo

## Propósito

Orientar el siguiente paso sin presentar el escáner como diagnóstico médico.
La decisión combina un resumen firmado del análisis con respuestas explícitas
del usuario.

## Rutas

### Atención médica pronta

Se activa si el usuario reporta empeoramiento rápido, fiebre o malestar,
secreción/calor/hinchazón, ampollas o afectación de ojos o boca. No se muestran
productos. La interfaz recomienda valoración pronta y mantiene disponible la
búsqueda de centros.

### Consulta dermatológica

Se activa ante lesión cambiante o con sangrado, lesión que no cicatriza,
lesiones profundas o dolorosas, cicatrices o preocupación persistente. Las
señales visuales intensas pueden reforzar esta orientación, pero no se presentan
como diagnóstico.

### Repetición de captura

Se activa cuando la confianza fotográfica es insuficiente para orientar.

### Autocuidado cosmético

Solo se activa sin señales de alerta y con confianza suficiente. Muestra tiendas
cercanas y productos demo ordenados por compatibilidad con prioridades de
hidratación, textura, poros, tono, líneas y balance de brillo.

## Restricciones

- Ningún cosmético se presenta como tratamiento de una enfermedad.
- La fotografía no se comparte con centros ni tiendas.
- Ubicación y resumen del escaneo requieren consentimiento para crear una cita.
- Los productos, tiendas, centros y horarios del MVP son datos demostrativos.
- La reserva queda en estado `requested` hasta confirmación del centro.
