# Punto F, paso 1 — Tabla de decisiones para el pre-registro

- **Fecha**: 2026-09-25.
- **Para qué**: que el grupo fije lo que falta ANTES de escribir el pre-registro.
  Nada de esto usa datos reales: todo sale de los puntos A a E y de mercados
  simulados.
- **Lo que ya está decidido** (las seis decisiones del mensaje que abrió el
  punto F) no se reabre aquí; donde una recomendación depende de ellas, se dice.
- **Cómo leer las tablas**: "principal" = va al análisis que confirma;
  "robustez" = se reporta aparte y no confirma nada. "Re-correr" dice qué
  controles cambian si el grupo elige otro valor, y cuánto tardan con la memoria
  libre de hoy (unos 3 GB).

Tiempos de referencia de los controles (medidos en D y E):

| control | comando | tiempo |
|---|---|---|
| negativo (50 x 3 años + 15 x 13 años) | `python -m experimentos.control_negativo` | ~18 min |
| positivo, curva D + control B | `python -m experimentos.control_positivo` | ~27 min |
| piso y traducción a pips | `python -m experimentos.control_positivo --piso` | ~1 min |
| auditoría causal | `python -m experimentos.auditoria_causal` | ~20 s |
| potencia de H3 y H4 (nuevo, parte c) | `python -m experimentos.potencia_moderadores` | ~11 min |
| anexo de sensibilidad (nuevo) | `python -m experimentos.anexo_sensibilidad` | ~20 s |

"Todo" = unos 60 minutos: queda en el límite de la hora, así que cualquier
cambio que obligue a todo se corre con piloto primero (regla vigente).

---

## a) Los parámetros POR DECIDIR

