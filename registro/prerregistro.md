# Pre-registro — Cascada de stops o presión de liquidez: qué ocurre tras las rupturas de rangos intradía en EUR/USD

- **Versión**: 1 (borrador para revisión del grupo; se congela con la etiqueta `prerregistro-v1`).
- **Fecha de redacción**: 25 de septiembre de 2026; revisado el 2 de octubre de 2026, después de la etapa de datos (ver "Cambios e incidentes después del borrador del 01-10-2026", al final). **Congelamiento previsto**: con la etiqueta anotada `prerregistro-v1` en el repositorio público, antes de calcular cualquier resultado y antes de la Etapa 3.
- **Repositorio**: https://github.com/Ozzaru/Cuartinhos_EURUSD. La versión que vale es la del commit con la etiqueta `prerregistro-v1`.

---

## 1. Estudio

### 1.1 Título

Cascada de stops o presión de liquidez: qué ocurre tras las rupturas de rangos intradía en EUR/USD.

### 1.2 Autores

Joshua Barrientos, Joel Vásquez, José Ignacio Moreno, Francisco Piñeda y Santiago López. Magíster en Finanzas, mención Cuantitativa, Escuela de Negocios, Universidad Adolfo Ibáñez.

### 1.3 Descripción y preguntas

Entre los operadores intradía circula la idea de que el precio "barre" el extremo de un rango previo, activa las órdenes stop acumuladas detrás de ese nivel y enseguida se devuelve. El estudio traduce esa idea a reglas observables y la enfrenta a dos predicciones rivales de la microestructura: **continuación** por cascada de stops (Osler, 2003, 2005) y **reversión** por provisión de liquidez (Grossman y Miller, 1988; Campbell, Grossman y Wang, 1993; Nagel, 2012).

Preguntas:

1. Tras romper el extremo del rango de la franja horaria anterior, ¿el EUR/USD sigue en la dirección de la ruptura o se devuelve?
2. ¿De qué condiciones depende: cercanía a números redondos, a los extremos del día anterior, compresión previa del rango y anuncios macroeconómicos?
3. ¿Sobrevive el efecto a los costos de ejecución?

### 1.4 Hipótesis

En todo el documento, el **efecto** de una celda (tipo de evento × horizonte) es el retorno normalizado posterior de los eventos menos el de minutos comparables (la nula emparejada, sección 5.1), **medido en la dirección que predice la hipótesis**. Así, "efecto > 0" significa lo mismo en H1 y en H2: que se cumple lo que la hipótesis predice.

| | enunciado | dirección | papel |
|---|---|---|---|
| **H1, continuación** | Tras una ruptura **sostenida** (sin reingreso durante 15 minutos), el precio sigue en la dirección de la ruptura más que en minutos comparables. | efecto > 0 (retorno en la dirección de la ruptura, mayor que el nulo) | **confirmatoria** (familia principal) |
| **H2, reversión** | Tras un **reingreso** al rango, el precio se devuelve más que en minutos comparables. | efecto > 0 (retorno en la dirección de la ruptura, menor que el nulo) | **confirmatoria** (familia principal) |
| **H3, moderadores** | Los efectos de H1 y H2 se **intensifican** donde se espera acumulación de órdenes: extremo cerca de un número redondo, cerca del extremo del día anterior, o tras una franja comprimida. | La dirección esperada es la de la propuesta (se intensifican), pero la prueba es **a dos colas**, que es la que se calibró; un efecto significativo en sentido contrario se reporta como tal. | **confirmatoria** (familia de moderadores) |
| **H4, información** | Con anuncio macroeconómico reciente hay **más continuación** que sin él. Se operacionaliza como esa diferencia; las dos mitades del enunciado de la propuesta ("con anuncios domina la continuación y sin ellos la reversión") no se prueban por separado. | diferencia (con anuncio − sin anuncio) > 0 | **análisis secundario pre-especificado, NO confirmatorio** (razón en 5.4 y 8) |
| **H5, explotabilidad** | La regla de operación derivada mantiene un resultado neto positivo tras costos en el tramo sellado, con Deflated Sharpe superior a 0,95. | resultado neto > 0 y DSR > 0,95 | confirmatoria **condicional**: solo se evalúa si se cumple el criterio de paso por costos (5.5) |

---

## 2. Diseño

### 2.1 Tipo de estudio

Estudio **observacional** sobre datos que ya existen (precios históricos de EUR/USD de un minuto y calendarios oficiales de anuncios). Los datos de 2003 a 2020 se descargaron el 1 y el 2 de octubre de 2026 y, antes de congelar este documento, **solo se revisó su calidad** (2.2 y 3.3). No hay manipulación ni asignación aleatoria.

### 2.2 Datos existentes

**Se congela antes de calcular cualquier resultado.** Los precios de EUR/USD de un minuto de 2003 a 2020 (Dukascopy y HistData) y el calendario de anuncios se obtuvieron el 1 y el 2 de octubre de 2026. Antes de congelar solo se revisó su **calidad** (3.3): **no se calculó ningún retorno posterior a eventos ni se clasificaron sostenidas o reingresos**, en ningún tramo. El control de calidad usa de las rupturas solo si las hay, su dirección y su minuto, nunca lo que pasa después.

La evidencia está en el repositorio:

- `registro/aperturas.md`: cada lectura de precios que tocó el tramo de validación quedó anotada **antes** de hacerse, como "lectura de calidad", con fecha UTC, tramo, fuente, propósito, hash del commit y usuario de git.
- El candado del código (2.4): hasta que exista la etiqueta `prerregistro-v1`, el único módulo que recibe precios es el de calidad, que no importa los módulos de resultados, nula ni inferencia. Se programó y se commiteó antes de leer el primer precio.

Como cualquier observador del mercado, los autores pueden haber visto gráficos del par, pero ninguno ha calculado las variables definidas aquí ni ha mirado retornos después de rupturas de franja. Todo el desarrollo previo (motor de eventos, pruebas estadísticas, controles de calibración y de potencia) se hizo con **mercados simulados**, y está en el repositorio con su historia de commits y la bitácora (`registro/bitacora.md`). El tramo sellado no se usa; una descarga accidental que lo incluía, no leída por ningún programa y borrada el mismo día, se describe al final.

### 2.3 Papel de cada tramo

| tramo | período | papel |
|---|---|---|
| **desarrollo** | desde el primer día disponible en Dukascopy hasta el 31-12-2016 | Se corre primero el análisis pre-registrado completo, con el código de la etiqueta `prerregistro-v1`. Sus resultados son **exploratorios**. Si llevan a cambiar algo, se agrega una enmienda fechada (2.5) **antes** de abrir validación. |
| **validación** | 01-01-2017 a 31-12-2020 | **Confirma H1, H2 y H3** y decide el criterio de paso por costos. Se abre una sola vez. |
| **sellado** | 01-01-2021 a 31-08-2026 | No se descarga hasta la Etapa 5 (16 al 20 de noviembre de 2026). Repite **exactamente** el mismo análisis una sola vez, y es el **único tramo donde se prueba H5**. |

Precisiones:

1. **Código congelado antes de abrir.** Antes de abrir validación se crea la etiqueta `validacion-v1` y su hash se anota en la bitácora; se corre ese código y no otro. Igual para el sellado, con `sellado-v1`.
2. **Calentamiento.** Las ventanas hacia atrás (20 días de `sigma_ref` y de compresión, 60 minutos de volatilidad reciente, día anterior) leen el tramo anterior, que ya está abierto.
3. **Borde.** Un evento pertenece al tramo de su fecha de Londres. Sus resultados no leen datos posteriores al fin del tramo: si un horizonte los necesita, queda sin dato.
4. **Lectura.** Una celda que rechaza en validación queda **confirmada**; si además rechaza en el sellado, **replicada**. Un desacuerdo entre tramos se reporta tal cual; los tramos no se combinan.
5. H4 (secundario) se corre y se reporta igual en los tres tramos.

### 2.4 Apertura única y registro de lecturas

Se programó en la etapa de datos (`fuentes/`), antes de leer el primer precio (commit `2292d7f`, 01-10-2026), y queda en el repositorio con sus tests (`tests/test_candado.py`, `tests/test_fuentes.py`).

