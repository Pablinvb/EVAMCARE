# Plan de validación clínica - DermaScan AI

Estado: BORRADOR PARA REVISIÓN POR DERMATOLOGÍA, BIOESTADÍSTICA, ÉTICA Y REGULACIÓN  
Mercado inicial propuesto: Ecuador  
Versión del producto evaluada: por congelar antes del estudio

## 1. Decisión de producto pendiente

Antes de validar debe aprobarse una única finalidad médica. No es válido estudiar
simultáneamente "tipo de piel, acné, poros, hidratación, envejecimiento, etc." sin
definir cada variable, población, usuario y decisión clínica.

Finalidad inicial recomendada:

> Software de apoyo para profesionales de dermatología que analiza fotografías
> faciales estandarizadas de personas adultas y cuantifica la severidad visible
> del acné facial como apoyo al seguimiento. No realiza diagnóstico autónomo,
> no descarta enfermedad y no recomienda medicamentos.

Esta finalidad es deliberadamente estrecha. Hidratación, poros, edad cutánea y
líneas de expresión deben permanecer como características cosméticas hasta que
cada una tenga referencia clínica y evidencia propia.

## 2. Población y entorno propuestos

- Personas de 18 años o más.
- Atención primaria y consulta dermatológica en Ecuador.
- Representación planificada de fototipos Fitzpatrick I-VI, con énfasis III-V.
- Exclusión inicial: maquillaje que oculte lesiones, filtros digitales,
  procedimientos faciales recientes, imágenes no estandarizadas o incapacidad
  para consentir.
- Usuario previsto inicial: profesional de salud entrenado.

## 3. Referencia clínica

- Tres dermatólogos certificados evalúan cada caso de forma independiente.
- Consenso adjudicado cuando existe desacuerdo.
- Escala clínica previamente seleccionada y documentada; para acné debe
  elegirse una escala validada y reproducible antes del protocolo final.
- Los evaluadores permanecen ciegos al resultado del algoritmo.
- El conjunto de prueba clínica no puede solaparse con entrenamiento,
  calibración ni selección de umbrales.

## 4. Estudios necesarios

### 4.1 Validez científica

Revisión sistemática que conecte las características de imagen utilizadas con
el estado clínico objetivo. Debe justificar qué señal mide el software y por
qué se relaciona con la finalidad médica.

### 4.2 Desempeño analítico

- Detección y segmentación facial frente a anotaciones expertas.
- Repetibilidad intra-dispositivo e inter-dispositivo.
- Robustez a iluminación, distancia, ángulo, cámara y compresión.
- Control de calidad que rechace capturas fuera de especificación.
- Pruebas de ciberseguridad, integridad de archivos y límites operativos.

### 4.3 Desempeño clínico retrospectivo

- Dataset externo, multicéntrico y bloqueado.
- Comparación con el consenso dermatológico.
- Resultados globales y estratificados por fototipo, sexo, edad, centro,
  dispositivo y severidad.
- Intervalos de confianza del 95%.

### 4.4 Estudio prospectivo

- Protocolo aprobado por un Comité de Ética de Investigación en Seres Humanos.
- Consentimiento informado y tratamiento lícito de fotografías biométricas.
- Registro previo del protocolo y del plan estadístico.
- Evaluación del uso real por el profesional previsto.
- Registro de fallos, exclusiones y eventos adversos.

## 5. Objetivos de desempeño preliminares

Estos valores son criterios de diseño y deben ser confirmados por el equipo
clínico y bioestadístico antes de calcular la muestra:

- Sensibilidad para detectar acné clínicamente relevante: >= 0.90.
- Especificidad: >= 0.80.
- AUC: >= 0.90.
- Kappa ponderado de severidad frente a consenso: >= 0.75.
- Diferencia absoluta de sensibilidad entre fototipos: <= 0.10.
- Tasa de capturas no evaluables correctamente rechazadas: >= 0.95.
- Límite inferior del IC 95% por encima del mínimo clínicamente aceptable.

No se autorizará el uso clínico si un subgrupo relevante incumple el criterio,
aunque el promedio global lo cumpla.

## 6. Estimación de muestra

La muestra debe calcularla un bioestadístico a partir del endpoint primario,
prevalencia esperada, precisión del intervalo de confianza y análisis de
subgrupos. Como orientación operativa, el estudio debe incluir suficientes
casos positivos y negativos por cada fototipo relevante; no basta un total
global grande con subgrupos pequeños.

## 7. Gestión de datos

- Consentimiento específico para captura, entrenamiento, validación y
  conservación; cada finalidad debe poder aceptarse por separado.
- Identificadores seudónimos; la tabla de reidentificación se guarda aparte.
- Cifrado en tránsito y reposo, control de acceso por rol y auditoría.
- Política documentada de retención, revocación y eliminación.
- Separación por paciente entre entrenamiento, validación y prueba.
- Versionado del dataset, etiquetas, protocolo y modelo.
- Prohibición de usar fotografías clínicas en servicios de terceros sin
  autorización explícita y contrato aplicable.

## 8. Sistema de calidad y expediente técnico

- Sistema de gestión de calidad alineado con ISO 13485.
- Ciclo de vida de software alineado con IEC 62304.
- Gestión de riesgos según ISO 14971.
- Usabilidad según IEC 62366-1.
- Seguridad y privacidad con controles verificables.
- Especificación de requisitos, arquitectura, trazabilidad y verificación.
- Gestión de cambios del modelo y plan de modificaciones predeterminadas.
- Vigilancia poscomercialización y procedimiento de incidentes.

La aplicabilidad exacta de cada norma y la clasificación de riesgo deben
confirmarse con ARCSA y un especialista regulatorio.

## 9. Puertas de liberación

1. Finalidad médica y clasificación regulatoria aprobadas.
2. Comité de ética y consentimiento aprobados.
3. Dataset bloqueado y protocolo estadístico firmado.
4. Verificación técnica aprobada.
5. Estudio clínico completado sin desviaciones críticas.
6. Informe clínico firmado por responsables clínico y bioestadístico.
7. Revisión de sesgo por subgrupos aprobada.
8. Registro o autorización sanitaria aplicable obtenida.
9. Etiquetado, instrucciones y vigilancia listos.

Solo después de completar las nueve puertas puede cambiarse el estado público
de `research_only` a `clinically_validated`.