`MIN_DIAS_TRATADOS` quedó fijado en 15 (confirmado en el punto E, "Decisiones
fijadas ANTES de ver la curva", punto 5): se le quitó la marca y no está en la
tabla. Quedan **20**. `HORIZONTE_PRINCIPAL` figura aunque la decisión 3 ya lo
resolvió, para dejar dicho qué se hace con él.

### a.1 Datos y eventos

| parámetro | valor actual | qué afecta | evidencia (bitácora) | recomendación | papel | re-correr si cambia |
|---|---|---|---|---|---|---|
| `COBERTURA_MIN_REFERENCIA` | 0,90 | Qué franjas sirven de referencia (y qué días cuentan para `sigma_ref` y la compresión). | A, decisión 4; B, "Hallazgo: un hueco en la regla de cierres" (con 0,90 el domingo quedaba tapado igual). Los mercados simulados no tienen huecos dentro de la semana: no hay evidencia simulada sobre este número. | **Mantener 0,90.** El control de calidad reporta cuántas franjas excluye por año; si en desarrollo excluye más del 10%, el grupo puede enmendarlo antes de abrir validación. | principal | No en la práctica: sin huecos simulados, los controles darían lo mismo. |
| `UMBRAL_MODO` | "pips" | La forma del umbral de ruptura. | A, decisión 2 ("vol" es robustez). | **Mantener "pips"** como principal y "vol" como robustez (ya está en la lista de robustez del pre-registro). | principal / "vol" robustez | Cambiar el principal: todo (~60 min, con piloto). |
| `UMBRAL_PIPS` | 1,0 | Cuándo hay ruptura: todo lo demás depende de esto. | Anexo de sensibilidad (tabla al final): con 1 pip rompe el 79,5% de las franjas; con 3, el 71%; con 5, el 63%. Todos los controles de D y E se midieron con 1,0. (El "17% de rupturas que aguantan" del punto B venía de un paseo aleatorio simple anterior al simulador; con el simulador de D y E es 40%.) | **Mantener 1,0.** Es el menor umbral que deja fuera el ruido del spread (0,2 pips en el simulador) sin esperar a que la cascada ya ocurrió: Osler (2005) ubica los stops justo detrás de los niveles. | principal | Todo (~60 min, con piloto). |
| `UMBRAL_VOL` | 1,0 | El umbral de la variante "vol" (umbral = 1,0 x `sigma_ref` x extremo). | A, decisión 2. Anexo: con 1,0 el umbral medio es **1,1 pips**, y las tasas de ruptura, sostenida y reingreso quedan a 1-2 puntos de las de 1 pip. | **Mantener 1,0**: la variante cambia la *forma* del umbral (proporcional a la volatilidad de la franja) y no su nivel. | robustez | Ninguno de los controles principales. Ver la nota sobre robustez no calibrada al final de a. |
| `M_SOSTENIDA_MIN` | 15 | Cuánto tiene que aguantar una ruptura para ser sostenida (H1). | Anexo: con 1 pip, aguanta el 61% de las rupturas con M = 5, el 40% con 15 y el 30% con 30. E, "Inyección" y control B: el 71-73% de las sostenidas reingresa después; el anexo lo reproduce (73%) y muestra que **ninguna variante lo elimina** (entre 50% y 83%). | **Mantener 15.** Cambiar M no resuelve la superposición (decisión 3). | principal | Todo (~60 min, con piloto). |
| `REGLA_SOSTENIDA` | "sin_reingreso" | Qué cuenta como aguantar: ningún cierre adentro en (t, t+M], o solo mirar t+M. | B, decisiones y ajustes (barra exacta en t+M con las dos reglas). | **Mantener "sin_reingreso"**: es la que calza con H1 tal como la escribe la propuesta ("ruptura sin reingreso"). | principal | Todo (~60 min, con piloto). |
| `VENTANA_REINGRESO_MIN` | None (hasta el fin de la franja) | Hasta cuándo se busca el reingreso (H2). | E, "Aparte, para la discusión del pre-registro" y control B (superposición). | **Mantener None.** La decisión 3 mantiene las definiciones; acotar la ventana cambiaría H2 después de medir el contagio. | principal | Todo (~60 min, con piloto). |
| `HORIZONTE_PRINCIPAL` | 60 | Nada en el código: solo lo lee `tests/test_config.py`. | Decisión 3 del punto F: la familia no se reduce. | **Eliminarlo** en el paso 2 (y su línea del test). Dejarlo invitaría a leer que hay un horizonte "principal". | — | Ninguno. |
| `DIAS_VOL_REF_MIN` | 10 (de 20) | Desde cuándo existe `sigma_ref`: sin él, el evento se descarta. | A, decisión 4. En los mercados simulados solo toca los primeros días. | **Mantener 10.** Declarar que al empezar validación (y el sellado) las ventanas hacia atrás leen el tramo anterior, que ya está abierto (ver b.2). | principal | No (solo cambia los primeros días de cada mercado). |
| `TOLERANCIA_PRECIO_MIN` | 2 | Si falta la barra de t o de t+h, se acepta la última cerrada hasta 2 min antes. Solo para medir resultados, nunca para declarar un evento. | A y B, "Decisiones de método" y decisión 2 del B. | **Mantener 2.** | principal | No (el simulador no tiene barras faltantes). |

### a.2 Moderadores (H3 y H4)

Prevalencias medidas en 200 mercados de 4 años (parte c), en proporción de
eventos con el moderador encendido:

| tipo | cerca de un redondo | cerca del extremo previo | comprimida | con anuncio (ventana) |
|---|---|---|---|---|
| sostenida | 0,20 | 0,17 | 0,32 | ~0,01 (2,8 días al año) |
| reingreso | 0,20 | 0,14 | 0,28 | ~0,01 (6,9 días al año) |

| parámetro | valor actual | qué afecta | evidencia (bitácora) | recomendación | papel | re-correr si cambia |
|---|---|---|---|---|---|---|
| `PASO_REDONDO` | 0,0050 | Qué es un número redondo (terminaciones 00 y 50). | Propuesta (Osler 2003, 2005: los stops se agrupan detrás de los redondos). C: 2,9% de p <= 0,05; D: la familia de moderadores queda entre 3,5% y 6,3% por coeficiente; parte c: calibrada. | **Mantener 0,0050.** | principal | Control negativo (~18 min) y potencia de H3 (~11 min). La familia principal no cambia. |
| `RADIO_REDONDO_PIPS` | 5 | Cuán cerca del redondo tiene que estar el extremo roto. | Prevalencia 0,20 (lo esperable: 10 de cada 50 pips). Efecto mínimo detectable de H3 en c. | **Mantener 5.** | principal | Igual que la fila anterior. |
| `RADIO_EXTREMO_PREVIO_PIPS` | 3 | Cuán cerca del máximo/mínimo del día anterior. | Prevalencia 0,14-0,17. | **Mantener 3.** | principal | Igual. |
| `DIA_PREVIO_MIN_COBERTURA` | 0,50 | Qué día anterior cuenta (los domingos, con 1-2 horas, no). | B, decisión 3 y ajuste 1 (retrocede al último día utilizable). | **Mantener 0,50.** | principal | No en la práctica (el domingo simulado queda muy por debajo de cualquier umbral razonable). |
| `DIAS_COMPRESION_MIN` | 10 (de 20) | Desde cuándo existe el ratio de compresión. | A, decisión 4 (misma regla que `sigma_ref`). | **Mantener 10**, por coherencia con `DIAS_VOL_REF_MIN`. | principal | No (solo los primeros días). |
| `CORTE_COMPRESION` | 0,75 | Cuándo la franja de referencia cuenta como comprimida. | Prevalencia 0,28-0,32. C, D y parte c: calibrado. | **Mantener 0,75.** | principal | Control negativo (~18 min) y potencia de H3 (~11 min). |
| `VENTANA_NOTICIAS_MIN` | 60 | Cuánto después de un anuncio un evento cuenta como "con anuncio" (H4). | C, opción E (ampliarla para ganar muestra: **no recomendada**, sería acomodar la hipótesis a la estadística); D, conteos; partes d y e (abajo). | **Mantener 60.** | principal ("franja" es robustez) | Control negativo (~18 min) y potencia de H4 (~11 min). |

### a.3 Nula emparejada

| parámetro | valor actual | qué afecta | evidencia (bitácora) | recomendación | papel | re-correr si cambia |
|---|---|---|---|---|---|---|
| `NULA_GRUPOS_VOL_RECIENTE` | 3 | En cuántos grupos se parte la volatilidad reciente para emparejar. | D (3a parte): los estratos aguantan (1.462 con datos, mediana 433 candidatos, 0,8% de eventos en estratos con menos de 100). No compró calibración y se mantuvo por ser correcto a priori. | **Mantener 3.** | principal | Negativo, positivo y potencia de H4 (~55 min, con piloto). |
| `VENTANA_VOL_RECIENTE_MIN` | 60 | Cuántos minutos hacia atrás mide la volatilidad reciente. | D (3a parte). | **Mantener 60.** | principal | Igual que la fila anterior. |

### a.4 Costos

| parámetro | valor actual | qué afecta | evidencia (bitácora) | recomendación | papel | re-correr si cambia |
|---|---|---|---|---|---|---|
| `COSTOS_IDA_VUELTA_PIPS` | [0,5; 1; 2] | Solo la lectura aproximada de la curva de potencia contra un costo. | E (2a parte), punto 5; cierre de E. | **Mantener la grilla y cambiar la marca** por "grilla de lectura": el costo del criterio de paso es el medido evento por evento (b.6). | descriptivo | Solo el reporte (`--solo-reporte`, segundos). |
| **nuevo** `COMISION_USD_POR_MILLON_LADO` | — | La comisión del efecto neto (criterio de paso y H5). | Tarifa publicada de Dukascopy (la fuente de los datos): 35 USD por millón de USD negociado en el tramo más bajo (menos de 5.000 USD de depósito o patrimonio y menos de 5 millones de volumen; Dukascopy aplica el criterio más favorable al cliente), cobrada en cada apertura y en cada cierre. Interactive Brokers cobra 0,20 pb (20 USD por millón). | **35 USD por millón por lado**: es la tarifa de la misma fuente cuyo bid/ask se usa y la que pagaría una cuenta como la del grupo. En retorno logarítmico son 0,70 pb ida y vuelta (unos 0,77 pips con el precio en 1,10). Se reporta también el efecto neto sin comisión, como cota. Guardar en el pre-registro la URL y la fecha de consulta de la tarifa. | principal | No: los controles miden efectos brutos. |
| **nuevo** `LATENCIA_VELAS` | — | Cuántas velas después de la señal se ejecuta la entrada. | Propuesta ("una vela de latencia"). | **1.** | principal | No. |

### Nota: las variantes de robustez no están calibradas

Ningún control corrió con `UMBRAL_MODO = "vol"`. `NOTICIA_MODO = "franja"` sí
(D, bloque largo, solo H4). Opción: correr el control negativo con
`UMBRAL_MODO = "vol"` (~18 min) para declarar su tamaño. Si no se corre, el
pre-registro dice que esa variante no se calibró.

---

## b) Decisiones de protocolo

### b.1 Lista cerrada de anuncios que cuentan como "noticia"

**Recomendación**: cuatro series, solo anuncios **programados**, con la hora
real de publicación que da la fuente oficial:

| institución | publicación | por año en validación | hora habitual | fuente de fecha y hora |
|---|---|---|---|---|
| Reserva Federal | Comunicado de política monetaria de las reuniones **programadas** del FOMC | 8 | 14:00 ET en validación; en años anteriores la hora cambió, por eso se toma de cada comunicado y no de una regla (a verificar en la etapa de datos) | federalreserve.gov: calendarios del FOMC y materiales históricos (la hora sale del comunicado). |
| BLS | Employment Situation (empleo) | 12 | 8:30 ET | bls.gov: calendarios de publicación por año y hora de embargo de cada comunicado archivado. |
| BLS | Consumer Price Index (IPC) | 12 | 8:30 ET | ídem. |
| BCE | Decisiones de política monetaria de las reuniones **programadas** del Consejo de Gobierno | 8 (mensual antes de 2015) | 13:45 CET hasta junio de 2022; **14:15 CET desde el 21 de julio de 2022** | ecb.europa.eu: comunicados "Monetary policy decisions" y calendario de reuniones. |

Unos **40 anuncios por año** en validación (el simulador de D y E tenía 32).

Reglas:
- Cuenta la **hora real** de publicación. Un anuncio atrasado (por ejemplo, por
  un cierre del gobierno de EE. UU.) cuenta en la fecha en que salió; uno
  cancelado no cuenta.
- **No entran**: reuniones o medidas no programadas (por ejemplo, las de marzo
  de 2020), minutas, discursos, testimonios ni las conferencias de prensa como
  anuncio aparte (caen dentro de los 60 minutos del comunicado).
- Conversión a UTC con la base de zonas horarias fijada (`tzdata` 2026.4):
  America/New_York para Fed y BLS, Europe/Berlin para el BCE.
- El calendario se arma en la etapa de datos, desde las fuentes, en un archivo
  versionado (`calendario/anuncios.csv`: `t_utc`, tipo, URL de la fuente). No
  tiene precios, así que puede armarse antes de abrir validación.

### b.2 Papel de cada tramo

**Recomendación**: la propuesta de partida, con cuatro precisiones.

| tramo | período | papel |
|---|---|---|
| desarrollo | desde el primer día disponible en Dukascopy hasta 2016-12-31 | Se corre primero el análisis pre-registrado completo, con el código de la etiqueta `prerregistro-v1`. Sus resultados son exploratorios. Si llevan a cambiar algo, se registra una **enmienda fechada en OSF antes de abrir validación**. |
| validación | 2017-01-01 a 2020-12-31 | **Confirma H1 a H4** y el criterio de paso por costos. Se abre una sola vez. |
| sellado | 2021-01-01 a 2026-08-31 | Repite exactamente lo mismo una sola vez, en la Etapa 5 (16-20 de noviembre), y es el único tramo donde se prueba **H5**. |

Precisiones:
1. **Código congelado antes de abrir**: antes de abrir validación se crea una
   etiqueta (`validacion-v1`) y su hash se anota en la bitácora; se corre ese
   código, no otro. Igual para el sellado (`sellado-v1`).
2. **Calentamiento**: las ventanas hacia atrás (20 días de `sigma_ref` y de
   compresión, 60 minutos de volatilidad reciente, día anterior) leen el tramo
   anterior, que ya está abierto.
3. **Borde**: un evento pertenece al tramo de su fecha de Londres; sus
   resultados no leen datos posteriores al fin del tramo (quedan NaN).
4. **Cómo se lee el sellado**: una hipótesis que rechaza en validación queda
   "confirmada"; si además rechaza en el sellado, "replicada". Un desacuerdo se
   reporta tal cual, sin combinar los tramos.

### b.3 Qué se puede hacer con validación antes de abrirla, y cómo lo garantiza el código

**Recomendación**: solo control de calidad (b.4), nunca retornos posteriores a
eventos. Tres piezas de código, a programar en la etapa de datos:

1. **Un cargador único** (`datos/cargador.py` o similar) por el que pasa toda
   lectura de precios. Si el rango pedido toca validación o el sellado sin
   `abrir="validacion"` o `abrir="sellado"`, levanta un error.
2. **Con la bandera, deja registro antes de entregar nada**: agrega una línea a
   `registro/aperturas.md` (fecha UTC, tramo, fuente, propósito, hash del commit,
   usuario de git) y exige el árbol de git limpio, para que lo que abre sea
   código commiteado. Una apertura para control de calidad usa
   `abrir="validacion_calidad"` y solo la acepta el módulo de calidad.
3. **Tests que lo vigilan**: que el cargador rechaza fechas de validación y del
   sellado sin bandera; que el módulo de calidad no importa `resultados`, `nula`
   ni `inferencia`; y que ninguna salida suya trae columnas `ret_`. El script de
   descarga rechaza fechas desde 2021-01-01 hasta la Etapa 5.

### b.4 Control de calidad: criterios concretos

Sobre las dos fuentes, por año. Dos datos verificados que cambian la
comparación: **HistData publica en EST fijo (UTC-5, sin horario de verano) y
solo el bid**. La comparación entre fuentes se hace, entonces, con el bid de
Dukascopy.

| chequeo | criterio | si falla |
|---|---|---|
| Integridad de la barra (máximo >= apertura y cierre, mínimo <= ambos, ask >= bid) | menos de 0,1% de barras inválidas | La barra inválida se trata como faltante (no se corrige). Más de 0,1%: se investiga antes de seguir. |
| Zona horaria | Correlación de retornos de 1 minuto entre fuentes para desfases de -120 a +120 min: el máximo tiene que estar en 0 todos los años. | Es un error de manejo: se corrige y se repite. |
| Apertura del domingo y cierre del viernes | Primera barra de la semana entre 21:00 y 23:00 UTC; última del viernes entre 20:00 y 22:00 UTC. | Se listan las semanas fuera de rango. |
| Huecos | Huecos de más de 60 min fuera del fin de semana, listados; % de franjas que no llegan a la cobertura de 0,90, por año. | Informativo (ver `COBERTURA_MIN_REFERENCIA`). |
| Horario de verano | Las franjas de los días de cambio duran 5 o 7 horas; las semanas en que EE. UU. y el Reino Unido no coinciden, bien ubicadas. | Error de manejo: se corrige. |
| Spread (Dukascopy) | Distribución por hora UTC y año; más ancho en el cierre de Nueva York. Spread <= 0: barra inválida. Más de 10 pips: se reporta, no se borra. | Informativo. |
| Extremos por franja | Diferencia de H y L entre fuentes, en pips: mediana y percentil 95 por año. | Informativo; alimenta el siguiente. |
| **Rupturas coincidentes** (detector con el bid de las dos fuentes, mismo umbral) | Acuerdo en "hay ruptura y en qué dirección" en **al menos 90%** de las franjas; para las rupturas en que coinciden, % con diferencia de hora de 2 min o menos. | 80-90%: el análisis principal (Dukascopy) no cambia y la réplica con HistData se reporta con advertencia. **Menos de 80%**: se detiene la etapa de datos y se busca un error de manejo (zona, formato, huecos). Si no lo hay, el grupo decide antes de abrir validación, lo registra y **no** cambia definiciones. |

**Criterios de exclusión**: barras inválidas pasan a faltantes. No se excluyen
días por calendario (feriados): el motor ya descarta las franjas sin cobertura,
las que cruzan un cierre, las de barra ambigua y las sin `sigma_ref`. Navidad y
Año Nuevo quedan fuera por cobertura.

### b.5 H5: el conjunto cerrado de configuraciones

**Recomendación**: 12 configuraciones, todas definidas ahora.

- **Dirección**: la de la hipótesis de la celda. Sostenida: a favor de la
  ruptura. Reingreso: en contra (vuelta hacia adentro del rango).
- **Entrada**: una vela después del evento, al ask si compra y al bid si vende.
- **Salida**, dos reglas:
  1. **por horizonte**: en t + h, con h en {30, 60, fin de franja} (los
     horizontes que confirman; el de 120 queda fuera);
  2. **por horizonte o extremo barrido, lo que ocurra primero**: se sale si una
     barra cierra del otro lado del extremo roto de la franja anterior
     (sostenida: vuelve adentro; reingreso: vuelve afuera), ejecutando una vela
     después.
- **Total**: 2 tipos x 3 horizontes x 2 reglas = **12**. Comisión y latencia
  fijas (a.4); la sensibilidad a la comisión no es otra configuración.
- **Cuáles se evalúan**: solo las de celdas que pasen el criterio de costos
  (b.6). Pero **N = 12 siempre**, aunque se evalúen menos.
- **Selección**: en la Etapa 4, con desarrollo y validación (walk-forward
  purgado), se elige UNA configuración: la de mayor Sharpe neto. Solo esa se
  prueba en el sellado.
- **Criterio de H5**: en el sellado, la configuración elegida tiene resultado
  neto positivo y **Deflated Sharpe > 0,95** (Bailey y López de Prado, 2014),
  con N = 12 y la varianza de los Sharpe de las 12 configuraciones corridas en
  ese mismo tramo. Sharpe sobre el P&L neto diario (días sin operación = 0),
  con asimetría y curtosis medidas.
- **Cómo se cuentan**: cada configuración evaluada en cualquier tramo se anota
  en `registro/ensayos_h5.csv` (solo se agregan filas: fecha, tramo,
  configuración, Sharpe, hash). Una configuración fuera de las 12 exige una
  enmienda antes de abrir el sellado y sube N. Volver a correr la misma
  configuración por un error corregido no suma, pero se anota con su motivo.
- Se reportan también, sin que decidan: la probabilidad de sobreajuste
  (Bailey et al., 2017) y la prueba de Ledoit y Wolf (2008).
- **Si ninguna celda pasa el criterio de costos**, H5 no se evalúa: se acota el
  mayor efecto compatible con los datos (borde superior del IC95 del efecto
  bruto por celda, en unidades y en pips). Es la rama que la propuesta ya
  contempla.

### b.6 Fórmula del efecto neto del criterio de paso

Para el evento i, con dirección de la ruptura d_i (+1 o -1) y signo de la
hipótesis s (+1 sostenida, -1 reingreso), la posición es q_i = s · d_i. La señal
existe en t_i (cierre de la barra del evento).

    P_entrada = ask(t_i + 1 min) si q_i = +1;  bid(t_i + 1 min) si q_i = -1
    P_salida  = bid(t_i + h)     si q_i = +1;  ask(t_i + h)     si q_i = -1
    c         = COMISION_USD_POR_MILLON_LADO / 1.000.000   (fracción por lado)

    r_neto_i = [ q_i · (ln P_salida - ln P_entrada) - 2c ] / ( sigma_ref_i · raiz(h) )

- Precios al cierre de la barra que cierra en ese instante (la regla de
  siempre), con la misma tolerancia de 2 minutos. La salida es un instante
  programado y no lleva latencia; para "fin de franja" es el mismo fin que usa
  el retorno bruto.
- Se divide por `sigma_ref` · raiz(h) para que quede en las mismas unidades que
  el efecto bruto y que el efecto mínimo detectable. También se reporta en pips.
- **Efecto neto de la celda** = promedio de r_neto_i. IC95 = promedio ±
  t(0,975; G-1) · error agrupado por fecha de Londres (la misma función que el
  resto del estudio). Es el P&L de operar en el evento, no "observado menos
  nulo".
- **Dónde**: en **validación**, con Dukascopy, en las celdas confirmadas ahí.
  Pasa si el límite inferior del IC95 es > 0 en al menos una. En desarrollo se
  reporta como descripción; en el sellado, como réplica.
- Observación, sin reabrir la decisión 2: "alguna celda confirmada" da hasta 6
  oportunidades y el IC95 no se corrige por eso. Es aceptable porque el paso
  solo habilita la Etapa 4, y lo que confirma H5 está en el sellado con
  deflactación.

---

## c) Potencia de H3 y H4

**Cómo se midió.** El piloto estimó 13 minutos, así que se midió por
simulación además de la aproximación: `python -m experimentos.potencia_moderadores`
(10,6 minutos, 200 mercados de 4 años, calendario de la lista cerrada, 500
repeticiones de la nula de H4). Mismo principio que el diseño D, aplicado al
subgrupo:

- **H3**: a los eventos con el moderador encendido se les suma signo · delta
  (+ en sostenidas, - en reingresos) en los cuatro horizontes, un moderador y un
  tipo a la vez. Holm sobre las 24 pruebas, dos colas, alfa 0,05.
- **H4**: a los eventos con anuncio de los dos tipos se les suma +delta. Holm
  sobre las pruebas que llegan a 15 días tratados, una cola, alfa 0,05.
- Por qué sale casi gratis (probado en los tests contra el cálculo directo):
  sumar delta a una columna de la regresión mueve el coeficiente exactamente
  delta y no toca el error; la nula de H4 sale solo de los minutos sorteados.
- Aproximación: (z(1 - alfa/(m · colas)) + z(0,80)) · desvío · raíz(1/n_con + 1/n_sin),
  con los conteos y el desvío del retorno de los mercados simulados.

**Efecto mínimo detectable al 80%, por celda (4 años, unidades de retorno
normalizado; pips con el factor de 7% del punto E, como orden de magnitud):**

| prueba | simulado (IC95 por mercados) | aproximación (Bonferroni / sin corregir) | en pips, 30 min / fin de franja |
|---|---|---|---|
| H3 comprimida, reingreso | 0,148-0,158 | 0,18 / 0,13 | ~0,8 / ~2,4 |
| H3 comprimida, sostenida | 0,217-0,221 | 0,25 / 0,18 | ~1,2 / ~3,6 |
| H3 cerca de un redondo, reingreso | 0,200-0,215 | 0,20 / 0,14 | ~1,1 / ~3,3 |
| H3 cerca de un redondo, sostenida | 0,287-0,313 | 0,29 / 0,21 | ~1,6 / ~4,8 |
| H3 extremo previo, reingreso | 0,221-0,235 | 0,23 / 0,17 | ~1,3 / ~3,6 |
| H3 extremo previo, sostenida | 0,303-0,319 | 0,31 / 0,22 | ~1,7 / ~5,2 |
| **H4 reingreso** (30 / 60 / 120 / fin) | 0,82 / 0,79 / 0,71 / 0,63 | 0,71-0,74 / 0,57-0,60 | ~4,7 / ~10 |
| **H4 sostenida** | **no llega** (la prueba entra a la familia en el 2% de los mercados) | 1,05-1,10 / 0,84-0,88 | — |

- Los IC95 del simulado van de ±0,01 a ±0,02 en H3 y de ±0,05 a ±0,13 en H4
  (detalle en `resultados/potencia_moderadores.md`).
- Para comparar: H1 y H2 por celda, 0,067-0,090 (punto E). **Una diferencia
  entre subgrupos necesita entre 2 y 4 veces más efecto en H3, y unas 10 veces
  más en H4.**
- La aproximación con Bonferroni calza con la simulación en redondos y extremos
  previos; en compresión la simulación da menos (la regresión con efectos fijos
  gana precisión que la aproximación no ve).
- **Tamaño de H3 en delta = 0** (de paso, otra medición del control negativo, con
  4 años): tasa por prueba 5,4%; mercados con algún rechazo de Holm 1,5%
  (IC95 0,5%-4,3%). **Calibrada.**

## d) Factibilidad de H4

Con el simulador cambiando solo el calendario: se agregó el BCE (8 al año, un
jueves, 12:45 UTC) al empleo, el IPC y el FOMC. **40 anuncios al año**, como la
lista cerrada. Mismos 200 mercados de 4 años.

| tipo | días tratados por año | con el calendario de D/E (mismo mercado, sin el BCE) | en 4 años: media [mín-máx] | mercados que llegan a 15 |
|---|---|---|---|---|
| sostenida | **2,8** | 2,1 | **11,3 [4-20]** | **18%** |
| reingreso | 6,9 | 5,1 | 27,8 [17-43] | 100% |

- El BCE suma ~0,8 días al año en sostenidas (+37%); por tipo de anuncio, en
  sostenidas: empleo 0,85, IPC 0,81, BCE 0,78 y FOMC 0,41 días al año (el FOMC
  cae de noche en Londres, cuando hay menos rupturas).
- **Respuesta**: con la lista cerrada, las sostenidas con anuncio suman unos
  **11 días en 4 años** (antes 8). La prueba de H4 sobre sostenidas **nace
  descriptiva en validación** en más de 8 de cada 10 mercados simulados.
  Contando solo los eventos con retorno y pareja en la nula, la mediana baja a
  9 días y entra en el 2% de los mercados. H4 en validación queda, en la
  práctica, como **4 pruebas sobre reingresos**.
- La regla es automática (`MIN_DIAS_TRATADOS` se aplica sobre los conteos
  reales), así que no hay nada que decidir después de ver los datos.
- Con la definición de robustez ("franja") serían 11,3 días al año en
  sostenidas. No se propone cambiar el modo: se decidió en el punto D y cambiarlo
  por muestra sería la opción E del punto C.
- **Dependencia del simulador**: los anuncios simulados triplican la
  volatilidad 5 minutos y no empujan el precio. Un anuncio real mueve el EUR/USD
  mucho más, así que es probable que en datos reales haya más rupturas justo
  después de un anuncio. El número es un orden de magnitud, no una predicción.

## e) Hallazgo: H4 no queda calibrada con 4 años

Es un control que falla. Siguiendo la regla, **no se ajustó nada**: se explica
y se proponen opciones.

En delta = 0 (mercados sin ningún patrón), con alfa 0,05:

| medición | valor |
|---|---|
| tasa por prueba (787 pruebas que entran a la familia, 192 mercados) | **10,8%** (IC95 por mercados 7,6%-14,4%) |
| la misma tasa en la cola opuesta | 11,1% (8,3%-14,1%) |
| mercados con algún rechazo de Holm | **12,0%** (Wilson 8,2%-17,2%) |
| p medio | 0,513 |
| por días tratados: 15-19 / 20-24 / 25-29 / 30 o más | 12,2% / 12,7% / 6,6% / 2,7% (37 pruebas) |
| punto D, 13 años, mismo modo, pruebas con 15 días o más | 7,5% (120 pruebas) |
| con alfa 0,025 | 6,7% por prueba (4,2%-9,6%); 9,0% por familia |

**Lectura.**

- El exceso es **simétrico**: la cola opuesta rechaza lo mismo. No favorece a
  H4. La nula sale más angosta que la variabilidad real del estadístico
  (sobredispersión).
- Baja cuando hay más días tratados. En validación la mediana es de ~22 días,
  justo donde el exceso es mayor.
- En el punto D no se vio: con 13 años había ~66 días tratados en reingresos y
  la tabla tenía 60 pruebas por celda (el error de Monte Carlo tapaba un 7-8%).
- **Causa probable, sin verificar**: la nula de H4 sortea los pseudo-eventos
  tratados en cualquier minuto de la ventana de 60 minutos. Los eventos reales
  se concentran justo después del anuncio, cuando la volatilidad está triplicada.
  Es la heterogeneidad entre grupos tratados que MacKinnon y Webb (2020) señalan
  como el caso en que también la versión estudentizada se aleja del nivel.

**Opciones para el grupo:**

1. **Extender a H4 la regla del alfa del punto E** (la de la familia principal):
   con 0,05 el IC queda entero sobre 5% y con 0,025 su borde inferior (4,2%) no
   pasa de 5%, así que daría **alfa 0,025 para H4**. Costo: el efecto mínimo en
   reingresos sube de 0,63-0,82 a 0,71-0,91. Queda declarado que la regla se
   aplicó a H4 después de ver este control simulado, antes de cualquier dato
   real. La tasa por familia seguiría en 9%, así que se declara igual.
2. **Declarar la limitación y dejar alfa 0,05**: "en el bloque de 4 años la
   prueba de H4 rechaza 10,8% por prueba y 12% por familia bajo la nula".
3. **Subir `MIN_DIAS_TRATADOS` a 25 o 30**: calibraría mejor, pero con ~22 días
   en validación casi todas las pruebas de H4 nacerían descriptivas. En la
   práctica, H4 dejaría de probarse.
4. **Emparejar los tratados por minutos desde el anuncio** (por ejemplo, 0-5,
   5-15 y 15-60): ataca la causa probable. Es un cambio de método que exige
   re-correr el bloque largo del control negativo y esta potencia (~20 min), con
   la regla de aceptación escrita antes, como en el punto D.

**Recomendación: la opción 1, declarando también el 9% por familia.** Usa una
regla que el grupo ya aprobó, no toca el método, deja H4 medible en reingresos y
no esconde el exceso. La 4 es la más correcta en principio. Pero se hace después
de ver el fallo y con dos días hasta el registro, y el punto D ya mostró dos
arreglos plausibles que no compraron nada. Si el grupo la quiere, que sea con la
regla escrita antes de correr.

---

## Anexo de sensibilidad de la detección (pendiente del punto B)

`python -m experimentos.anexo_sensibilidad`: 5 mercados de 4 años, solo
detección (sin retornos ni nula). Porcentajes sobre las franjas utilizables.

| umbral | M | % franjas con ruptura | % con sostenida | % con reingreso | % de rupturas que aguantan M | % de sostenidas que reingresan |
|---|---|---|---|---|---|---|
| **1 pip** | 5 | 79,5 | 48,5 | 70,5 | 61,1 | 81,8 |
| **1 pip** | **15** | **79,5** | **32,2** | **70,5** | **40,5** | **73,3** |
| **1 pip** | 30 | 79,5 | 23,4 | 70,5 | 29,5 | 64,5 |
| 3 pips | 15 | 71,3 | 47,4 | 53,8 | 66,5 | 64,7 |
| 5 pips | 15 | 62,9 | 49,9 | 40,3 | 79,5 | 56,7 |
| vol 1,0 (1,1 pips) | 15 | 80,7 | 31,5 | 72,1 | 39,1 | 74,0 |
| vol 2,0 (2,2 pips) | 15 | 77,5 | 43,1 | 64,2 | 55,6 | 70,6 |
| vol 3,0 (3,2 pips) | 15 | 73,9 | 50,4 | 56,4 | 68,2 | 66,8 |

En negrita, la configuración actual. La tabla completa (las 18 variantes) está
en `resultados/anexo_sensibilidad.md`. Un umbral más alto cambia reingresos por
sostenidas, pero en todas las variantes reingresa después entre el 50% y el 83%
de las sostenidas.

---

## Otras cosas que aparecieron al preparar la tabla

1. **H3 tiene dirección en la propuesta y se prueba a dos colas.** La propuesta
   dice "ambos efectos se intensifican"; `FAMILIA_MODERADORES` prueba a dos
   colas. Recomendación: el pre-registro declara la dirección y dice que la
   prueba es a dos colas (más exigente); un rechazo en contra se reporta como
   contrario a H3.
2. **H4 en la propuesta tiene dos mitades** ("con anuncios domina la
   continuación y sin ellos la reversión"). La prueba mide la diferencia con
   menos sin anuncio (una cola, "mayor"). La mitad "sin anuncio, reversión" ya la
   cubre H2 en la muestra completa. Hay que escribirlo así en el pre-registro.
3. `FOMC_POR_ANIO` está en `config.py` pero ningún código lo lee (las 8 reuniones
   están fijas en `simulacion/mercado.py`). Recomendación: borrarlo en el paso 2.
4. En el paso 1 se agregaron al código, sin cambiar nada de D y E:
   - el BCE como anuncio simulado opcional (`ANUNCIOS_SIMULADOS`; el calendario
     por defecto quedó idéntico, verificado);
   - `nula.correr_h4(..., con_distribuciones=True)`, que devuelve los t nulos;
   - `experimentos/potencia_moderadores.py` (partes c y d) y
     `experimentos/anexo_sensibilidad.py` (pendiente del punto B), con sus tests.

---

## Lo que decidió el grupo (25-09-2026, antes del paso 2)

- **a)** Se mantienen los 20 valores y se quitan todas las marcas.
  - `HORIZONTE_PRINCIPAL` se elimina, con su test.
  - `COMISION_USD_POR_MILLON_LADO = 35` (coherente con que los precios son de Dukascopy) y `LATENCIA_VELAS = 1`.
  - Sensibilidad pre-declarada: comisión de 0 y de 70.
- **b)** Se aprueban b.1 a b.6, con dos precisiones:
  - b.3: la lectura de validación que hace el control de calidad también se anota en `registro/aperturas.md`, como "lectura de calidad", distinta de la apertura.
  - b.4: la réplica con HistData usa bid; el análisis principal usa el precio medio de Dukascopy.
- **c-e)** H4 pasa a **análisis secundario pre-especificado, no confirmatorio**: se corre igual en cada tramo y se reporta con estimación, IC y p-valor, pero no confirma nada. Lo confirmatorio queda en H1, H2 y H3; H3 sigue confirmatoria, con su potencia declarada (0,15-0,32).
- **f)** Redacciones:
  - H3: dirección esperada la de la propuesta, prueba a dos colas; un efecto en sentido contrario se reporta como tal.
  - H4: se operacionaliza como la diferencia; las dos mitades de la propuesta no se prueban por separado.
- **g)** Se corre el control negativo con `UMBRAL_MODO = "vol"` y, si se puede cambiando solo `ZONA`, con la partición UTC. Si algo falla, se declara y no se ajusta nada.

Aplicado en el paso 2 (ver la bitácora). Además, dos piezas que el pre-registro necesitaba especificadas en código:

- la regla de rezagos de Newey-West, piso(4 · (n/100)^(2/9)) (Newey y West, 1994);
- el IC de H4 por inversión de la prueba de aleatorización.

`FOMC_POR_ANIO`, sin uso, se borró.