- **Cargador único** (`fuentes/cargador.py`). Es el único módulo que lee archivos de precios; un test revisa que ningún otro lea parquet ni conozca las rutas de los precios. También convierte los crudos a parquet en UTC, y antes verifica que cada crudo siga igual a su huella en `registro/manifiesto_datos.csv` (tamaño y SHA-256). Los precios viven fuera del repositorio.
- **Hasta la etiqueta `prerregistro-v1`**: solo entrega datos al módulo de calidad (`fuentes/calidad.py`, con propósito "calidad"; el cargador revisa qué módulo lo llama), en cualquier tramo salvo el sellado. Cualquier otro pedido es un error.
- **Con la etiqueta**: el desarrollo se lee sin restricción; validación y sellado exigen la bandera explícita `abrir="validacion"` o `abrir="sellado"`, un tramo por vez. Sin la bandera, el cargador levanta un error.
- **Registro.** Toda lectura que toca validación, y toda apertura, exige el árbol de git limpio y deja **antes** una línea en `registro/aperturas.md` (fecha UTC, clase, tramo, fuente, propósito, rango, hash del commit y usuario de git). Hay dos clases de línea:
  - **"lectura de calidad"**: el control de calidad, o la conversión a parquet, lee validación antes de abrirla (3.3). Nunca calcula retornos posteriores a eventos.
  - **"apertura"**: la apertura única de validación (Etapa 3) o del sellado (Etapa 5).
- `registro/aperturas.md` **solo crece**: el cargador exige que empiece exactamente con su versión del último commit (ninguna línea editada ni borrada), y se commitea al cierre de cada sesión. Es la única excepción al árbol limpio, porque es lo que el cargador escribe.
- **Sellado.** La descarga y la conversión rechazan toda fecha desde el 01-01-2021 hasta la Etapa 5. El registro de crudos rechaza, sin leerlo, todo archivo de Dukascopy cuyo nombre declare una fecha final posterior al 31-12-2020. Antes de interpretar un precio, la conversión lee solo las horas y se detiene si algún minuto es del sellado.
- **Tests que lo vigilan:**
  - sin la etiqueta, el cargador rechaza todo lo que no sea el módulo de calidad;
  - con la etiqueta, rechaza validación y sellado sin la bandera;
  - la lectura de validación exige el árbol limpio y queda anotada;
  - el registro solo admite líneas agregadas;
  - el módulo de calidad no importa resultados, nula ni inferencia (tampoco eventos, moderadores ni auditoría);
  - ninguna salida suya trae retornos posteriores ni los tipos sostenida o reingreso;
  - la descarga, el registro y la conversión rechazan el sellado.

### 2.5 Política de enmiendas

- **Una enmienda** es una sección fechada dentro de "Enmiendas", al final de este documento, con su razón (un error, o algo que mostró el análisis de desarrollo). Cada enmienda se congela con una etiqueta anotada nueva (`prerregistro-v2`, `prerregistro-v3`, ...) y tiene su entrada en la bitácora. **Solo se admiten antes de abrir validación.**
- **Después de abrir validación**: el análisis confirmatorio no cambia. Si se descubre un error de código, se corrige y se reportan las dos versiones (la pre-registrada y la corregida); la nota del error va en la bitácora.
- Una configuración de H5 fuera del conjunto cerrado (5.5) solo puede agregarse con una enmienda, y suma al número de ensayos.

### 2.6 Calendario

| fecha | hito |
|---|---|
| 01 y 02-10-2026 | descarga de datos hasta 2020 y control de calidad (solo calidad: ningún resultado) |
| 02-10-2026 | Entrega N1 |
| antes de calcular cualquier resultado y antes de la Etapa 3 | congelamiento: etiqueta `prerregistro-v1` en el repositorio público |
| 05-10 al 23-10-2026 | Etapa 3: análisis en desarrollo; enmiendas, si las hay; apertura de validación; criterio de paso |
| 26-10 al 13-11-2026 | Etapa 4: regla de operación (solo si pasa el criterio), o acotación del efecto |
| 16-11 al 20-11-2026 | Etapa 5: descarga y apertura única del tramo sellado |

---

## 3. Datos

### 3.1 Fuentes

| fuente | qué | papel |
|---|---|---|
| **Dukascopy** | Velas de 1 minuto de EUR/USD con **bid y ask**, en UTC. El precio medio es (bid + ask) / 2. | **Análisis principal**: todas las definiciones y resultados usan el **precio medio**; el efecto neto usa bid y ask. |
| **HistData** | Velas de 1 minuto de EUR/USD, **solo bid**. Su documentación dice hora EST fija (UTC−5, sin horario de verano), pero los archivos vienen en **hora de Nueva York con horario de verano**: se convierten a UTC con `America/New_York` (ver abajo). | **Control y réplica**: la réplica del análisis con HistData usa **bid**, mientras el análisis principal usa el precio medio de Dukascopy. La coincidencia entre fuentes se mide con el bid de las dos. |
| **Calendarios oficiales** | Fecha y hora de los anuncios de la lista cerrada (4.8). | Variable de anuncio (H4) y control en la regresión de H3. |

**HistData: zona horaria y réplica.** Decisión del grupo del 02-10-2026, después del control de calidad (3.3):

- **Zona horaria.** Los archivos de HistData vienen en hora de Nueva York con horario de verano, al revés de lo que dice su documentación (EST fija). El control de calidad lo mostró:
  - con EST fija, la correlación entre fuentes tenía su máximo en +60 minutos todos los años;
  - la apertura del domingo de HistData quedaba una hora tarde durante el verano de EE. UU.

  Se convierten con `America/New_York` (base de zonas fijada). Es un error de manejo de la segunda fuente (3.3) y el análisis principal no cambia.
- **Regla de exclusión de la réplica.** Lo que no queda alineado con Dukascopy se excluye de la réplica con HistData, sin corregirlo con desfases calculados:
  1. Se excluye una **semana** (domingo a viernes) si la apertura del domingo y el cierre del viernes de HistData están ambos corridos 60 ± 10 minutos respecto de la hora de Nueva York, con el mismo signo.
  2. Se excluye un **mes** (UTC) si su desfase con Dukascopy (el máximo de la correlación de 3.3) no es 0, medido sin las semanas del punto 1.

  Las demás desviaciones (datos ralos que empiezan tarde, días faltantes, feriados) se informan y no se excluyen.
- **Lo que excluye en 2003-2020.**
  - **8 semanas de 2019-2020**: las que empiezan el 10, 17 y 24 de marzo y el 27 de octubre de 2019, y el 8, 15 y 22 de marzo y el 25 de octubre de 2020. En esos años HistData cambia de horario en las fechas europeas y no en las de EE. UU.
  - **11 meses de 2003-2006**: mayo, junio, julio, octubre, noviembre y diciembre de 2003; febrero, marzo, junio y noviembre de 2004; octubre de 2006. Mayo a julio de 2003 vinieron en EST fija; los demás están corridos 1 o 2 minutos.
- **Cuándo se precisó la regla.** Se precisó después de ver las tablas de calidad de 2003-2020, para separar un reloj corrido de un dato faltante. Esas tablas son solo horas de apertura y cierre semanales y la zona horaria mes a mes; no contienen ningún resultado. **Se aplica sin cambios al tramo sellado.**
- **Dónde está.** Las tolerancias y las listas están en `config.py`. El control de calidad aplica la regla en cada corrida y verifica que encuentre exactamente esas listas.

### 3.2 Períodos

- Los tres tramos de 2.3. El tamaño de muestra lo fija el período, no una regla de parada.
- **Orden de magnitud esperado**, según el simulador (no según los datos): unas 310 sostenidas y 700 reingresos por año. En los 4 años de validación, unas 1.230 sostenidas y 2.790 reingresos.

### 3.3 Control de calidad

Se hace sobre las dos fuentes, por año. Sobre validación es una **lectura de calidad** (2.4): nunca calcula retornos posteriores a eventos.

