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
| 2026-10-01 23:13:52 | complemento al incidente del 01-10-2026: los dos archivos se abrieron por error unos segundos en Excel, que solo carga el comienzo (mayo de 2003 a comienzos de 2006, desarrollo); ningún programa del proyecto los leyó | desarrollo, validacion, sellado | dukascopy | - | 2003-05-04 a 2026-10-01 | db9c4378640199a5d0b60a296c6fe81d4d1b6a4b | Joel Vásquez |
| 2026-10-01 23:17:23 | lectura de calidad | desarrollo, validacion | dukascopy | conversion a parquet | 2003-05-04 a 2020-12-31 | 8b253624ecedb10a2eba224750cec4fa662cf489 | Joel Vásquez |
| 2026-10-01 23:28:07 | lectura de calidad | desarrollo, validacion | histdata | conversion a parquet | 2003-05-04 a 2020-12-31 | 1cc5728ed5bb53ab090045f1c6e5812c9733eb9f | Joel Vásquez |
| 2026-10-01 23:32:38 | lectura de calidad | desarrollo, validacion | dukascopy | calidad | 2016-12-29 a 2017-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:32:38 | lectura de calidad | desarrollo, validacion | histdata | calidad | 2016-12-29 a 2017-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:32:50 | lectura de calidad | validacion | dukascopy | calidad | 2017-12-29 a 2018-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:32:51 | lectura de calidad | validacion | histdata | calidad | 2017-12-29 a 2018-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:33:03 | lectura de calidad | validacion | dukascopy | calidad | 2018-12-29 a 2019-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:33:03 | lectura de calidad | validacion | histdata | calidad | 2018-12-29 a 2019-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:33:15 | lectura de calidad | validacion | dukascopy | calidad | 2019-12-29 a 2020-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-01 23:33:15 | lectura de calidad | validacion | histdata | calidad | 2019-12-29 a 2020-12-31 | 5d4e0b6bf483b0ea1fb501854dc9da2c0c532c6e | Joel Vásquez |
| 2026-10-02 00:25:45 | lectura de calidad | desarrollo, validacion | histdata | conversion a parquet | 2003-05-04 a 2020-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:37:06 | lectura de calidad | desarrollo, validacion | dukascopy | calidad | 2016-12-29 a 2017-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:37:06 | lectura de calidad | desarrollo, validacion | histdata | calidad | 2016-12-29 a 2017-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:37:58 | lectura de calidad | validacion | dukascopy | calidad | 2017-12-29 a 2018-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:37:58 | lectura de calidad | validacion | histdata | calidad | 2017-12-29 a 2018-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:38:49 | lectura de calidad | validacion | dukascopy | calidad | 2018-12-29 a 2019-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:38:49 | lectura de calidad | validacion | histdata | calidad | 2018-12-29 a 2019-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:39:39 | lectura de calidad | validacion | dukascopy | calidad | 2019-12-29 a 2020-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 00:39:40 | lectura de calidad | validacion | histdata | calidad | 2019-12-29 a 2020-12-31 | 6d680c54bda2af0357548b3442aafcf23b86f520 | Joel Vásquez |
| 2026-10-02 01:09:08 | lectura de calidad | desarrollo, validacion | dukascopy | calidad | 2016-12-29 a 2017-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:09:08 | lectura de calidad | desarrollo, validacion | histdata | calidad | 2016-12-29 a 2017-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:10:02 | lectura de calidad | validacion | dukascopy | calidad | 2017-12-29 a 2018-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:10:02 | lectura de calidad | validacion | histdata | calidad | 2017-12-29 a 2018-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:10:56 | lectura de calidad | validacion | dukascopy | calidad | 2018-12-29 a 2019-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:10:56 | lectura de calidad | validacion | histdata | calidad | 2018-12-29 a 2019-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:11:46 | lectura de calidad | validacion | dukascopy | calidad | 2019-12-29 a 2020-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
| 2026-10-02 01:11:46 | lectura de calidad | validacion | histdata | calidad | 2019-12-29 a 2020-12-31 | 672781ae89f42f128a894b8f687363ddd1d1aa76 | Joel Vásquez |
