# Integración de catálogos de skincare

## Tiendas conectadas

- Dermasoft Ecuador
- Gloria Saltos
- Dipaso
- Mendieta Beauty
- Fybeca

Estas referencias no implican una alianza comercial. Cada ficha abre la URL
oficial del comercio. Precio, stock, despacho y condiciones pertenecen al
retailer y deben confirmarse antes de comprar.

## Selección de rutina

El recomendador filtra primero por tipo de piel:

- Seca
- Grasa
- Mixta
- Equilibrada
- Sensible
- Mixta deshidratada

Después relaciona necesidades visibles de hidratación, textura, poros,
uniformidad de tono, líneas y balance de brillo. Finalmente construye una
rutina mínima:

1. Limpieza.
2. Tratamiento opcional cuando aporta a una necesidad detectada.
3. Hidratación.
4. Protección solar.

No se recomiendan múltiples productos del mismo paso para inflar la rutina.

## Fuentes técnicas

- Dermasoft y Mendieta: WooCommerce Store API.
- Dipaso: catálogo público VTEX.
- Gloria Saltos y Fybeca: fichas oficiales con Product JSON-LD cuando está
  disponible.

El archivo `backend/catalog_data.py` conserva referencias verificadas para que
el MVP siga funcionando cuando una tienda no responda. El comando:

```powershell
python scripts/sync_store_catalog.py
```

intenta refrescar precio, disponibilidad y fecha de verificación. Se aplican
pausas conservadoras por dominio y no se copian descripciones completas ni
imágenes de las tiendas.

## Seguridad de recomendación

- Los productos solo aparecen en la ruta de autocuidado cosmético.
- No se muestran si el cuestionario activa consulta médica.
- No se presenta ningún cosmético como tratamiento de enfermedad.
- Se indica suspender el producto ante irritación.
- La protección solar permanece como paso básico, no como sustituto de consulta.