| chequeo | criterio | si falla |
|---|---|---|
| Integridad de la barra (máximo ≥ apertura y cierre; mínimo ≤ ambos; ask ≥ bid) | Menos de 0,1% de barras inválidas. | La barra inválida se trata como faltante, sin corregirla. Más de 0,1%: se investiga antes de seguir. |
| Zona horaria | Correlación de retornos de 1 minuto entre fuentes para desfases de −120 a +120 minutos: el máximo tiene que estar en 0 en todos los años. | Error de manejo: se corrige y se repite. |
| Apertura del domingo y cierre del viernes | Primera barra de la semana entre 21:00 y 23:00 UTC; última del viernes entre 20:00 y 22:00 UTC. | Se listan las semanas fuera de rango. |
| Huecos | Huecos de más de 60 minutos fuera del fin de semana, listados; porcentaje de franjas que no llegan a la cobertura mínima (4.1), por año. | Informativo. |
| Horario de verano | Las franjas de los días de cambio de hora duran 5 o 7 horas; las semanas en que EE. UU. y el Reino Unido no coinciden quedan bien ubicadas. | Error de manejo: se corrige. |
| Spread (Dukascopy) | Distribución por hora UTC y año; más ancho en el cierre de Nueva York. Spread ≤ 0: barra inválida. Más de 10 pips: se reporta, no se borra. | Informativo. |
| Extremos por franja | Diferencia de máximos y mínimos de franja entre fuentes (bid), en pips: mediana y percentil 95 por año. | Informativo. |
| **Rupturas coincidentes** | Con el detector sobre el bid de las dos fuentes y el mismo umbral: acuerdo en "hay ruptura y en qué dirección" en **al menos 90%** de las franjas; para las rupturas que coinciden, porcentaje con diferencia de hora de 2 minutos o menos. | Entre 80% y 90%: el análisis principal no cambia y la réplica con HistData se reporta con advertencia. **Menos de 80%**: se detiene la etapa de datos y se busca un error de manejo (zona, formato, huecos). Si no lo hay, el grupo decide antes de abrir validación, lo registra y **no cambia definiciones**. |

**Resultados, 2003-2020.** Control del 1 y 2 de octubre de 2026, con HistData en hora de Nueva York y la réplica sin los períodos fuera de alineación (3.1). `resultados/` no se versiona; los números están en la bitácora, punto G.

| chequeo | resultado |
|---|---|
| Integridad de la barra | **Cumple** todos los años. Dukascopy: 125 barras inválidas de 6.619.380, todas de 2013 por spread ≤ 0 (máximo de 0,034% en un año); además, 10.469 velas planas (minutos sin ticks), que pasan a faltantes. HistData: ninguna barra inválida en 6.224.358. |
| Zona horaria | **Cumple**: máximo en desfase 0 los 18 años, también en un barrido de ±15 horas. Correlación de 0,51-0,77 en 2003-2007 y de 0,87-1,00 desde 2008. |
| Apertura del domingo y cierre del viernes | Dukascopy: 5 de 920 semanas fuera de rango (feriados y un hueco en 2003). HistData: 63 de 916 (datos ralos y feriados). |
| Huecos | Huecos de más de 60 minutos fuera del fin de semana: 20 en Dukascopy y 125 en HistData (sobre todo 2004-2005). |
| Cobertura | Porcentaje de franjas de lunes a viernes bajo 0,90, sin contar la [18,24) del viernes, que siempre queda bajo. Dukascopy: 0%-1,4% por año. HistData: hasta 65% en 2003-2011 y 0,6%-1,7% desde 2012. |
| Horario de verano | **Cumple**: las 35 franjas de 5 o 7 horas caen en los domingos de cambio de hora del Reino Unido. |
| Spread (Dukascopy) | Mediana de 1 pip hasta 2010 (1,4 en 2008), de 0,8-0,9 en 2011-2012 y de 0,3 desde 2013. Más ancho a las 21-22 UTC. 716 barras con más de 10 pips (se reportan, no se borran). |
| Extremos por franja | Mediana de la diferencia entre fuentes: 0,0-0,1 pips desde 2015; 2-5 pips antes de 2010 (HistData más alto). |
| Rupturas coincidentes | **Cumple**: acuerdo de 91,6% a 100%, todos los años sobre el 90%. A 2 minutos o menos: 69%-90% hasta 2011 y 94,5%-100% desde 2012. |

### 3.4 Criterios de exclusión

- Barras inválidas (3.3): pasan a faltantes.
- No se excluyen días por calendario (feriados). El motor descarta, por regla, las franjas de referencia con cobertura menor a 0,90, las que tienen un cierre de mercado entre la referencia y la franja en curso, las de barra ambigua (4.2) y las que no tienen `sigma_ref`. Navidad y Año Nuevo quedan fuera por cobertura.
- Precio faltante en un instante: se usa la última barra cerrada dentro de los 2 minutos anteriores; si no hay, ese resultado queda sin dato. Un horizonte que cruza un cierre de mercado queda sin dato.
- Se reporta cuántos eventos y franjas se pierden en cada paso.

---

## 4. Variables

Todos los valores están en `config.py` (etiqueta `prerregistro-v1`). **Regla de causalidad**: en el instante t solo se usan barras cuyo **cierre** es ≤ t; el índice de cada barra es su hora de apertura, así que su información existe en índice + 1 minuto.

### 4.1 Franjas y referencia

- **Franjas**: cuatro bloques de 6 horas en **hora de Londres** (Europe/London, con horario de verano): [0,6), [6,12), [12,18) y [18,24). Los días de cambio de hora una franja dura 5 o 7 horas.
- **Referencia de la franja k**: la franja k−1. H = máximo de los máximos del precio medio de k−1; L = mínimo de sus mínimos.
- La franja k solo genera eventos si su referencia tiene **cobertura ≥ 0,90** (minutos presentes / esperados), no empezó con el mercado cerrado (hueco inicial ≤ 60 minutos) y no hay un **cierre de mercado** (hueco > 60 minutos) entre k−1 y k. A la franja en curso nunca se le exige cobertura: exigirla sería mirar el futuro.

### 4.2 Eventos

Cada franja produce a lo sumo un evento de cada tipo. La dirección d (+1 alcista, −1 bajista) la fija la ruptura.

- **Ruptura**: primera barra de la franja k cuyo máximo medio supera H + **1 pip** (alcista) o cuyo mínimo medio baja de L − 1 pip (bajista). El evento ocurre en el cierre de esa barra. Si la primera barra que rompe, rompe los dos lados, la franja no genera eventos (**barra ambigua**). Tipo **descriptivo**.
- **Sostenida (H1)**: la ruptura aguanta **15 minutos**: ninguna barra en (t_ruptura, t_ruptura + 15] cierra de vuelta adentro. Se exige la barra exacta que cierra en t_ruptura + 15; si falta, no hay evento. El evento ocurre en t_ruptura + 15, cuando ya se sabe todo lo necesario. Si el plazo pasa del fin de la franja, no hay evento.
- **Reingreso (H2)**: primera barra posterior a la ruptura cuyo cierre medio vuelve adentro, hasta el fin de la franja. El evento ocurre en el cierre de esa barra.
- **"Adentro" es estricto**: para una ruptura alcista, cierre < H; un cierre exactamente en H cuenta como afuera. Para una bajista, cierre > L.

### 4.3 Umbral

Principal: **1 pip** fijo. Robustez: umbral proporcional a la volatilidad, **1,0 × sigma_ref × extremo** (en el simulador equivale en promedio a 1,1 pips).

### 4.4 Volatilidad de referencia (sigma_ref)

Desviación típica de un retorno logarítmico de 1 minuto del precio medio en **ese mismo tipo de franja**, en los **20 días válidos anteriores** (sin incluir el propio día). Solo cuentan pares de barras consecutivas dentro de la misma franja, y un día cuenta solo si esa franja cumple la cobertura de 0,90. Con menos de **10** días válidos no hay `sigma_ref` y la franja no genera eventos.

### 4.5 Horizontes y resultado

- **Horizontes**: 30, 60 y 120 minutos, y **fin de franja** (hasta el fin de la franja del evento o hasta la última barra antes de un cierre de mercado, lo que ocurra primero).
- **Resultado normalizado**: r_h = d · (ln P(t+h) − ln P(t)) / (sigma_ref · √h), con P(t) = cierre medio de la barra que cierra en t y h en minutos. Positivo = el precio sigue en la dirección de la ruptura.
- **Papel de cada horizonte**: 30, 60 y fin de franja **confirman** (familia principal). El de **120 minutos es descriptivo** en la familia principal: se calcula y se reporta en todas las tablas, con su medición, pero no confirma nada (7.4). Sigue dentro de H3 y H4.
- **En pips**: el efecto de una celda se traduce multiplicando por la mediana, entre los eventos de la celda, de sigma_ref · √h · P / pip. Es la traducción evento por evento con los datos reales; la del simulador (sección 6) es solo un orden de magnitud.

