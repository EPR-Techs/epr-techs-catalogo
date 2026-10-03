# EPR Techs · Catálogo de ventas

Catálogo web estático preparado para GitHub Pages. El archivo maestro es `data/catalogo_maestro.xls` (también se conserva una copia `.xlsx` para compatibilidad local).

## Actualizar el catálogo

1. Reemplaza `data/catalogo_maestro.xls` por el nuevo archivo maestro.
2. Ejecuta:

```bash
pip install -r requirements.txt
python scripts/obtener_imagenes_desde_fichas.py
python generar_catalogo.py
```

3. Publica/actualiza `index.html` en GitHub Pages.

El generador conserva la estructura del sitio, filtros, marcas, segmentos, fichas, costos y PVP sugeridos.

## Imágenes

No existe búsqueda por Internet ni por motores de imágenes. La rutina de imágenes únicamente visita la URL de ficha de producto registrada en `data/product_urls.json` y trata de obtener la imagen de esa ficha (`og:image`, Twitter image, JSON-LD o una imagen de la propia página). La URL de imagen queda guardada en `data/image_cache.json` y el catálogo la utiliza directamente.

**Importante:** el XLS maestro recibido no contiene hipervínculos visibles. Por ello se conserva un registro separado de URLs por `Clave` a partir del catálogo anterior. Para productos nuevos, agrega una URL en `data/product_urls.json` o incorpora una columna `URL` al maestro y adapta el generador.

## Precios

El costo del XLS se interpreta sin IVA. Los precios en dólares se convierten a MXN con `USD_MXN` en `generar_catalogo.py`; actualmente está configurado en `18.3688`. El PVP se calcula con una tabla de margen por nivel de costo, agrega IVA del 16% y redondea a escalones comerciales.

El PVP es **sugerido**, no una cotización automática de mercado por SKU. Debe revisarse frente a competencia, promociones, disponibilidad y condiciones comerciales antes de publicarlo como precio definitivo.

## GitHub Actions

`.github/workflows/update-catalog.yml` permite regenerar el catálogo al hacer push de un nuevo maestro. También puede ejecutarse manualmente desde GitHub Actions.
