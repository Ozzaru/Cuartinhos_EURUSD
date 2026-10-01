# Registro de lecturas de precios

Lo escribe solo `fuentes/cargador.py` (pre-registro, seccion 2.4). Una linea por
lectura, escrita ANTES de entregar o convertir los datos. Clases:

- **lectura de calidad**: el control de calidad (o la conversion a parquet) lee
  un rango que toca validacion antes de abrirla. Nunca calcula retornos
  posteriores a eventos.
- **apertura**: la apertura unica de validacion (Etapa 3) o del sellado (Etapa 5).

| fecha UTC | clase | tramo | fuente | proposito | rango (UTC) | commit | usuario de git |
|---|---|---|---|---|---|---|---|
| 2026-10-01 23:08:44 | incidente: descarga accidental que incluye el sellado; no leída; borrada | desarrollo, validacion, sellado | dukascopy | - | 2003-05-04 a 2026-10-01 | 86dc1ae63277469921b45c8836b80c7922546692 | Joel Vásquez |
