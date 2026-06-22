# Enrutamiento posterior al escaneo

## Propósito

Orientar el siguiente paso sin presentar el escáner como diagnóstico médico.
La decisión combina un resumen firmado del análisis con síntomas, duración y
antecedentes declarados por el usuario.

## Puntuación explicable

`Risk Score = visión (60%) + síntomas (25%) + antecedentes (15%)`

- La visión considera imperfecciones, enrojecimiento, pigmentación y número de
  zonas localizadas. Su puntuación se limita porque el modelo aún no está
  validado clínicamente y no puede crear prioridad alta por sí solo.
- Los síntomas consideran picazón, duración, dolor, inflamación, secreción y
  cambios recientes.
- Los antecedentes consideran cáncer de piel previo, antecedentes familiares e
  inmunosupresión.

Las cicatrices, marcas postinflamatorias y estrías estables no suman riesgo.
Solo se considera si cambian, crecen, causan molestias o aparecieron
recientemente sin una causa clara.

La visión artificial nunca activa por sí sola una ruta médica. Si el usuario no
reporta síntomas ni antecedentes relevantes, el resultado será autocuidado
cosmético; si la fotografía tiene baja confianza, se solicitará repetirla.
Incluso síntomas leves aislados permanecen en autocuidado y seguimiento.

## Rutas

### Atención médica pronta

Se activa por lesión cambiante con sangrado, falta de cicatrización, ampollas
con afectación de ojos/boca, empeoramiento rápido o fiebre acompañada de
inflamación, secreción o ampollas. Estas reglas prevalecen sobre la puntuación.

### Consulta dermatológica

Se activa en puntuación media, picazón intensa/persistente, dolor relevante,
inflamación, secreción, más de seis semanas sin mejoría o antecedentes que
reducen el umbral de consulta.

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
- El historial del cuestionario solo se almacena cuando el usuario activa el
  consentimiento correspondiente.