### 4.6 Moderadores (H3)

Todos usan información anterior al evento. Valen 1 o 0, y quedan sin dato si no se pueden calcular.

- **cerca_redondo**: el extremo roto está a **5 pips o menos** de un múltiplo de 0,0050 (terminaciones 00 y 50).
- **cerca_extremo_previo**: el extremo roto está a **3 pips o menos** del máximo (ruptura alcista) o del mínimo (bajista) del **último día de Londres anterior con cobertura ≥ 0,50**. Casi siempre es la víspera; para un lunes, el viernes.
- **comprimida**: rango (H − L) de la franja de referencia / mediana del rango de ese mismo tipo de franja en los 20 días válidos anteriores (mínimo 10) **< 0,75**.

### 4.7 Anuncio ("noticia", H4 y control de H3)

- **Principal ("ventana")**: hubo un anuncio de la lista cerrada en los **60 minutos** previos al evento, o sea en (t − 60, t].
- **Robustez ("franja")**: la franja del evento contiene algún anuncio.
- Una sola función marca a los eventos y a los minutos candidatos de la nula.

### 4.8 Lista cerrada de anuncios

Solo anuncios **programados**, con la hora real de publicación que da la fuente oficial. Unos 40 por año en validación.

| institución | publicación | por año | hora habitual | fuente |
|---|---|---|---|---|
| Reserva Federal | Comunicado de política monetaria de las reuniones programadas del FOMC | 8 | 14:00 ET en validación; en otros años cambió, por eso se toma de cada comunicado | federalreserve.gov (calendarios del FOMC y materiales históricos) |
| BLS | Employment Situation (empleo) | 12 | 8:30 ET | bls.gov (calendarios de publicación y hora de embargo de cada comunicado) |
| BLS | Consumer Price Index (IPC) | 12 | 8:30 ET | ídem |
| BCE | Decisiones de política monetaria de las reuniones programadas del Consejo de Gobierno | 8 (mensual antes de 2015) | 13:45 CET hasta junio de 2022; 14:15 CET desde el 21-07-2022 | ecb.europa.eu (comunicados "Monetary policy decisions" y calendario de reuniones) |

- Un anuncio atrasado cuenta en la fecha y hora en que salió; uno cancelado no cuenta.
- **No entran**: reuniones o medidas no programadas (por ejemplo, las de marzo de 2020), minutas, discursos, testimonios ni conferencias de prensa como anuncio aparte (caen dentro de los 60 minutos del comunicado).
- Conversión a UTC con la base de zonas horarias fijada (`tzdata` 2026.4): America/New_York para la Fed y el BLS, Europe/Berlin para el BCE.
- El calendario se arma desde las fuentes en un archivo versionado (`calendario/anuncios.csv`: hora UTC, tipo y URL de la fuente). No contiene precios.
- **Calendario armado** (1 y 2 de octubre de 2026): **767 anuncios de 2003 a 2020**.
  - Por tipo: 216 de empleo, 216 de IPC, 192 del BCE (12 por año hasta 2014 y 8 desde 2015) y 143 de la Fed (8 por año; 7 en 2020, por la reunión cancelada de marzo).
  - En validación: 40 por año (39 en 2020).
- **De dónde sale la hora.**
  - Fed: del comunicado (39) o de las minutas de la reunión (75).
  - BLS: 8:30 ET, verificada en la línea de embargo de 10 comunicados, incluidos los atrasados de octubre de 2013.
  - BCE: 13:45 CET, por la regla publicada; el comunicado no dice su hora.
- **Fed antes de 2009 sin hora explícita.** 29 comunicados no la dicen ni en el comunicado ni en las minutas en HTML: 28 de 2003 a junio de 2006 y el del 25-06-2008. Usan **2:15 p.m. ET**, la práctica de la Fed en esos años, y quedan marcados así en el archivo. Las minutas del 25-06-2008, en PDF, lo confirman: "to be released at 2:15 p.m.".
- **Lo no programado que se excluyó** (`calendario/excluidos.csv`):
  - **Fed**:
    - las conferencias telefónicas: 25-03, 01-04, 08-04 y 16-04-2003; 10-08, 16-08 y 06-12-2007; 09-01, 21-01, 10-03, 24-07, 29-09 y 07-10-2008; 16-01, 07-02 y 03-06-2009; 09-05 y 15-10-2010; 01-08 y 28-11-2011;
    - las reuniones no programadas: 16-10-2013, 04-03-2014, 04-10-2019, 02-03-2020 y 15-03-2020;
    - la reunión cancelada del 17-18-03-2020;
    - los votos por escrito: 19-03, 23-03, 31-03 y 27-08-2020;
    - la reunión del 15-09-2003, que no tuvo comunicado.
  - **BCE**: la decisión coordinada del 08-10-2008. Una decisión del BCE se considera programada si su comunicado dice "At today's meeting" o anuncia la conferencia de prensa de ese día; el día de la semana no sirve, porque varias reuniones programadas fueron en miércoles.
  - También se excluyeron entradas de la lista del BCE que no son decisiones de política monetaria: TARGET2-Securities (2007), y el PEPP y operaciones de liquidez (marzo y abril de 2020).

### 4.9 Variables de emparejamiento de la nula (no son explicativas)

Índice de franja; día de la semana; **decil de sigma_ref** (deciles calculados sobre las franjas que pueden generar eventos); **tercio de la franja** (posición del instante sobre el largo real de la franja, hasta su fin o el cierre de mercado); **tercio de volatilidad reciente** (volatilidad realizada de los 60 minutos previos con barras cerradas, con al menos 30 retornos válidos; si no, grupo "sin dato").

---

## 5. Análisis

### 5.1 Nula emparejada (H1 y H2)

1. **Candidatos**: todos los minutos de franjas que pueden generar eventos y que tienen resultado definido en ese horizonte.
2. A cada evento se le sortea un minuto candidato de su **mismo grupo**, definido por las **cinco variables** de 4.9 (índice de franja, día de la semana, decil de sigma_ref, tercio de la franja y tercio de volatilidad reciente), **excluyendo su propia franja**. Al minuto sorteado se le asigna la dirección del evento y se le calcula el mismo resultado, con la misma función.
3. **Estadístico estudentizado**: el promedio de la celda dividido por su error estándar **agrupado por fecha de Londres**, calculado con la misma función en los datos y en cada repetición.
4. **1.000 repeticiones**. p-valor de una cola con la corrección de Phipson y Smyth (2010): (1 + nº de repeticiones al menos tan extremas) / (1 + 1.000). La cola es la de la hipótesis: "mayor" en sostenidas, "menor" en reingresos.
5. Un evento sin pareja posible queda fuera de la comparación y se reporta.
6. **Efecto reportado** = promedio observado − promedio nulo, en la dirección de la hipótesis, en unidades normalizadas y en pips (4.5).

### 5.2 Familias, correcciones y alfas

| familia | pruebas | estadístico | corrección | alfa | cola |
|---|---|---|---|---|---|
| **Principal (H1, H2)** | 6: {sostenida, reingreso} × {30, 60, fin de franja} | nula emparejada estudentizada (5.1) | **Holm** | **0,025** | una (la de la hipótesis) |
| **Moderadores (H3)** | 24: {sostenida, reingreso} × {30, 60, 120, fin de franja} × {cerca_redondo, cerca_extremo_previo, comprimida} | t del coeficiente en la regresión (5.3) | **Holm** | 0,05 | dos |
| H4 (secundario, no confirma) | 8: {sostenida, reingreso} × 4 horizontes | aleatorización estudentizada (5.4) | Holm dentro de H4, solo como referencia | 0,05 | una ("mayor") |

- **Qué se confirma.** Una celda de la familia principal queda confirmada si su p ajustado por Holm es ≤ 0,025 y el efecto tiene el signo predicho. H1 recibe apoyo si se confirma al menos una celda de sostenidas; H2, si se confirma al menos una de reingresos. Se reportan todas las celdas.
- **Lectura de la pregunta 1** según el resultado (en validación; "sí" = la hipótesis recibe apoyo):

  | H1 (sostenidas) | H2 (reingresos) | lectura |
  |---|---|---|
  | sí | no | Domina la continuación tras las rupturas que aguantan. |
  | no | sí | Domina la reversión tras los reingresos. Por la regla 8.2 (a), no se concluye que no haya continuación. |
  | sí | sí | Operan los dos mecanismos, en momentos distintos de la trayectoria. |
  | no | no | No hay efecto por encima del mínimo detectable (sección 6); se acota su tamaño. |

