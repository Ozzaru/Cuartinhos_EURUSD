# Pre-registro — Cascada de stops o presión de liquidez: qué ocurre tras las rupturas de rangos intradía en EUR/USD

- **Versión**: 1 (borrador para revisión del grupo; se congela con la etiqueta `prerregistro-v1`).
- **Fecha de redacción**: 25 de septiembre de 2026. **Registro previsto en OSF**: martes 29 de septiembre de 2026.
- **Repositorio**: https://github.com/Ozzaru/Cuartinhos_EURUSD. El registro en OSF cita el hash del commit con la etiqueta `prerregistro-v1`.
- **Cómo está organizado**: cada sección indica, entre corchetes, el campo de la plantilla de pre-registro de OSF al que corresponde.

---

## 1. Estudio

### 1.1 Título [OSF: Title]

Cascada de stops o presión de liquidez: qué ocurre tras las rupturas de rangos intradía en EUR/USD.

### 1.2 Autores [OSF: Authors]

Joshua Barrientos, Joel Vásquez, José Ignacio Moreno, Francisco Piñeda y Santiago López. Magíster en Finanzas, mención Cuantitativa, Escuela de Negocios, Universidad Adolfo Ibáñez.

### 1.3 Descripción y preguntas [OSF: Description; Research questions]

Entre los operadores intradía circula la idea de que el precio "barre" el extremo de un rango previo, activa las órdenes stop acumuladas detrás de ese nivel y enseguida se devuelve. El estudio traduce esa idea a reglas observables y la enfrenta a dos predicciones rivales de la microestructura: **continuación** por cascada de stops (Osler, 2003, 2005) y **reversión** por provisión de liquidez (Grossman y Miller, 1988; Campbell, Grossman y Wang, 1993; Nagel, 2012).

Preguntas:

1. Tras romper el extremo del rango de la franja horaria anterior, ¿el EUR/USD sigue en la dirección de la ruptura o se devuelve?
2. ¿De qué condiciones depende: cercanía a números redondos, a los extremos del día anterior, compresión previa del rango y anuncios macroeconómicos?
3. ¿Sobrevive el efecto a los costos de ejecución?

### 1.4 Hipótesis [OSF: Hypotheses]

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

### 2.1 Tipo de estudio [OSF: Study type]

Estudio **observacional** sobre datos que ya existen (precios históricos de EUR/USD de un minuto y calendarios oficiales de anuncios) y que **los autores no han descargado ni analizado**. No hay manipulación ni asignación aleatoria.

### 2.2 Datos existentes [OSF: Existing data; Explanation of existing data]

**Registro previo al acceso a los datos.** Ningún autor ha descargado ni analizado precios de EUR/USD para este estudio. Como cualquier observador del mercado, los autores pueden haber visto gráficos del par, pero ninguno ha calculado las variables definidas aquí ni ha mirado retornos después de rupturas de franja. Todo el desarrollo previo al registro (motor de eventos, pruebas estadísticas, controles de calibración y de potencia) se hizo con **mercados simulados**, y está en el repositorio con su historia de commits y la bitácora (`registro/bitacora.md`).

### 2.3 Papel de cada tramo [OSF: Study design]

| tramo | período | papel |
|---|---|---|
| **desarrollo** | desde el primer día disponible en Dukascopy hasta el 31-12-2016 | Se corre primero el análisis pre-registrado completo, con el código de la etiqueta `prerregistro-v1`. Sus resultados son **exploratorios**. Si llevan a cambiar algo, se registra una enmienda fechada en OSF **antes** de abrir validación (2.5). |
| **validación** | 01-01-2017 a 31-12-2020 | **Confirma H1, H2 y H3** y decide el criterio de paso por costos. Se abre una sola vez. |
| **sellado** | 01-01-2021 a 31-08-2026 | No se descarga hasta la Etapa 5 (16 al 20 de noviembre de 2026). Repite **exactamente** el mismo análisis una sola vez, y es el **único tramo donde se prueba H5**. |

Precisiones:

1. **Código congelado antes de abrir.** Antes de abrir validación se crea la etiqueta `validacion-v1` y su hash se anota en la bitácora; se corre ese código y no otro. Igual para el sellado, con `sellado-v1`.
2. **Calentamiento.** Las ventanas hacia atrás (20 días de `sigma_ref` y de compresión, 60 minutos de volatilidad reciente, día anterior) leen el tramo anterior, que ya está abierto.
3. **Borde.** Un evento pertenece al tramo de su fecha de Londres. Sus resultados no leen datos posteriores al fin del tramo: si un horizonte los necesita, queda sin dato.
4. **Lectura.** Una celda que rechaza en validación queda **confirmada**; si además rechaza en el sellado, **replicada**. Un desacuerdo entre tramos se reporta tal cual; los tramos no se combinan.
5. H4 (secundario) se corre y se reporta igual en los tres tramos.

### 2.4 Apertura única y registro de lecturas [OSF: Blinding]

- Toda lectura de precios pasa por un **cargador único**. Si el rango pedido toca validación o el sellado sin una bandera explícita, el cargador levanta un error.
- Con la bandera, antes de entregar datos, el cargador agrega una línea a `registro/aperturas.md` con fecha UTC, tramo, fuente, propósito, hash del commit y usuario de git, y exige el árbol de git limpio. Hay dos clases de línea:
  - **"lectura de calidad"**: la que hace el control de calidad sobre validación antes de abrirla (3.3). Solo la acepta el módulo de calidad, que no calcula retornos posteriores a eventos.
  - **"apertura"**: la apertura única de validación (Etapa 3) o del sellado (Etapa 5).