- En H3, un rechazo en la dirección esperada apoya H3; uno en la dirección contraria se reporta como contrario a H3.
- **Si no se rechaza**, se acota el efecto: se reporta el borde superior del IC95 del efecto de cada celda, en unidades y en pips, junto al efecto mínimo detectable (sección 6).
- **Errores**: agrupados por **fecha de Londres** en todo el estudio (estadístico de la nula, regresiones de H3, diferencia de H4, efecto neto). **Newey-West** se reporta como contraste para los coeficientes de H3 y para el promedio de cada celda principal, con rezagos = piso(4 · (n/100)^(2/9)) (Newey y West, 1994), con n = eventos de la celda en orden de tiempo.
- **Romano-Wolf** (2005) se reporta como **prueba secundaria**, rotulada como otro test: t de la regresión del promedio contra cero, a dos colas, sin la nula, con stepdown sobre 1.000 remuestreos de días. No confirma nada.
- **Descriptivos**, a dos colas y sin corrección: el tipo ruptura (todos los horizontes) y el horizonte de 120 minutos de la familia principal.

### 5.3 Regresiones de H3

Por celda (tipo × horizonte), mínimos cuadrados de r_h sobre:

- constante;
- los tres moderadores probados;
- **noticia** (4.7), como **control** y no como prueba;
- efectos fijos de índice de franja, día de la semana y año (el de año, si la muestra tiene al menos dos años).

Errores agrupados por fecha de Londres, con la corrección de muestra finita G/(G−1) · (n−1)/(n−k). Los eventos sin algún moderador quedan fuera de esa regresión. Un moderador que no varía en una celda deja esa prueba sin estadístico; no ocupa lugar en Holm.

### 5.4 Prueba de H4 (análisis secundario)

- Estadístico: t_dif = (media con anuncio − media sin anuncio) / error agrupado por fecha.
- **Nula por aleatorización** (MacKinnon y Webb, 2020): los pseudo-eventos tienen la misma estructura que los eventos (5.1), pero los "con anuncio" salen **solo** de minutos dentro de una ventana de anuncio, y los "sin anuncio" solo de minutos fuera. 1.000 repeticiones; p-valor de una cola ("mayor") con Phipson y Smyth.
- **Se reporta**: diferencia estimada; **IC95 por inversión de la prueba**, [dif − q97,5 · error, dif − q2,5 · error], con q los cuantiles de los t nulos; p-valor; y como referencia, Holm dentro de las pruebas de H4 que llegan a 15 días tratados. También la versión sin estudentizar.
- Una prueba con **menos de 15 días distintos con evento "con anuncio"** se reporta solo con su estimación y sin p-valor ("descriptiva, muestra insuficiente").
- **H4 no confirma nada, en ningún tramo.** Razón: con 4 años no está calibrada (10,8% de rechazos por prueba bajo la nula con alfa 0,05, con exceso simétrico) ni tiene potencia (efecto mínimo de 0,63-0,82 en reingresos; en sostenidas no se alcanza, y en el 82% de los mercados simulados no llega a 15 días tratados). Es el problema de pocos grupos tratados que estudian MacKinnon y Webb (2020).

### 5.5 Criterio de paso por costos y H5

**Efecto neto, evento por evento.** Para el evento i, con dirección d_i y signo de la hipótesis s (+1 sostenida, −1 reingreso), la posición es q_i = s · d_i.

    P_entrada = ask al cierre de t_i + 1 min  si q_i = +1;  bid  si q_i = −1   (una vela de latencia)
    P_salida  = bid al cierre de t_i + h      si q_i = +1;  ask  si q_i = −1   (instante programado, sin latencia)
    c         = 35 / 1.000.000 por lado (comisión de 35 USD por millón negociado)

    r_neto_i = [ q_i · (ln P_salida − ln P_entrada) − 2c ] / ( sigma_ref_i · √h )

- Precios de Dukascopy, con la misma tolerancia de 2 minutos. "Fin de franja" usa el mismo fin que el resultado bruto.
- **Efecto neto de la celda** = promedio de r_neto_i. IC95 = promedio ± t(0,975; G−1) · error agrupado por fecha de Londres. Es el resultado de operar en el evento, no "observado menos nulo". También se reporta en pips.
- **Criterio de paso a la Etapa 4**: se evalúa en **validación**. Pasa si el límite inferior del IC95 del efecto neto es **> 0 en al menos una celda confirmada** (5.2). En desarrollo se reporta como descripción; en el sellado, como réplica.
- **Sensibilidad pre-declarada**: el efecto neto se repite con comisión de **0 y de 70** USD por millón por lado. No cambia la decisión.
- La comisión es la tarifa publicada de Dukascopy para su tramo más bajo (menos de 5.000 USD de depósito o patrimonio y menos de 5 millones de volumen), cobrada en cada apertura y en cada cierre; se consultó el 25-09-2026 en https://www.dukascopy.com/swiss/english/about/fee-schedule/.
- **Si ninguna celda pasa**: H5 no se evalúa. Se acota el tamaño máximo de efecto compatible con los datos (borde superior del IC95 del efecto bruto y neto por celda, en unidades y en pips). Un efecto real pero no rentable es un resultado válido.

**H5: conjunto cerrado de 12 configuraciones.**

- **Dirección**: la de la hipótesis de la celda (a favor de la ruptura en sostenidas; en contra en reingresos).
- **Entrada**: una vela después del evento, al ask si compra y al bid si vende.
- **Salida**, dos reglas: (1) **por horizonte**, en t + h con h en {30, 60, fin de franja}; (2) **por horizonte o extremo barrido, lo que ocurra primero**: se sale si una barra cierra del otro lado del extremo roto (sostenida: vuelve adentro; reingreso: vuelve afuera), ejecutando una vela después.
- 2 tipos × 3 horizontes × 2 reglas = **12 configuraciones**. Comisión y latencia fijas; la sensibilidad a la comisión no es otra configuración.
- **Solo se evalúan** las de celdas que pasan el criterio de paso, pero **N = 12 siempre**.
- **Selección**: en la Etapa 4, con desarrollo y validación (walk-forward purgado; López de Prado, 2018), se elige UNA configuración: la de mayor Sharpe neto. Solo esa se prueba en el sellado.
- **Criterio de H5**, en el sellado: la configuración elegida tiene resultado neto positivo y **Deflated Sharpe > 0,95** (Bailey y López de Prado, 2014). El DSR usa N = 12, la varianza de los Sharpe de las 12 configuraciones corridas en el sellado, y la asimetría y curtosis de la serie. El Sharpe es sobre el resultado neto diario (días sin operación = 0).
- **Conteo de configuraciones**: cada configuración evaluada en cualquier tramo se anota en `registro/ensayos_h5.csv` (solo se agregan filas: fecha, tramo, configuración, Sharpe y hash). Volver a correr la misma configuración por un error corregido no suma, pero se anota con su motivo.
- Se reportan, sin que decidan: Sharpe con intervalo (Lo, 2002), probabilidad de sobreajuste (Bailey et al., 2017) y la prueba de Ledoit y Wolf (2008) frente a comprar y mantener.

### 5.6 Robustez declarada

Se repite el análisis completo con cada variante. Ninguna confirma nada: se reporta si concuerda o no con el análisis principal.

1. **Segunda fuente**: HistData con **bid** (el principal usa el precio medio de Dukascopy).
2. **Partición fija en UTC** (franjas [0,6), [6,12), [12,18) y [18,24) UTC).
3. **Sin días de anuncio**: se excluyen los eventos cuyo día de Londres tiene algún anuncio de la lista cerrada.
4. **Subperíodos**: cada tramo por año calendario y en dos mitades de años completos (validación: 2017-2018 y 2019-2020; sellado: 2021-2023 y 2024-2026; desarrollo: primera y segunda mitad de sus años). Busca el desgaste asociado al trading algorítmico (Chaboud et al., 2014).
5. **UMBRAL_MODO "vol"**: umbral de 1,0 × sigma_ref × extremo (4.3).
6. **NOTICIA_MODO "franja"** (4.7).

**Calibración de las variantes en el simulador.** Se corrió el control negativo con las mismas semillas que el principal (50 mercados de 3 años y 15 de 13; `--variante`). Tasa por prueba (IC95 remuestreando mercados) y mercados con algún rechazo de Holm:

| variante | principal, alfa 0,05 | principal, alfa 0,025 | principal, familiar (0,025) | moderadores, por prueba | moderadores, familiar | H4 "ventana", por prueba |
|---|---|---|---|---|---|---|
| principal (punto D) | 7,7% [4,3%-11,7%] | 4,0% [2,0%-6,0%] | 8% | 4,8% [3,5%-6,3%] | 0% | 7,5% |
| umbral "vol" | 7,0% [4,3%-10,0%] | 4,0% [2,0%-6,3%] | 4% | 4,4% [3,2%-5,8%] | 2% | 8,3% |
| partición UTC | 6,7% [4,0%-9,7%] | 3,3% [1,3%-5,7%] | 2% | 5,0% [3,5%-6,8%] | **10%** (Wilson 4,3%-21,4%) | 4,2% |

- **Umbral "vol"**: se comporta como la configuración principal. En la cola de la hipótesis contra la opuesta, con 0,05, la asimetría sale distinta de cero: +5,0 puntos [+0,7; +9,0]. Con 0,025 no: +2,7 [−0,3; +5,3]. Son los mismos 50 mercados en que la corrida principal daba +4,0 [−0,7; +8,7]; en los 200 mercados de 4 años del punto E no hay asimetría (6.3).
- **Partición UTC**: por prueba, calibrada. La familia de moderadores rechaza en 5 de 50 mercados (10%; la corrida principal, en 0); el intervalo contiene el 5%. **Ojo**: el simulador ancla su perfil horario a la misma zona que las franjas, así que en esta variante el mercado simulado sigue el reloj UTC. El control no mide el desfase de una hora que el horario de verano produce entre una partición UTC y un mercado anclado a Londres.
- **NOTICIA_MODO "franja"**: solo afecta a H4. Bloque largo del punto D: 10,0% por prueba [4,2%-17,5%].
- **Segunda fuente, sin días de anuncio y subperíodos**: no tienen control en simulación. Cambian la fuente o el subconjunto de datos, no el método.

### 5.7 Qué es exploratorio

- Todo el análisis en desarrollo.
- El tipo ruptura y el horizonte de 120 minutos de la familia principal (descriptivos).
- H4 (secundario pre-especificado: se corre igual, no confirma).
- Romano-Wolf (prueba secundaria).
- Cualquier análisis no descrito aquí se rotula como exploratorio en todo informe.

---

## 6. Potencia y tamaño (medidos con mercados simulados)

### 6.1 Cómo se midió

- **Simulador** (`simulacion/mercado.py`): mercado **sin ningún patrón** por construcción. Tiene semana de mercado de domingo 17:00 a viernes 17:00 (Nueva York), volatilidad anual de 7%, perfil horario de volatilidad por hora de Londres, un régimen de volatilidad diario AR(1), spread de 0,2 pips (triple entre 21:00 y 23:00 UTC) y anuncios que triplican la volatilidad durante 5 minutos **sin empujar el precio**. No tiene tendencia, reversión ni memoria que mire precios pasados.
- **Control negativo** (punto D): 50 mercados de 3 años y 15 de 13 años, con 1.000 repeticiones.
- **Control positivo, diseño D** (punto E): sobre cada mercado limpio se suma delta al retorno normalizado de cada sostenida y se resta de cada reingreso, en todos los horizontes. Potencia = proporción de mercados que rechazan con el signo correcto. 200 mercados de 4 años (duración de validación), 100 de 6 (sellado) y 30 de 13 (desarrollo); 500 repeticiones; efecto mínimo detectable al 80%, con IC95 remuestreando mercados.
- **Control B** (punto E, descriptivo): el efecto se inyecta en los precios y se itera inyectar → detectar hasta que coinciden los eventos. Mide cuánto de un efecto de precio llega a cada celda.
- **H3 y H4** (punto F): el mismo principio aplicado al subgrupo, en 200 mercados de 4 años con el calendario de la lista cerrada (40 anuncios por año).
- **Auditoría causal** (punto E): 40 cortes de la muestra (20 en el instante exacto de un evento). La comparación de todo lo que el motor declara en t, con igualdad exacta, pasa en los 40. Una fuga sembrada de un minuto se detecta.

### 6.2 Alfa de la familia principal

`ALFA_PRINCIPAL = 0,025` lo fijó una regla escrita antes de la corrida larga del punto E, con la tasa **por prueba** en delta = 0 del bloque de 4 años (1.200 pruebas en 200 mercados; IC95 remuestreando mercados):

| alfa | tasa por prueba | IC95 |
|---|---|---|
| 0,05 | 7,4% | 5,5%-9,4% (entero sobre 5%: exceso demostrado) |
| 0,025 | 4,25% | 2,8%-5,8% (el borde inferior no pasa de 5%) |

### 6.3 El tamaño medido en cada bloque

**El tamaño medido de la prueba principal no es el mismo en cada bloque, y se declaran todos, sin promediarlos: con alfa 0,05, 7,4% por prueba en 4 años (200 mercados), 4,3% en 6 años (100 mercados), 6,7% en 13 años (30 mercados) y 7,7% en el control negativo de 3 años (50 mercados; IC95 4,3%-11,7%); con el alfa adoptado de 0,025, 4,25%, 1,5%, 4,4% y 4,0%.**

Tasa familiar (mercados con algún rechazo de Holm) con alfa 0,025: 3,5% (IC95 1,7%-7,0%) en 4 años; 1,0% en 6; 6,7% (1,8%-21,3%) en 13; y 8,0% (4 de 50; 3,2%-18,8%) en el control negativo de 3 años, recalculando Holm sobre las 6 pruebas confirmatorias.

**Diagnóstico de simetría**: tasa por prueba en la cola de la hipótesis contra la cola opuesta, con alfa 0,05 (IC95 de la diferencia, remuestreando mercados):

| bloque | cola de la hipótesis | cola opuesta | diferencia [IC95] |
|---|---|---|---|
| 3 años (punto D) | 7,7% | 3,7% | +4,0 [−0,7; +8,7] |
| 4 años | 7,4% | 6,6% | +0,8 [−1,7; +3,3] |
| 6 años | 4,3% | 5,3% | −1,0 [−4,2; +2,0] |
| 13 años | 6,7% | 11,7% | −5,0 [−12,8; +2,8] |

En 4 años el exceso está en las dos colas: no se demuestra que favorezca a H1 y H2. En el bloque de 3 años, con alfa 0,025, la asimetría sí sale distinta de cero (+2,7 puntos [+0,3; +5,0], 50 mercados).

**La diferencia entre 4 y 6 años no tiene explicación: en la cola de la hipótesis, la tasa por prueba de 4 años supera a la de 6 en +3,1 puntos [+0,4; +5,8] con alfa 0,05 y en +2,75 [+1,0; +4,6] con 0,025, mayor que el azar, y los dos bloques usan el mismo código y la misma nula; solo cambian la duración y las semillas.** Son cuatro intervalos mirados a la vez, sin corregir por multiplicidad. Queda como pregunta abierta.

### 6.4 Efecto mínimo detectable POR CELDA (el titular)

Holm con alfa 0,025, potencia 80%. Unidades de retorno normalizado y, entre paréntesis, pips con el factor mediano pips/unidad del simulador con volatilidad de 7% (5,68 a 30 minutos, 8,04 a 60 y 16,28 a fin de franja).

| celda | **4 años (confirma)** | 6 años | 13 años |
|---|---|---|---|
| reingreso 30 | **0,069** (0,39 pips) | 0,056 (0,32) | 0,036 (0,21) |
| reingreso 60 | **0,067** (0,54) | 0,054 (0,43) | 0,042 (0,33) |
| reingreso fin de franja | **0,067** (1,10) | 0,054 (0,88) | 0,038 (0,61) |
| sostenida 30 | **0,086** (0,49) | 0,075 (0,43) | 0,062 (0,35) |
| sostenida 60 | **0,085** (0,68) | 0,074 (0,60) | 0,060 (0,48) |
| sostenida fin de franja | **0,090** (1,47) | 0,072 (1,17) | 0,057 (0,92) |