- Tests que lo vigilan: el cargador rechaza fechas de validación y del sellado sin bandera; el módulo de calidad no importa los módulos de resultados, nula ni inferencia; ninguna salida suya trae retornos posteriores. El script de descarga rechaza fechas desde el 01-01-2021 hasta la Etapa 5.
- Este mecanismo se programa en la etapa de datos, antes de cualquier descarga de validación, y queda en el repositorio.

### 2.5 Política de enmiendas [OSF: Other]

- **Antes de abrir validación**: se admiten enmiendas fechadas en OSF, cada una con su razón, motivadas por errores o por el análisis de desarrollo. Cada enmienda queda también en la bitácora y en un commit etiquetado.
- **Después de abrir validación**: el análisis confirmatorio no cambia. Si se descubre un error de código, se corrige y se reportan las dos versiones (la registrada y la corregida), con el error documentado en la bitácora y en una nota en OSF.
- Una configuración de H5 fuera del conjunto cerrado (5.5) solo puede agregarse con enmienda **antes de abrir el sellado**, y suma al número de ensayos.

### 2.6 Calendario [OSF: Other]

| fecha | hito |
|---|---|
| 29-09-2026 | registro en OSF |
| 29-09 al 01-10-2026 | descarga de datos hasta 2020 y control de calidad |
| 02-10-2026 | Entrega N1 |
| 05-10 al 23-10-2026 | Etapa 3: análisis en desarrollo; enmiendas, si las hay; apertura de validación; criterio de paso |
| 26-10 al 13-11-2026 | Etapa 4: regla de operación (solo si pasa el criterio), o acotación del efecto |
| 16-11 al 20-11-2026 | Etapa 5: descarga y apertura única del tramo sellado |

---

## 3. Datos

### 3.1 Fuentes [OSF: Data collection procedures]

| fuente | qué | papel |
|---|---|---|
| **Dukascopy** | Velas de 1 minuto de EUR/USD con **bid y ask**, en UTC. El precio medio es (bid + ask) / 2. | **Análisis principal**: todas las definiciones y resultados usan el **precio medio**; el efecto neto usa bid y ask. |
| **HistData** | Velas de 1 minuto de EUR/USD, **solo bid**, en hora EST **fija** (UTC−5, sin horario de verano; se convierte a UTC sumando 5 horas). | **Control y réplica**: la réplica del análisis con HistData usa **bid**, mientras el análisis principal usa el precio medio de Dukascopy. La coincidencia entre fuentes se mide con el bid de las dos. |
| **Calendarios oficiales** | Fecha y hora de los anuncios de la lista cerrada (4.8). | Variable de anuncio (H4) y control en la regresión de H3. |

### 3.2 Períodos [OSF: Sample size; Sample size rationale]

- Los tres tramos de 2.3. El tamaño de muestra lo fija el período, no una regla de parada.
- **Orden de magnitud esperado**, según el simulador (no según los datos): unas 310 sostenidas y 700 reingresos por año. En los 4 años de validación, unas 1.230 sostenidas y 2.790 reingresos.

### 3.3 Control de calidad [OSF: Data exclusion]

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

### 3.4 Criterios de exclusión [OSF: Data exclusion; Missing data]

- Barras inválidas (3.3): pasan a faltantes.
- No se excluyen días por calendario (feriados). El motor descarta, por regla, las franjas de referencia con cobertura menor a 0,90, las que tienen un cierre de mercado entre la referencia y la franja en curso, las de barra ambigua (4.2) y las que no tienen `sigma_ref`. Navidad y Año Nuevo quedan fuera por cobertura.
- Precio faltante en un instante: se usa la última barra cerrada dentro de los 2 minutos anteriores; si no hay, ese resultado queda sin dato. Un horizonte que cruza un cierre de mercado queda sin dato.
- Se reporta cuántos eventos y franjas se pierden en cada paso.

---

## 4. Variables [OSF: Measured variables; Indices]

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

### 4.9 Variables de emparejamiento de la nula (no son explicativas)

Índice de franja; día de la semana; **decil de sigma_ref** (deciles calculados sobre las franjas que pueden generar eventos); **tercio de la franja** (posición del instante sobre el largo real de la franja, hasta su fin o el cierre de mercado); **tercio de volatilidad reciente** (volatilidad realizada de los 60 minutos previos con barras cerradas, con al menos 30 retornos válidos; si no, grupo "sin dato").

---

## 5. Análisis [OSF: Statistical models; Inference criteria]

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

### 5.7 Qué es exploratorio [OSF: Exploratory analysis]

- Todo el análisis en desarrollo.
- El tipo ruptura y el horizonte de 120 minutos de la familia principal (descriptivos).
- H4 (secundario pre-especificado: se corre igual, no confirma).
- Romano-Wolf (prueba secundaria).
- Cualquier análisis no descrito aquí se rotula como exploratorio en todo informe.

---

## 6. Potencia y tamaño (medidos con mercados simulados) [OSF: Sample size rationale]

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

## 7. Cambios respecto de la propuesta [OSF: Other]

1. **Holm en vez de Romano-Wolf como corrección principal.** Tal como están implementados, no son dos correcciones del mismo test sino dos tests distintos. Holm corrige los p-valores de la nula emparejada, a una cola. Romano-Wolf prueba el promedio contra cero con el t de la regresión, a dos colas y sin la nula, porque su bootstrap necesita un estadístico común. El test que se pre-registra es la nula emparejada, y Holm es válido con cualquier dependencia entre pruebas. Romano-Wolf se reporta como prueba secundaria. Decidido sin mirar la curva de potencia.
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

## 8. Limitaciones [OSF: Other]

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

---

## 9. Reproducibilidad [OSF: Other]

- **Repositorio**: https://github.com/Ozzaru/Cuartinhos_EURUSD, etiqueta **`prerregistro-v1`**. El registro en OSF cita su hash.
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