- IC95 en 4 años (remuestreando mercados): de 0,002 a 0,008 a cada lado del valor, según la celda.
- El de **familia** (0,050 / 0,041 / 0,028 en 4 / 6 / 13 años) se reporta pero no es el titular: supone que las 6 celdas tienen el efecto y cuenta cualquier rechazo.
- **H3** (4 años, alfa 0,05, Holm sobre 24, dos colas): **0,15-0,32** (reingresos 0,15-0,24; sostenidas 0,22-0,32), entre 2 y 4 veces el de H1 y H2. En pips: ~0,8-1,7 a 30 minutos y ~2,4-5,2 a fin de franja. Tamaño de H3 en delta = 0: 5,4% por prueba; 1,5% de mercados con algún rechazo de Holm (IC95 0,5%-4,3%).
- **H4** (secundario): 0,63-0,82 en reingresos (~4,7 pips a 30 minutos, ~10 a fin de franja); en sostenidas no se alcanza.
- **Costos, como orden de magnitud**: en 4 años, medio pip de ida y vuelta vale 0,03 a 0,09 unidades según el horizonte, del mismo orden que el efecto mínimo detectable. El criterio de paso usa el costo medido evento por evento (5.5).

### 6.5 Supuestos de los que depende

**La potencia se midió en mercados simulados y depende de los supuestos del simulador; en particular, la traducción a pips supone una volatilidad anual de 7%, y con 5% o 10% los mismos efectos valen unos 30% menos o 40% más pips.**

| volatilidad anual | pips por unidad, 30 min | 60 min | 120 min | fin de franja |
|---|---|---|---|---|
| 5% | 4,1 | 5,8 | 8,2 | 11,6 |
| 7% | 5,7 | 8,0 | 11,4 | 16,3 |
| 10% | 8,1 | 11,4 | 16,2 | 23,5 |

Además: el efecto se inyectó como una constante sobre el retorno normalizado (diseño D), no como un mecanismo de precio; los anuncios simulados no empujan el precio; y el número de eventos y de días con anuncio depende del perfil de volatilidad simulado. La traducción definitiva a pips se hará evento por evento con el sigma_ref de los datos reales (4.5).

---

## 7. Cambios respecto de la propuesta

1. **Holm en vez de Romano-Wolf como corrección principal.** Tal como están implementados, no son dos correcciones del mismo test sino dos tests distintos. Holm corrige los p-valores de la nula emparejada, a una cola. Romano-Wolf prueba el promedio contra cero con el t de la regresión, a dos colas y sin la nula, porque su bootstrap necesita un estadístico común. El test que se pre-registra es la nula emparejada, y Holm es válido con cualquier dependencia entre pruebas. Romano-Wolf se reporta como prueba secundaria. Decidido sin mirar la curva de potencia. La propuesta citaba también el Reality Check de White (2000) junto a Romano-Wolf: tampoco se usa en las familias de pruebas. La búsqueda de H5 se penaliza con el Deflated Sharpe y la probabilidad de sobreajuste (5.5).
2. **Emparejamiento por tercio de la franja y por volatilidad reciente**, además de franja, día y decil de volatilidad. Un evento no ocurre en cualquier minuto: tiende a llegar en un momento determinado de la franja y justo después de una expansión. Comparar con minutos de otro momento o de otra volatilidad reciente era comparar cosas distintas. Ninguno de los dos cambios mejoró la calibración en el control negativo; se mantienen por ser correctos a priori, y los estratos siguen holgados.
3. **Errores agrupados por fecha de Londres en vez de Newey-West** como especificación principal. Los eventos del mismo día comparten shocks; Newey-West queda como contraste (5.2).
4. **El horizonte de 120 minutos es descriptivo** en la familia principal. En el control negativo, esa celda rechazó entre el 14% y el 16% de las veces bajo la hipótesis nula, así que no se usa para confirmar. No se esconde: se reporta con su medición.
5. **Alfa 0,025 en la familia principal.** Lo fijó una regla escrita antes de la corrida: con 0,05 la tasa por prueba medida en 4 años (7,4%, IC95 5,5%-9,4%) supera el 5%; con 0,025 (4,25%, IC95 2,8%-5,8%) no se demuestra exceso (6.2).
6. **H4 pasa a análisis secundario, medido por aleatorización.** La propuesta la medía con un indicador de anuncio en la regresión. En el control negativo ese coeficiente rechazaba el 25% de las veces bajo la nula, porque los eventos con anuncio caben en muy pocos días. La inferencia por aleatorización (MacKinnon y Webb, 2020) corrigió la mayor parte en 13 años, pero en 4 años sigue sin calibrar y sin potencia (5.4). La variable de anuncio queda en la regresión de H3 como control.

Además se precisan tres cosas que la propuesta dejaba abiertas:

- "Ruptura sin reingreso" se operacionaliza como **sostenida** (aguanta 15 minutos). "Nunca se devolvió" exigiría conocer el futuro.
- H3 se prueba a dos colas (1.4).
- El costo del criterio de paso se mide evento por evento con bid/ask, comisión y latencia (5.5).

---

## 8. Limitaciones

1. **Tamaño distinto entre bloques y diferencia sin explicar entre 4 y 6 años.** El tamaño medido de la prueba principal no es igual entre bloques (6.3). La diferencia entre 4 y 6 años es mayor que el azar en la cola de la hipótesis y **no tiene explicación**: mismo código, misma nula, solo cambian la duración y las semillas. Con el alfa adoptado, el tamaño por prueba de 4 años cumple el 5%, pero no puede descartarse un exceso de hasta 5,8%.
2. **Contagio entre celdas.** El 71-73% de las sostenidas tiene un reingreso posterior en la misma franja. En el control B, un efecto de reversión sobre los reingresos se contagia a las sostenidas **en contra de H1**: −29% (30 minutos), −41% (60) y −63% (fin de franja) del delta. Al revés, un efecto de continuación se contagia a los reingresos en −14% a −21%. El contagio siempre va en contra de la otra hipótesis, así que no crea falsos positivos, pero resta potencia. **Regla de interpretación**:
   - (a) si H2 se confirma y H1 no, **no se concluye que no hay continuación**;
   - (b) un efecto negativo en las sostenidas **no se lee como una reversión propia** de ellas.
   
   No se excluyen las sostenidas que reingresan después, porque eso condicionaría en el futuro. En ninguna variante del anexo de sensibilidad la superposición baja del 50%.
3. **La potencia se midió en mercados simulados** y depende de sus supuestos (6.5), en especial de la volatilidad de 7% en la traducción a pips.
4. **Sesgo de 13 años en sostenidas.** En el bloque de 13 años (30 mercados), el estimador de las sostenidas tiene un sesgo de −0,004 a −0,007, a unos 2 errores de Monte Carlo de cero. Va contra H1 y es chico frente al efecto mínimo detectable de esas celdas (0,057-0,062). No se investigó más.
5. **H4** no está calibrada con 4 años: 10,8% por prueba (IC95 7,6%-14,4%) y 12% por familia bajo la nula con alfa 0,05, con exceso simétrico. Por eso es secundaria.
6. **Variantes de robustez.** Las variantes "vol" y UTC quedaron calibradas por prueba en el control negativo (5.6), con dos cosas que se declaran:
   - con la partición UTC, la familia de moderadores rechazó en el 10% de los mercados (IC de Wilson 4,3%-21,4%);
   - con el umbral "vol", la asimetría a favor de H1 y H2 sale distinta de cero con alfa 0,05, en los mismos 50 mercados que ya la mostraban en la corrida principal.
   
   El control de la partición UTC usa un mercado simulado anclado a UTC. "Sin días de anuncio", los subperíodos y la segunda fuente no tienen control en simulación.
7. **La segunda fuente solo tiene bid**, así que la réplica con HistData cambia a la vez el proveedor y el tipo de precio.
8. **El criterio de paso** mira hasta 6 celdas confirmadas y no se corrige por eso. Solo habilita la Etapa 4: lo que confirma H5 está en el sellado, con deflactación por ensayos.
9. **Piso**: con 200 mercados no se detecta un sesgo propio de los eventos (prueba conjunta de Hotelling, p = 0,45), pero los intervalos por celda admiten sesgos de hasta ±0,005 unidades (hasta +0,008 en sostenida a fin de franja), del orden de un décimo del efecto mínimo detectable.
10. **La réplica con HistData no es independiente en 2019-2020.** En esos dos años de validación, HistData coincide con el bid de Dukascopy: la correlación de los cambios de 1 minuto es 1,00000 y los extremos de franja son iguales. En esos dos años la réplica no es una fuente independiente. En 2015-2018 la correlación es 0,99.

---

## 9. Reproducibilidad

- **Repositorio**: https://github.com/Ozzaru/Cuartinhos_EURUSD, etiqueta anotada **`prerregistro-v1`**. Las enmiendas, si las hay, llevan su propia etiqueta (2.5).
- **Entorno**: Python 3.13.2 en Windows 11, con versiones fijas en `requirements.txt`: pandas 2.2.3, numpy 2.4.6, scipy 1.18.1, statsmodels 0.15.0, pyarrow 25.0.1, matplotlib 3.11.2, pytest 9.1.1, tzdata 2026.4 y pytz 2026.3.post1. pandas se queda en 2.2 a propósito (pandas 3 cambió la resolución por defecto de las fechas); desde numpy 2.5 los tests fallan a propósito por un aviso de pandas.
- **Todo parámetro vive en `config.py`**; ningún otro archivo inventa números. Semilla maestra: 20260916.
- **Tests**: `pytest`, con cero avisos (los avisos de obsolescencia se tratan como error).
- **Cómo correr los controles** (los resultados van a `resultados/`, que no se versiona y se regenera):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
python -m experimentos.control_negativo                            control negativo (~18 min)
python -m experimentos.control_negativo --variante umbral_vol      variante de robustez
python -m experimentos.control_negativo --variante particion_utc   variante de robustez
python -m experimentos.control_positivo --piso                     piso y traduccion a pips (~1 min)
python -m experimentos.control_positivo                            curva de potencia y control B (~27 min)
python -m experimentos.diagnostico_tamano                          diagnostico del tamano (segundos)
python -m experimentos.auditoria_causal                            auditoria causal (~20 s)
python -m experimentos.potencia_moderadores                        potencia de H3 y H4 (~11 min)
python -m experimentos.anexo_sensibilidad                          anexo de sensibilidad (~20 s)
```

- El historial de decisiones, con cada número de este documento y su sección de origen, está en `registro/bitacora.md` y `registro/decisiones_F.md`.

## Referencias

- Bailey, D. H., Borwein, J. M., López de Prado, M., y Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance*, 20(4), 39-70.
- Bailey, D. H., y López de Prado, M. (2014). The deflated Sharpe ratio. *The Journal of Portfolio Management*, 40(5), 94-107.
- Campbell, J. Y., Grossman, S. J., y Wang, J. (1993). Trading volume and serial correlation in stock returns. *The Quarterly Journal of Economics*, 108(4), 905-939.
- Chaboud, A. P., Chiquoine, B., Hjalmarsson, E., y Vega, C. (2014). Rise of the machines: Algorithmic trading in the foreign exchange market. *The Journal of Finance*, 69(5), 2045-2084.
- Grossman, S. J., y Miller, M. H. (1988). Liquidity and market structure. *The Journal of Finance*, 43(3), 617-633.
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65-70.
- Ledoit, O., y Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. *Journal of Empirical Finance*, 15(5), 850-859.
- Lo, A. W. (2002). The statistics of Sharpe ratios. *Financial Analysts Journal*, 58(4), 36-52.
- López de Prado, M. (2018). *Advances in financial machine learning*. Wiley.
- MacKinlay, A. C. (1997). Event studies in economics and finance. *Journal of Economic Literature*, 35(1), 13-39.
- MacKinnon, J. G., y Webb, M. D. (2020). Randomization inference for difference-in-differences with few treated clusters. *Journal of Econometrics*, 218(2), 435-450.
- Nagel, S. (2012). Evaporating liquidity. *The Review of Financial Studies*, 25(7), 2005-2039.
- Newey, W. K., y West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703-708.
- Newey, W. K., y West, K. D. (1994). Automatic lag selection in covariance matrix estimation. *The Review of Economic Studies*, 61(4), 631-653.
- Osler, C. L. (2003). Currency orders and exchange rate dynamics. *The Journal of Finance*, 58(5), 1791-1819.
- Osler, C. L. (2005). Stop-loss orders and price cascades in currency markets. *Journal of International Money and Finance*, 24(2), 219-241.
- Phipson, B., y Smyth, G. K. (2010). Permutation p-values should never be zero. *Statistical Applications in Genetics and Molecular Biology*, 9(1), Article 39.
- Romano, J. P., y Wolf, M. (2005). Stepwise multiple testing as formalized data snooping. *Econometrica*, 73(4), 1237-1282.
- White, H. (2000). A reality check for data snooping. *Econometrica*, 68(5), 1097-1126.

---

## Enmiendas

Ninguna (versión 1).

---

## Cambios e incidentes después del borrador del 01-10-2026

Cambios respecto de la etiqueta `prerregistro-borrador-1` (commit `debbfbb`, "pre-registro tal como estaba antes de descargar datos"), según `git diff prerregistro-borrador-1`. **No cambió ninguna definición, prueba, alfa ni parámetro del estudio.** En `config.py` solo se agregó la sección 12 (datos reales); ninguna línea de las secciones 1 a 11 cambió (0 líneas quitadas).

**En este documento** (02-10-2026; la razón es la misma para todos: la etapa de datos se hizo antes del congelamiento, revisando solo la calidad):

| sección | cambio | razón |
|---|---|---|
| Encabezado y 2.6 | El congelamiento ya no es "antes de cualquier descarga" sino "antes de calcular cualquier resultado y antes de la Etapa 3"; datos y calidad, el 1 y el 2 de octubre. | El calendario de datos se adelantó al congelamiento. |
| 2.1 y 2.2 | Los datos de 2003-2020 ya se descargaron y solo se revisó su calidad, sin ningún resultado; evidencia: `registro/aperturas.md` y el candado. | Lo mismo. |
| 2.4 | El candado, descrito tal como quedó programado (`fuentes/`), con sus tests. | Antes estaba descrito como algo por programar. |
| 3.1 | HistData viene en hora de Nueva York con horario de verano (se convierte con `America/New_York`); regla de exclusión de la réplica y lo que excluye en 2003-2020. | El control de calidad mostró la zona en +60 minutos con EST fija (decisión del grupo del 02-10-2026). |
| 3.3 | Resumen de los resultados del control de calidad 2003-2020. | `resultados/` no se versiona. |
| 4.8 | Número final de anuncios; 2:15 p.m. ET para los comunicados de la Fed anteriores a 2009 sin hora explícita; lista de lo no programado que se excluyó. | El calendario se armó desde las fuentes; algunos comunicados antiguos no dicen su hora. |
| 8.10 | La réplica con HistData no es independiente en 2019-2020. | Hallazgo del control de calidad. |

**En el código y los datos del repositorio** (01-10-2026, etapa de datos, punto G de la bitácora):

- **`fuentes/`** (nuevo): el candado y el cargador único (2.4), la conversión a parquet en UTC, el manifiesto de los crudos, la descarga de HistData, el calendario de anuncios y el control de calidad. Tests nuevos: `test_candado.py`, `test_fuentes.py`, `test_calendario.py` y `test_rupturas.py`.
- **`motor/`**:
  - La detección de la ruptura pasó de `eventos.py` a `motor/rupturas.py`, y `motor/__init__.py` ya no importa sus submódulos. Así el control de calidad no carga los módulos de resultados.
  - La detección es **idéntica**: se compararon antes y después 36 combinaciones (6 mercados simulados × 6 variantes de config), con igualdad exacta de la tabla completa de eventos.
- **Archivos versionados nuevos, sin precios**: `calendario/` (anuncios, excluidos y pendientes, este último vacío), `registro/aperturas.md` y `registro/manifiesto_datos.csv`.

**Incidente del 01-10-2026:**

El 01-10-2026, por un error de rango en el exportador de JForex, se descargaron velas de 1 minuto de EUR/USD desde el 04-05-2003 hasta el 01-10-2026, incluido el tramo sellado. Antes de borrarlos, los archivos se abrieron por error en Excel durante unos segundos; Excel solo carga el comienzo del archivo (desde mayo de 2003, tramo de desarrollo), así que no se mostró ningún dato del tramo sellado, y ningún programa del proyecto los leyó. Se registró su tamaño y su SHA-256, se borraron el mismo día y se exportó de nuevo solo hasta el 31-12-2020. El caché interno de JForex también se borró.
