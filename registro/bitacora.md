# Bitacora de trabajo

Registro por punto de control. Con leer `README.md` y este archivo se puede
retomar el trabajo en una sesion nueva sin mas contexto.

**Convencion de hashes**: el hash anotado es el del commit que cierra el punto
de control. Como el hash solo existe despues de commitear, cada entrada se
completa con un segundo commit pequeno (`bitacora: hash del punto X`).

**Estado general**: Fase 1 (motor, estadistica y controles con datos
simulados). NO se descargan ni se miran datos reales en esta etapa.

---

## Punto de control A — Estructura y configuracion

- **Fecha**: 2026-09-16
- **Commit**: `c915dfa` (`punto A: estructura del proyecto y configuracion`)
- **Tests**: `pytest` -> 5 pasan, 0 fallan (pruebas de humo de `config.py`).

### Que se hizo

- Estructura completa: `config.py`, `motor/`, `simulacion/`, `experimentos/`,
  `tests/`, `registro/`, `datos/` y `resultados/` (las dos ultimas ignoradas
  por git, con un `.gitkeep` para que la carpeta exista al clonar).
- Modulos creados como esqueletos con su docstring: cada uno dice que hara y
  en que punto de control se llena.
- `config.py` con todos los parametros y un comentario por linea. Dos marcas
  distintas: `# POR DECIDIR` (el grupo debe fijarlo antes de pre-registrar) y
  `# PARAMETRO DE SIMULACION` (solo afecta al banco de pruebas, no se
  pre-registra porque los resultados se normalizan por `sigma_ref`).
- Entorno virtual `.venv` con Python 3.13.2 y las dependencias instaladas.
  `requirements.txt` quedo con versiones FIJAS (`==`) para que la tesis se
  pueda reproducir tal cual.
- `pytest.ini` agrega la raiz al path, asi `import config` funciona desde
  cualquier test.
- Repositorio git local inicializado. Sin remoto: nada sale del computador.

### Decisiones de esta sesion que quedan documentadas

1. **Referencia que cruza un cierre de mercado**
   (`REFERENCIA_CRUZA_CIERRE = False`): si entre la franja de referencia y la
   franja en curso hay un cierre de mercado (hueco > `HUECO_CIERRE_MIN`), esa
   franja no genera eventos.
   *Consecuencia esperada, a verificar en el punto B*: la franja [18,24) del
   domingo y la [0,6) del lunes normalmente NO generan eventos. El mercado
   abre domingo a las 17:00 de Nueva York, o sea entre las 22:00 y las 23:00
   de Londres: la franja [18,24) del domingo queda casi vacia (falla la
   cobertura y ademas contiene el cierre), y por lo tanto tampoco sirve como
   referencia para la [0,6) del lunes.
2. **Umbral en modo "vol"**:
   `umbral_precio = UMBRAL_VOL * sigma_ref * extremo_de_referencia`. El
   extremo (H o L) es 100% pasado. `UMBRAL_VOL = 1.0` provisional, porque 0.5
   desviaciones de 1 minuto es menos de 1 pip. El modo principal sigue siendo
   `"pips"`; `"vol"` es solo una prueba de robustez.
3. **Familias de pruebas separadas**: `FAMILIA_PRINCIPAL` (H1 sostenida a una
   cola > 0 y H2 reingreso a una cola < 0, en los 4 horizontes = 8 pruebas) y
   `FAMILIA_MODERADORES` (H3 y H4: 2 tipos x 4 horizontes x 4 moderadores = 32
   pruebas, a dos colas). "ruptura" queda como descriptivo, fuera de ambas.
   El solapamiento entre sostenida y reingreso no invalida Holm (vale con
   cualquier dependencia) y Romano-Wolf lo captura al remuestrear dias.
4. **Dias validos para `sigma_ref` y para la compresion**: un dia pasado cuenta
   para el tipo de franja j solo si esa franja j de ese dia cumple
   `COBERTURA_MIN_REFERENCIA`. Con menos de `DIAS_VOL_REF_MIN` (o
   `DIAS_COMPRESION_MIN`) dias validos, la variable queda NaN y el evento se
   descarta.
5. **Control positivo**: `NULA_REPETICIONES_POTENCIA = 500` (en vez de 1000)
   para que la corrida quepa en tiempo; se reportara el error de Monte Carlo.
   Con Holm sobre 8 pruebas el p-valor minimo alcanzable debe poder bajar de
   0.05/8 = 0.00625, y con 500 repeticiones alcanza (p minimo = 1/501).
6. **Duraciones de potencia**: `ANIOS_POTENCIA = [4, 13]` (4 ~ tramo de
   validacion, 13 ~ tramo de desarrollo). Se agrega 6 (~ tramo sellado) si el
   tiempo lo permite.
7. **Efectos fijos de ano**: se incluyen siempre que la muestra tenga al menos
   2 anos distintos. Misma especificacion en simulados y en reales.
8. **Volatilidad del simulador (7% anual)**: no se pre-registra; queda marcada
   como `# PARAMETRO DE SIMULACION`.
9. **Nota heredada del proyecto anterior**: en su `null_random_entries` los
   pools de instantes candidatos se limitaban a dias habiles
   (`weekday < 5`). Ese filtro NO se copia: aqui el dia de semana sale de la
   fecha de Londres y los pools se arman solo con minutos validos segun las
   reglas de este proyecto.

### Decisiones de metodo fijadas (no llevan POR DECIDIR, pero se pre-registran)

Estas van al pre-registro del punto F aunque el grupo no tenga que votarlas:
son elecciones de metodo, no parametros libres.

- `NULA_DECILES_VOL = 10`: la nula empareja por decil de volatilidad, o sea 10
  grupos. Con menos grupos el emparejamiento seria mas grueso; con mas, algunos
  grupos quedarian sin candidatos suficientes para sortear.
- `TIPO_ERRORES = "cluster"`: los errores estandar se agrupan por fecha de
  Londres, porque los eventos del mismo dia comparten shocks. Newey-West queda
  como alternativa de robustez, no como especificacion principal.
- `RW_REPETICIONES = 1000`: remuestreos de dias del bootstrap de Romano-Wolf.
- **"Dentro" del extremo es estricto**: para una ruptura alcista el precio esta
  adentro solo si `mid_close < H`, y para una bajista solo si `mid_close > L`.
  Un cierre exactamente EN el extremo cuenta como afuera. Afecta tanto al
  reingreso como a la regla `sin_reingreso` de la sostenida.
- **La ruptura sostenida exige la barra exacta que cierra en t_ruptura + M**,
  con las dos reglas. Si esa barra falta, no hay evento sostenido.
  `TOLERANCIA_PRECIO_MIN` se aplica solo a los precios de los retornos:
  declarar que una ruptura aguanto es afirmar algo sobre un instante preciso,
  medir un retorno no.
- **`cerca_extremo_previo` retrocede hasta el ultimo dia de Londres utilizable**
  (el que cumple `DIA_PREVIO_MIN_COBERTURA`), no solo la vispera. Para un lunes
  eso es normalmente el viernes. Asi el moderador no se pierde por el domingo.

### Ajuste posterior al cierre del punto A (mismo dia)

- **pandas bajado de 3.0.5 a 2.2.3** y fijado en `requirements.txt`. Motivo:
  pandas 3 cambio la resolucion por defecto de las fechas y aqui un error de
  unidades de tiempo pasaria en silencio. `pip check` no reporta ningun
  conflicto y el resto de las versiones fijas quedan igual. pandas 2.2 arrastra
  `pytz`, que tambien quedo fijado.
- **numpy bajado de 2.5.3 a 2.4.6** y fijado. Se probo la frontera una por una:
  2.1.3, 2.2.6, 2.3.5 y 2.4.6 conviven limpias con pandas 2.2.3; desde 2.5.0 la
  operacion `indice + pd.Timedelta(...)` levanta un DeprecationWarning de numpy
  desde dentro de pandas ("generic unit for NumPy timedelta"). 2.4.6 es la mas
  reciente sin ese aviso. `pip check` sin conflictos y scipy, statsmodels,
  pyarrow y matplotlib siguen en sus versiones originales, sin necesidad de
  tocarlas.
- **Regla nueva: la corrida de tests termina con CERO avisos.** `pytest.ini`
  trata `DeprecationWarning` y `FutureWarning` como error. Un aviso de esa clase
  suele ser el primer sintoma de un cambio de comportamiento silencioso
  (unidades de tiempo, zonas horarias, manejo de NaN). Si alguna vez uno viene
  de una libreria externa y es inevitable, se silencia solo ese caso, con su
  filtro y su comentario; la regla completa no se apaga.
  Efecto secundario util: el test del cierre de barra suma con `pd.Timedelta`
  a proposito, asi que subir numpy a 2.5 rompe la suite y nadie lo cambia sin
  enterarse.
- **Nuevo modulo `motor/tiempo.py`**: unica puerta de conversion de fechas
  (`a_ns`, `de_ns`, `cierre_ns`, `a_zona`, `a_utc`). Regla del proyecto:
  ningun otro modulo convierte tiempos a mano. `cierre_ns` es la regla de
  causalidad escrita como codigo.
- **`tests/test_tiempo.py`**: 9 pruebas. Nanosegundos enteros con el valor
  exacto de una fecha calculada aparte, paso de un minuto = 60.000.000.000 ns,
  cierre de una barra = apertura de la siguiente, ida y vuelta fecha <-> ns,
  error si la fecha no trae zona, e ida y vuelta UTC <-> Londres identica en
  verano, invierno y los dos dias de cambio de horario de 2020.
- El `.docx` de la propuesta se movio a `docs/` y sigue versionado.

### Pendientes al cerrar el punto A

- Los 16 parametros marcados `# POR DECIDIR` en `config.py` (lista completa en
  el informe del punto A y, mas adelante, en el pre-registro).
- Verificar en el punto B las dos consecuencias esperadas de la decision 1
  (domingo [18,24) y lunes [0,6) sin eventos) y el horizonte `fin_franja`
  cortado por el cierre del viernes.
- Para el **punto E**: el piloto tiene que medir tiempo **y memoria** por
  mercado. El numero de procesos en paralelo se limita para no pasar del ~70%
  de la RAM disponible (procesos = min(nucleos, RAM_disponible * 0.70 /
  memoria_por_mercado)). Sin ese tope, 13 anos de minutos por proceso llenan la
  memoria y el sistema empieza a usar disco.

### Siguiente

Punto de control B: `motor/franjas.py`, `motor/eventos.py`,
`motor/resultados.py` y `motor/moderadores.py` con su bateria de tests.

---

## Punto de control B — Motor de eventos

- **Fecha**: 2026-09-16
- **Commit**: `88b02d0` (`punto B: motor de eventos, resultados y moderadores`)
- **Tests**: `pytest` -> 68 pasan, 0 fallan, 0 avisos.

### Que se hizo

Cuatro modulos del motor, mas un orquestador `motor.preparar()` que encadena
todo: barras -> calendario -> sigma -> eventos -> retornos -> moderadores.

- **`franjas.py`**: la clase `Barras` (datos en arrays, con el instante de
  CIERRE de cada barra ya calculado), la numeracion de `sesiones` de mercado y
  el `calendario` de franjas. El calendario incluye TODAS las franjas del
  periodo, tengan datos o no, para que la referencia de la franja k sea siempre
  su vecina y una franja ausente invalide la siguiente en vez de colarse.
  Los minutos esperados de cada franja salen de su inicio y su fin reales, no
  de un 360 fijo: el dia del cambio de hora una franja dura 5 o 7 horas.
- **`eventos.py`**: deteccion de ruptura, sostenida y reingreso, con un bucle
  por franja y numpy adentro. Para "el primer minuto que cumple X" se usa
  `np.argmax` sobre la mascara, verificando antes que haya algun True.
- **`resultados.py`**: `sigma_por_franja` y `agregar_retornos`. El corazon es
  `_ventana_pasada`, que resume las ultimas N filas VALIDAS anteriores a cada
  fila, con el corrimiento explicito. Es la defensa contra la trampa del
  `rolling()` de pandas, que incluye la fila actual.
- **`moderadores.py`**: los cuatro moderadores de H3 y H4, todos con
  informacion anterior al evento.

### Hallazgo: un hueco en la regla de cierres de mercado

Al escribir el test del lunes aparecio un caso que la regla no cubria. La
comparacion "la referencia y la franja k comparten sesion" detecta un cierre
ENTRE las dos franjas, pero NO uno que ocurra DENTRO de la franja de
referencia antes de su primera barra. Es exactamente el caso del domingo: la
franja [18,24) figura completa en el calendario, pero sus datos empiezan recien
cuando el mercado abre, ya avanzada la franja.

Se agrego al calendario la columna `hueco_inicial` (minutos entre el inicio de
la franja y su primera barra) y ahora la referencia tambien exige
`hueco_inicial <= HUECO_CIERRE_MIN`. Con la cobertura al 90% el caso quedaba
tapado igual, pero la regla no puede depender de que nadie baje ese umbral.

### Verificacion de la consecuencia anunciada en el punto A

Sobre 12 semanas simuladas con fines de semana de verdad (cierre viernes 21:00
UTC, apertura domingo 21:00 UTC), rupturas detectadas por dia y franja:

| dia | franja 0 | franja 1 | franja 2 | franja 3 |
|-----|---------:|---------:|---------:|---------:|
| lun | **0**    | 10       | 9        | 8        |
| mar | 10       | 8        | 7        | 9        |
| mie | 9        | 10       | 10       | 9        |
| jue | 8        | 10       | 10       | 9        |
| vie | 10       | 9        | 9        | 8        |
| sab | 0        | 0        | 0        | 0        |
| dom | 0        | 0        | 0        | **0**    |

Sale tal cual se anuncio: la franja [0,6) del lunes y la [18,24) del domingo no
generan eventos, y el resto del calendario funciona normal (entre 7 y 10
rupturas por cada 12 o 13 franjas disponibles). El horizonte `fin_franja` de
las rupturas del viernes tarde termina siempre a las 21:00 UTC, o sea en el
cierre y no en el fin nominal de la franja.

### Decisiones de esta etapa

1. **Modulo nuevo `motor/tiempo.py`** (ya venia del ajuste anterior) y **una
   funcion unica de precio**: `resultados.precio_en`. Todo el motor pregunta
   "cual es el precio en el instante t" por ese solo camino, que aplica la
   regla de la barra t - 1 minuto y la tolerancia.
2. **`TOLERANCIA_PRECIO_MIN = 2`** (# POR DECIDIR): se movio a config, porque
   afecta resultados. Se aplica tanto al precio del evento como al precio a
   t + h. Consecuencia declarada: la sostenida con la regla `fuera_en_t_mas_m`
   puede decidirse con una barra de hasta 2 minutos antes de t + M si la exacta
   falta.
3. **`DIA_PREVIO_MIN_COBERTURA = 0.50`** (# POR DECIDIR): parametro nuevo. Sin
   el, `cerca_extremo_previo` de todos los lunes se comparaba contra el domingo,
   que trae una o dos horas de mercado. Con el, esos eventos quedan en NaN.
4. **Desempate de la barra ambigua**: si el grupo apagara
   `EXCLUIR_BARRA_AMBIGUA`, gana el lado que penetro mas, medido en veces el
   umbral de ese lado. Queda declarado en el docstring y probado.
5. **"Dentro" del extremo es estricto**: para una ruptura alcista, el reingreso
   exige `mid_close < H`. Un cierre exactamente en H se considera todavia
   afuera.
6. **Los moderadores binarios van como 1.0 / 0.0 / NaN**, no como booleanos,
   para que las regresiones puedan descartar las filas incompletas.

### Rendimiento medido

| muestra | minutos | franjas | eventos | tiempo | memoria de los datos |
|---------|--------:|--------:|--------:|-------:|---------------------:|
| 1 ano   | 525.600 | 1.460   | 2.643   | 0,35 s | 38 MB |
| 3 anos  | 1.576.800 | 4.380 | 8.107   | 0,88 s | 114 MB |

Extrapolado, 13 anos son unos 4 segundos de pipeline y cerca de 490 MB de datos
por mercado. El tiempo no sera el problema en el punto E; la memoria si, y por
eso el tope de procesos en paralelo ya esta anotado como pendiente.

### Pendientes al cerrar el punto B

- Sigue todo lo del punto A, mas los dos parametros nuevos: ya son **18**
  marcados `# POR DECIDIR`.
- Para el punto D: con `UMBRAL_PIPS = 1.0` rompe cerca del 85% de las franjas y
  solo un 17% de esas rupturas aguanta 15 minutos sin reingresar. Son numeros
  de un paseo aleatorio, no del EUR/USD, pero conviene que el grupo los mire al
  fijar el umbral y M.
- Para el punto E: el motor se queda en float64. Nada de float32, porque las
  comparaciones contra H y L podrian cambiar por redondeo y eso alteraria que
  cuenta como ruptura. Si la memoria aprieta, se bajan los procesos en paralelo
  o se genera el mercado por anos.
- Para el punto F: el borrador lleva un ANEXO DE SENSIBILIDAD, calculado solo
  con mercados simulados y solo descriptivo, para que el grupo elija umbral y M
  con numeros a la vista. Tabla con % de franjas con ruptura, % con sostenida y
  % con reingreso para `UMBRAL_PIPS` en {1, 3, 5}, `UMBRAL_VOL` en {1, 2, 3} y
  `M_SOSTENIDA_MIN` en {5, 15, 30}.

### Ajustes posteriores al cierre del punto B (2026-09-17)


Cuatro cambios pedidos por el grupo, todos con su test:

1. `cerca_extremo_previo` ahora retrocede al ultimo dia utilizable en vez de
   quedar en NaN cuando la vispera es un domingo.
2. El motor se queda en float64 (ver pendientes).
3. La sostenida exige la barra exacta de t_ruptura + M con las dos reglas.
4. Quedan escritas como decisiones de metodo la estrictez de "dentro" y el
   alcance de `TOLERANCIA_PRECIO_MIN`.

Tests despues de los ajustes: 70 pasan, 0 fallan, 0 avisos.

---

## Punto de control C — Estadistica

- **Fecha**: 2026-09-17
- **Commit**: `bbf6a69` (`punto C: hipotesis nula emparejada e inferencia`)
- **Tests**: `pytest` -> 91 pasan, 0 fallan, 0 avisos.

### Que se hizo

- **`nula.py`**: la hipotesis nula emparejada. A cada evento se le sortean
  minutos con el mismo indice de franja, el mismo dia de semana y el mismo
  decil de volatilidad, excluyendo su propia franja. Los retornos de TODOS los
  minutos candidatos se precalculan una sola vez, asi cada repeticion es solo
  sortear indices. p-valor de Phipson y Smyth (2010).
- **`inferencia.py`**: minimos cuadrados con errores agrupados por fecha de
  Londres (escritos a mano en numpy, porque el bootstrap repite el ajuste
  decenas de miles de veces), Holm paso a paso y Romano-Wolf (2005) stepdown
  con el maximo del estadistico t, remuestreando DIAS con reemplazo.
- **Refactor previo**: `resultados.calcular_retornos` es ahora el nucleo comun.
  Los eventos reales y los minutos sorteados pasan por la MISMA funcion, asi la
  comparacion no puede desalinearse. Y `eventos.franjas_utilizables` es la
  unica definicion de "franja que puede generar eventos", que la nula reusa
  para decidir de donde puede sortear.

### HALLAZGO IMPORTANTE: el moderador "noticia" rechaza de mas

Al medir la tasa de falsos positivos sobre 30 mercados sin ningun patron, la
familia de moderadores rechaza mucho mas de lo que deberia. Los numeros:

| coeficiente            | % de p brutos <= 0.05 | rechazos tras Holm |
|------------------------|----------------------:|-------------------:|
| `cerca_extremo_previo` | 1,7%                  | 0 de 240           |
| `cerca_redondo`        | 2,9%                  | 0 de 240           |
| `comprimida`           | 5,4%                  | 1 de 240           |
| **`noticia`**          | **25,0%**             | **27 de 176**      |

Esperado: 5% en la primera columna y casi cero en la segunda.

**El problema NO esta en el motor ni en la correccion.** Tres verificaciones:

1. Los errores estandar agrupados coinciden con statsmodels a precision de
   maquina (esta como test).
2. Comparando la variabilidad de las estimaciones ENTRE mercados contra el
   error estandar reportado DENTRO de cada mercado, la razon mediana es 0,98:
   bien calibrado. Pero en `noticia` esa razon llega a 2,86, o sea que el error
   estandar reportado es hasta tres veces mas chico de lo que deberia.
3. Sacando `noticia` de la familia, la tasa de p brutos <= 0.05 baja a 3,3% y
   solo 1 de 30 mercados tiene algun rechazo corregido (3,3%). Correcto.

**La causa, en simple**: casi ningun evento cae cerca de un anuncio. En estos
mercados de prueba el grupo "con noticia" tiene en promedio 4,2 eventos
repartidos en 4,2 dias para los reingresos, y 0,8 eventos para las sostenidas.
El error estandar agrupado se apoya en que haya muchos grupos con variacion; si
el grupo tratado cabe en uno o dos dias, la formula devuelve un numero
demasiado chico y cualquier diferencia parece significativa. Es un problema
conocido en la literatura (pocos clusters tratados; Cameron, Gelbach y Miller
2008; MacKinnon y Webb 2017), no una particularidad de este codigo.

**Romano-Wolf lo corrige**: sobre 15 mercados dio 0 rechazos de `noticia`
contra 13 de Holm. Pero 0 de 15 sugiere que se pasa de conservador, porque en
muchos remuestreos el grupo tratado desaparece y el estadistico queda sin
definir. Habria que medir cuanta potencia queda, y eso es justamente el punto E.

**Opciones para el grupo** (ninguna aplicada, ninguna es obviamente la mejor):

- **A. Exigir un minimo de dias tratados** para que la prueba de `noticia` entre
  en la familia (por ejemplo 20 dias con evento cerca de un anuncio). Si no se
  llega, se informa descriptivamente y sin prueba formal. Simple, transparente y
  facil de pre-registrar.
- **B. Bootstrap wild cluster** solo para `noticia`. Es el remedio estandar de la
  literatura para pocos clusters tratados. Mas trabajo y un metodo mas que
  explicar en la tesis.
- **C. Romano-Wolf como correccion principal** de la familia de moderadores
  (`CORRECCION_PRINCIPAL = "romano_wolf"`), aceptando perder potencia.
- **D. Cambiar como se mide H4**: en vez de un coeficiente en la regresion,
  partir la muestra en "con noticia" y "sin noticia" y comparar cada grupo con
  su propia nula emparejada. La nula es exacta y no depende de que los errores
  estandar sean confiables con pocos datos. Es la opcion que mejor calza con el
  resto del diseno, pero cambia el enunciado operativo de H4.
- **E. Ampliar `VENTANA_NOTICIAS_MIN`** para que mas eventos cuenten como
  tratados. **No recomendada**: cambiaria la hipotesis para acomodar la
  estadistica, que es exactamente lo que un pre-registro busca evitar.

Advertencia sobre estos numeros: el calendario de anuncios usado aqui es de
juguete. El del punto D (empleo, IPC y FOMC, 32 al ano) dara mas eventos
tratados y el problema sera menor, pero no desaparece para las sostenidas, que
son pocas. El control negativo del punto D lo va a medir bien.

### Decisiones de esta etapa

1. **Los deciles de volatilidad se calculan sobre las franjas CANDIDATAS**, no
   sobre los eventos. Asi ningun grupo de emparejamiento queda sin minutos de
   donde sortear.
2. **Holm se aplica a los p-valores brutos de cada familia**: los de la nula
   emparejada para H1 y H2, los de la regresion para H3 y H4. Romano-Wolf, en
   cambio, trabaja siempre sobre los estadisticos t de la regresion, porque
   necesita un estadistico comun y su propio remuestreo. Esa diferencia queda
   declarada y va al pre-registro.
3. **El p-valor de dos colas se centra en el promedio de la nula**, no en cero:
   la distribucion nula no tiene por que estar exactamente centrada.
4. **Una prueba que no se puede correr** (por ejemplo un moderador que no varia
   en esa celda) sale como NaN y no ocupa lugar en la familia de Holm.
5. **Un evento que no tiene con quien emparejarse** queda fuera de la
   comparacion y se informa en `n_descartados`, en vez de compararse consigo
   mismo.

### Rendimiento

Sobre 2 anos simulados con fines de semana: nula con 500 repeticiones, 1,2 s;
Romano-Wolf con 200 remuestreos sobre la familia de 32 pruebas, 1,2 s por
mercado. El punto D es viable con Holm; Romano-Wolf conviene reservarlo para la
tabla final y no para las 50 corridas del control negativo.

### Pendientes al cerrar el punto C

- **Decidir entre las opciones A a E** de `noticia` antes de cerrar el punto D.
  Mientras tanto, el control negativo se corre tal cual y el reporte va a
  mostrar el problema con el calendario de anuncios de verdad.
- Sigue todo lo anterior, incluidos los 18 parametros `# POR DECIDIR`.

### RESUELTO (2026-09-22): H4 pasa a inferencia de aleatorizacion

El grupo decidio la opcion D, con una vuelta de tuerca importante. Queda
cerrado el pendiente anterior.

**Que se decidio.** H4 ya no se mide con el coeficiente de `noticia` en la
regresion. Se mide comparando dos submuestras, "con anuncio" y "sin anuncio",
y se contrasta contra una nula construida por sorteo.

**El estadistico observado** es la diferencia entre submuestras, estudentizada:

    t_dif = (media_con_anuncio - media_sin_anuncio) / error estandar agrupado

**La nula** sortea pseudo-eventos con la misma estructura que los reales (misma
cantidad, mismo indice de franja, mismo dia de semana, mismo decil de
volatilidad) y con la condicion que hace todo el trabajo: los pseudo-eventos
"con anuncio" salen SOLO de minutos dentro de una ventana de anuncio, y los
"sin anuncio" SOLO de minutos fuera. Como la nula ya incorpora que los minutos
de anuncio se mueven mas, lo que sobrevive es el efecto propio del evento. Es
una diferencia en diferencias hecha por sorteo. p-valor de Phipson y Smyth, a
una cola "mayor", porque H4 predice mas continuacion cuando hay anuncio.

**Por que estudentizado y no la diferencia cruda.** MacKinnon y Webb (2020)
muestran que, con pocos grupos tratados y grupos heterogeneos, la inferencia
por aleatorizacion basada en los coeficientes es poco confiable, mientras que
la basada en estadisticos t se mantiene cerca del nivel nominal, a cambio de
algo de potencia. El error estandar se calcula con la MISMA funcion en los
datos reales y en cada repeticion de la nula
(`inferencia.diferencia_agrupada`), y hay un test que lo verifica contando
llamadas. Igual se reportan las dos versiones, con y sin estudentizar, para
tener evidencia propia.

**Literatura citada.**
- MacKinnon y Webb (2020), "Randomization inference for difference-in-differences
  with few treated clusters", Journal of Econometrics 218(2), 435-450. Es la
  base del metodo y del uso del estadistico t.
  PDF: `docs/papers/MacKinnonWebb_2020_inferencia_aleatorizacion.pdf`.
- MacKinnon y Webb (2018), The Econometrics Journal 21(2), 114-135. Por que se
  descarto el bootstrap wild cluster con muy pocos grupos tratados.
- Conley y Taber (2011), REStat 93(1), y Ferman y Pinto (2019), REStat 101(3).
  Alternativas consideradas y no adoptadas.
- Cameron, Gelbach y Miller (2008), REStat 90(3). El problema general de pocos
  clusters, que es el que se encontro en el punto C.

**Lo que cambio en el codigo.**
1. `FAMILIA_H4`: 2 tipos x 4 horizontes = 8 pruebas, corregidas con Holm.
2. `FAMILIA_MODERADORES` baja a 24 pruebas (3 moderadores x 2 tipos x 4
   horizontes). `noticia` SALE de las pruebas pero SIGUE como variable de
   control en la regresion, para que los coeficientes de H3 no queden
   contaminados por los eventos con anuncio.
3. `MIN_DIAS_TRATADOS = 30` (# POR DECIDIR): minimo de dias distintos con
   evento "con anuncio" para que la prueba entre a la familia. Si no se
   alcanza, se informa como "descriptivo, muestra insuficiente", no se corrige
   y no se concluye. Una prueba asi tampoco gasta lugar en la familia de Holm,
   para no castigar a las demas por una prueba en la que no se puede confiar.
   El valor definitivo se calibra con el control negativo del punto D.
4. `NOTICIA_MODO`: `"ventana"` (principal, anuncio en los
   VENTANA_NOTICIAS_MIN minutos previos) y `"franja"` (robustez, cualquier
   evento de una franja que contenga un anuncio). Las dos quedan
   pre-registradas desde ahora, para que despues no parezca que se eligio la
   que convenia. Una sola funcion, `moderadores.marcar_noticia`, las
   implementa, y la usan por igual los eventos y los minutos candidatos.

**Primera evidencia.** Sobre 2 anos simulados con el calendario de anuncios del
punto D, el modo "ventana" deja 15 eventos tratados y el modo "franja" 101. Con
2 anos de datos ninguna prueba llega a 30 dias tratados, asi que todas quedan
descriptivas; con los 13 anos del tramo de desarrollo si deberian llegar.

#### EJEMPLO PARA EL INFORME N1 (guardar)

El caso que resume por que hubo que cambiar el metodo. Mercado simulado sin
ningun patron, o sea donde por construccion NO hay nada que encontrar. Tipo
reingreso, horizonte 30 minutos, modo "ventana":

| dato | valor |
|---|---|
| eventos "con anuncio" | **2** |
| dias distintos con evento tratado | **2** |
| eventos "sin anuncio" | 1.572 |
| diferencia de promedios | 0,88 |
| estadistico t | **5,78** |
| p-valor por regresion (lo que se hacia antes) | del orden de 1e-8 |
| **p-valor por aleatorizacion (lo que se hace ahora)** | **0,16** |

Un t de 5,78 en una regresion es un hallazgo espectacular, del tipo que se
pone en el resumen de una tesis. Aqui esta calculado sobre DOS observaciones
de DOS dias, en datos donde no hay nada que descubrir. La nula por sorteo, que
compara esos 2 eventos contra otros minutos de anuncio igual de volatiles, lo
deja en 0,16: ni cerca de significativo. La moraleja para el informe: el
problema no era el tamano del efecto sino el error estandar, y no se ve mirando
el resultado, solo se ve corriendo el control negativo.

**Lo que tiene que agregar el reporte del punto D** (pedido del grupo):
- Tasa de falsos positivos por familia, con intervalo binomial al 95%:
  `FAMILIA_PRINCIPAL` (8), `FAMILIA_MODERADORES` (24) y `FAMILIA_H4` (8).
- Para H4: esa tasa por tramos de dias tratados (<10, 10-29, 30-99, >=100) y
  por las dos versiones del estadistico. Con eso se fija `MIN_DIAS_TRATADOS`
  con evidencia y no a ojo.
- Para H4: la misma tabla con `NOTICIA_MODO = "ventana"` y con `"franja"`.
- Romano-Wolf tambien en el control negativo, comparado con Holm en cada
  familia.

### Sobre docs/papers/

Carpeta que mantiene el grupo a mano, con los PDF de la literatura citada.
Tiene su propio `.gitignore` que excluye los PDF del repositorio; solo se
versionan el `README.md` y el propio `.gitignore`. No se modifica desde aqui.

### Calendario

El informe N1 es el 2 de octubre. Los puntos D, E y F deberian cerrarse
alrededor del 26 de septiembre. Si una corrida amenaza con pasar de una hora,
se reducen repeticiones o duraciones, se dice en el informe con su error de
Monte Carlo, y se sigue. Los controles no se sacrifican: se sacrifica tamano
de muestra.

---

## Punto de control D — Mercado simulado y control negativo

- **Fecha**: 2026-09-22
- **Commit**: `b488493` (`punto D: mercado simulado y control negativo`)
- **Tests**: `pytest` -> 129 pasan, 0 fallan, 0 avisos.

### El mercado simulado (`simulacion/mercado.py`)

Un mercado donde, por construccion, NO hay nada que descubrir. Ningun
ingrediente mira precios pasados para decidir hacia donde ir.

Lo que SI tiene, porque son cosas que el EUR/USD tiene de verdad y que podrian
confundir al motor si faltaran:

- semana de mercado de domingo 17:00 a viernes 17:00, hora de Nueva York;
- volatilidad que cambia con la hora de Londres;
- regimen de volatilidad lento (AR(1) diario), para que los deciles de
  volatilidad de la nula tengan de donde agarrarse;
- spread bid-ask, triple entre las 21:00 y las 23:00 UTC;
- anuncios macro que multiplican la volatilidad por tres durante cinco
  minutos, SIN empujar el precio hacia ningun lado.

Lo que NO tiene: tendencia, reversion, memoria de volatilidad intradia ni
ninguna relacion entre el pasado y la direccion futura.

**Calibracion verificada** (1 ano, semilla 7): volatilidad anual medida 7,01%
contra 7% pedido; el perfil horario medido correlaciona 0,99 con el pedido;
spread medio 0,233 pips, que es exactamente lo que dan 0,2 pips durante 22
horas y 0,6 durante 2.

**Detalle declarado**: la regla del IPC es "dia 12 de cada mes a las 13:30
UTC", y el dia 12 a veces cae sabado o domingo. Se dejo la regla tal cual esta
escrita en vez de correrla al dia habil siguiente. Consecuencia medida: 11 de
36 anuncios de IPC en 3 anos caen en minutos cerrados y no afectan a nadie. Si
el grupo prefiere moverlos al dia habil siguiente, es un cambio de dos lineas.

### Como se corre

```
python -m experimentos.control_negativo --piloto     mide tiempo y memoria
python -m experimentos.control_negativo              corrida completa
```

**Piloto medido en este equipo** (20 nucleos, 16,8 GB de RAM):

| bloque | duracion del mercado | tiempo por mercado | pico de memoria |
|---|---|---|---|
| corto | 3 anos | 9,5 s | ~0,37 GB |
| largo | 13 anos, H4 con dos modos | 37,7 s | ~0,97 GB |

El numero de procesos en paralelo lo decide `experimentos/recursos.py` a partir
de la memoria DISPONIBLE, no de los nucleos: con 13 anos por proceso, llenar la
memoria haria que el sistema empiece a usar disco y la corrida "paralela"
terminaria tardando mas que la secuencial. En esta maquina habia alrededor de
1 GB libre, asi que la corrida uso 2 procesos y no 20.

La corrida completa (50 mercados de 3 anos mas 15 de 13 anos, con 1000
repeticiones de la nula y Romano-Wolf) tardo entre **11,4 y 14,9 minutos**
segun cuanto mas estuviera haciendo la maquina, bien por debajo del limite de
una hora. Se corrio dos veces y dio exactamente los mismos numeros, que es la
comprobacion de que las semillas hacen su trabajo.

### Resultados del control negativo

**El efecto medio queda en cero.** Entre -0,0065 y +0,0087 segun tipo y
horizonte, con errores de Monte Carlo de 0,003 a 0,005. No hay nada que
distinga esos numeros del cero, que es exactamente lo que se buscaba.

**Tasa de falsos positivos por familia** (50 mercados, alfa = 5%):

| familia | pruebas | tasa bruta | IC 95% | mercados con algun rechazo | IC 95% |
|---|---:|---:|---|---:|---|
| moderadores (24 pruebas) | 1.200 | 0,047 | [0,036, 0,060] | 0,04 | [0,011, 0,135] |
| principal (8 pruebas) | 400 | 0,070 | [0,049, 0,099] | 0,06 | [0,021, 0,162] |

Los dos intervalos contienen el 5%, asi que el control **pasa**. Holm y
Romano-Wolf dan exactamente la misma tasa por familia (0,04 y 0,06).

**Un numero para vigilar.** La familia principal dio 0,070 y su intervalo
apenas alcanza a contener el 5% (el borde inferior es 0,049). El promedio de
sus p-valores es 0,462 en vez de 0,5, y en el histograma se nota una leve
inclinacion hacia la izquierda. Mirando celda por celda, la unica que se
despega es **reingreso a 120 minutos: 0,16** (8 rechazos de 50); las otras
siete van de 0,02 a 0,10. Con 50 mercados no alcanza para saber si es una
miscalibracion real o mala suerte de esa celda. La familia de moderadores, en
cambio, esta impecable: promedio de p-valores 0,50 y tasas de 0,035, 0,043 y
0,063 por coeficiente.

**Hipotesis sobre el origen**, sin tocar nada todavia: la nula empareja por
indice de franja, dia de semana y decil de volatilidad, pero NO por la posicion
del minuto dentro de la franja. Los eventos reales no caen en cualquier minuto
(una ruptura tiende a ocurrir cuando el precio ya se movio), mientras que los
minutos sorteados se reparten por toda la franja. A horizontes largos esa
diferencia pesa mas, que es coherente con que la celda peor sea la de 120
minutos. Opciones si el grupo quiere cerrarlo: (a) correr 50 mercados mas para
ver si el 0,16 se sostiene; (b) agregar la hora del dia como cuarta variable de
emparejamiento; (c) dejarlo documentado como limitacion. **No se cambio nada**:
el control pasa segun el criterio acordado.

### H4: la inferencia de aleatorizacion funciono

Comparacion con lo que habia antes, sobre mercados sin ningun patron:

| metodo | tasa de falsos positivos de `noticia` |
|---|---:|
| coeficiente en la regresion (punto C) | **0,250** |
| aleatorizacion estudentizada (ahora) | **0,067 a 0,100** |

Se acabo el problema grande. Lo que queda esta dentro del ruido: con 60 pruebas
por celda, el error de Monte Carlo es de 2,8 puntos, asi que un 0,083 no se
distingue de un 0,05.

**Y no hay gradiente con los dias tratados.** Esta es la tabla que importa, por
modo y tipo, sobre los 15 mercados de 13 anos:

| modo | tipo | dias tratados (medio, min-max) | tasa estudentizado | tasa sin estudentizar |
|---|---|---|---:|---:|
| ventana | sostenida | 21 (14-32) | 0,100 | 0,083 |
| ventana | reingreso | 58 (39-73) | 0,083 | 0,083 |
| franja | sostenida | 100 (85-118) | 0,083 | 0,067 |
| franja | reingreso | 273 (259-284) | 0,083 | 0,083 |

Con 21 dias tratados rechaza igual que con 273. **La tabla por tramos del
reporte enganaba**: cada combinacion de modo y tipo cae casi entera en un solo
tramo, asi que ahi el tamano de la muestra tratada y el tipo de evento quedan
confundidos y las diferencias entre tramos (0,125 contra 0,068) son ruido.

**Conclusion sobre `MIN_DIAS_TRATADOS`**: la evidencia NO respalda subirlo a
100, y tampoco confirma que 30 sea el numero correcto. En el rango observado
(14 a 284 dias tratados) la calibracion no cambia. Lo que sigue sin probarse es
el rango de menos de 14 dias, que es justo donde el metodo viejo se rompia y
donde ningun mercado de 13 anos llego a caer. Propuesta para el grupo:
**bajar el minimo a 15 o incluso sacarlo**, porque su justificacion original
era el error estandar agrupado y ese ya no se usa; o dejarlo en 30 como margen
de prudencia, sabiendo que con eso la prueba sobre sostenidas nace descriptiva
(ver abajo).

**Estudentizar no cambio nada medible.** Las dos versiones dan practicamente lo
mismo (0,083 contra 0,083, 0,100 contra 0,083). Es esperable: la ventaja que
documentan MacKinnon y Webb aparece con MUY pocos grupos tratados y
heterogeneos, y aqui ninguna celda bajo de 14 dias. Se mantiene la version
estudentizada como principal, tal como quedo pre-registrada, pero conviene
decir en la tesis que en este banco de pruebas las dos se comportaron igual.

### Cuanta muestra va a haber de verdad (lo que se pregunto)

Promedio por ano simulado, sobre los 15 mercados de 13 anos:

| modo | tipo | eventos/ano | tratados/ano | dias tratados/ano | proyectado a 13 anos |
|---|---|---:|---:|---:|---:|
| ventana | sostenida | 311 | 1,7 | **1,7** | **~21 dias** |
| ventana | reingreso | 701 | 4,6 | 4,6 | ~58 dias |
| franja | sostenida | 311 | 8,0 | 8,0 | ~100 dias |
| franja | reingreso | 701 | 21,5 | 21,5 | ~273 dias |

**Respuesta directa: si, con el modo principal "ventana" la prueba de H4 sobre
sostenidas nace descriptiva.** Da unos 21 dias tratados en 13 anos (rango
observado 14 a 32), por debajo del minimo de 30. La de reingresos si pasa, con
unos 58.

Esto invierte el papel de los dos modos: el que se penso como robustez
("franja") es el unico que deja muestra comoda para las dos pruebas. Vale la
pena que el grupo lo discuta antes de pre-registrar, porque cambiar de modo
principal DESPUES de ver los datos reales seria exactamente lo que un
pre-registro busca impedir. Decidirlo ahora, con datos simulados, es legitimo.

### Detalle del calendario simulado

De 36 anuncios de IPC en 3 anos, 11 caen en minutos cerrados porque el dia 12
cayo sabado o domingo. Se mantuvo la regla literal del enunciado. Si el grupo
prefiere correrlos al dia habil siguiente, sube la muestra tratada de H4 cerca
de un 15% y es un cambio de dos lineas.

### Pendientes al cerrar el punto D

- **Decidir `MIN_DIAS_TRATADOS`** con la evidencia de arriba (15, 30 o sin
  minimo).
- **Decidir el modo principal de noticia**, sabiendo que "ventana" deja la
  prueba sobre sostenidas sin muestra.
- **Decidir si se investiga la celda de reingreso a 120 minutos** (0,16 de
  falsos positivos) o se documenta como limitacion.
- Sigue todo lo anterior, incluidos los 19 parametros `# POR DECIDIR`.

---

## Punto D (segunda parte) — Dos arreglos y una hipotesis descartada

- **Fecha**: 2026-09-23
- **Commit**: `c6b6575` (`punto D (2a parte): anuncios en dia habil, tercio de franja e hipotesis descartada`)
- **Tests**: `pytest` -> 140 pasan, 0 fallan, 0 avisos.

### Decisiones que fijo el grupo

1. **`MIN_DIAS_TRATADOS` baja de 30 a 15** (sigue `# POR DECIDIR`, provisional).
   Razon: la tasa de falsos positivos es plana desde 14 dias tratados, asi que
   30 no estaba respaldado por nada; pero el piloto mostro rechazo severo por
   debajo de 10 dias, asi que dejar el minimo en cero tampoco.
2. **`NOTICIA_MODO` principal queda en `"ventana"`**, con `"franja"` como
   robustez pre-registrada. Razon: las dos tienen la misma tasa de falsos
   positivos, o sea que mas muestra no compra calibracion, y la ventana es
   fiel al mecanismo que plantea H4 (el anuncio acaba de ocurrir).
3. **`CORRECCION_PRINCIPAL` queda ABIERTA**, con Holm provisional. Se agrego
   `REPORTAR_AMBAS_CORRECCIONES = True`: toda tabla trae Holm y Romano-Wolf.

   El argumento, que va al informe: **el control negativo mide TAMANO, no
   potencia**. Bajo la hipotesis nula las dos correcciones dan practicamente la
   misma tasa (0 y 0,02 en moderadores; 0,08 y 0,06 en principal), asi que este
   experimento no las distingue. La diferencia entre ellas es otra: **Holm
   controla el error familiar bajo dependencia arbitraria**, asi que la
   correlacion entre horizontes no lo invalida, solo le resta potencia;
   **Romano-Wolf aprende esa dependencia de los datos** y por eso puede detectar
   mas cuando las pruebas estan correlacionadas, que es justo el caso aqui (los
   cuatro horizontes miden el mismo evento). La decision correcta es comparar
   POTENCIA, y eso es el punto E. A 1,2 segundos por mercado, no hay razon para
   elegir a ciegas mientras tanto.

### Arreglo 1: los anuncios de fin de semana

Los anuncios que caian sabado o domingo ahora se corren al siguiente dia con
mercado abierto, como pasa en la realidad. Funciono como se esperaba: la
muestra tratada subio alrededor de un 15% en las cuatro combinaciones.

| modo y tipo | dias tratados antes | despues |
|---|---:|---:|
| franja / reingreso | 273 | 313 |
| franja / sostenida | 100 | 114 |
| ventana / reingreso | 58 | 66 |
| ventana / sostenida | 21 | **24** |

Ese ultimo numero importa: con el minimo en 15, la prueba de H4 sobre
sostenidas con el modo "ventana" **ya entra en la familia** (el minimo
observado en 15 mercados fue 18 dias). Con el minimo anterior de 30 habria
nacido descriptiva.

### Arreglo 2: emparejar por tercio de franja — LA HIPOTESIS ERA FALSA

Se agrego la posicion dentro de la franja como cuarta variable de
emparejamiento, calculada sobre el largo REAL de la franja:

    posicion = (instante - inicio real) / (fin real - inicio real)

donde el fin real es el que llegue primero entre el fin de la franja y el
cierre del mercado. Asi funciona igual en los dias de cambio de hora (franjas
de 5 o 7 horas) y en la franja recortada del viernes. Vive en
`franjas.posicion_en_franja` y `franjas.tercio_de_franja`, y la usan por igual
los eventos y los minutos candidatos.

**Los estratos no se quedaron sin candidatos**, asi que no hizo falta bajar a
quintiles: con franja x dia x decil x tercio quedan 531 estratos con datos, la
mediana tiene 1.904 minutos candidatos, el mas pobre tiene 46, y de 5.383
eventos solo 7 quedan sin pareja posible.

**Y no arreglo nada.** Esta es la comparacion, con todo lo demas igual:

| | antes | ahora |
|---|---:|---:|
| familia principal, tasa bruta | 0,070 | 0,0675 |
| familia principal, p-valor medio | 0,462 | 0,463 |
| **celda reingreso a 120 minutos** | **0,16** | **0,16** |
| familia moderadores, tasa bruta | 0,047 | 0,048 |
| H4, tasa por modo y tipo | 0,067-0,100 | 0,050-0,117 |

La celda de 120 minutos quedo exactamente igual: 8 rechazos de 50 antes y
despues. La hipotesis de que el exceso venia de comparar momentos distintos de
la franja **queda descartada**.

Se decidio **mantener** el emparejamiento por tercio de todas formas: es a
priori mas correcto comparar un evento del principio de la franja con minutos
del principio, los estratos siguen holgados y no cuesta tiempo. Pero queda
dicho que no compra calibracion, y revertirlo es quitar una linea de la clave.

Siguiendo la instruccion del grupo, **no se probaron mas variantes**. Buscar
hasta que una calce seria elegir el metodo mirando el resultado.

### Estado del control negativo despues de los arreglos

| familia | tasa bruta | IC 95% | mercados con algun rechazo (Holm / RW) |
|---|---:|---|---|
| moderadores (24 pruebas) | 0,048 | [0,038, 0,062] | 0,00 / 0,02 |
| principal (8 pruebas) | 0,0675 | [0,047, 0,096] | 0,08 / 0,06 |

Los dos intervalos contienen el 5%. La familia principal sigue con su leve
exceso, concentrado en reingreso a 120 minutos.

### El corte calibrado por tamano: NO es viable

Se calculo la propuesta que pidio el grupo: el corte de p que dejaria cada
familia en 5% de mercados con algun rechazo. El resultado es que **no se puede
fijar un numero**:

| familia | corte calibrado | IC 95% | mercados para que el IC mida 0,01 |
|---|---:|---|---:|
| principal (Holm) | 0,023 | [0,012, 0,147] | **9.134** |
| moderadores (Holm) | 0,074 | [0,054, 0,165] | 6.149 |

El intervalo del corte de la familia principal va de 0,012 a 0,147: doce veces
mas ancho que el propio corte. Fijar 0,023 seria inventar precision. Para
estrecharlo a 0,01 harian falta unos 9.100 mercados, o sea unas 40 horas de
computo, porque el ancho de un percentil se encoge con la raiz del numero de
observaciones y aqui se esta estimando el percentil 5 con 50 datos.

Dato util de paso: el corte calibrado de la familia de MODERADORES sale en
0,074, o sea POR ENCIMA de 0,05. Esa familia no esta rechazando de mas, esta
rechazando de menos: es conservadora.

**Recomendacion: no adoptar el corte calibrado.** Las dos opciones que quedan
para la celda de 120 minutos son las que puso el grupo sobre la mesa: sacar ese
horizonte de la familia principal, o declarar la limitacion. Mi preferencia es
**declarar la limitacion**, porque sacar un horizonte despues de ver que es el
que falla es exactamente la clase de decision que un pre-registro busca
impedir, y porque el exceso es modesto (0,16 contra 0,05 en una celda de ocho,
con 50 mercados detras).

### Pendientes al cerrar esta parte

- **Decidir la celda de reingreso a 120 minutos**: sacarla de la familia o
  declarar la limitacion.
- **Confirmar `MIN_DIAS_TRATADOS = 15`** tras esta corrida (la evidencia lo
  respalda: el minimo observado de dias tratados fue 18).
- `CORRECCION_PRINCIPAL` se decide en el punto E por potencia.
- Sigue todo lo anterior, ahora con 19 parametros `# POR DECIDIR`.

---

## Punto D (tercera parte) — Ultimo intento de calibracion, y lo que se encontro

- **Fecha**: 2026-09-23
- **Commit**: pendiente (se completa en el commit siguiente)
- **Tests**: `pytest` -> 154 pasan, 0 fallan, 0 avisos.

### Que se probo, con la regla escrita ANTES de mirar el resultado

Hipotesis del grupo: un evento no es un minuto cualquiera. Un reingreso ocurre
justo despues de una expansion, asi que llega con la volatilidad RECIENTE alta
por construccion. La nula emparejaba por volatilidad de los ultimos 20 dias,
pero no por la de los ultimos minutos.

Dos cambios, juntos y de una sola vez:

1. **Volatilidad reciente como quinta variable de emparejamiento**: la
   volatilidad realizada de los 60 minutos anteriores al instante, medida solo
   con barras ya cerradas, partida en tercios. Vive en
   `resultados.volatilidad_reciente`.
2. **Estadistico de la familia principal estudentizado**: el promedio dividido
   por su error estandar agrupado por fecha de Londres, calculado con la misma
   funcion (`inferencia.media_agrupada`) en los datos reales y en cada
   repeticion de la nula, igual que ya se hacia en H4.

**Los estratos aguantaron**: con franja x dia x decil x tercio x volatilidad
reciente quedan 1.462 estratos con datos, la mediana tiene 433 minutos
candidatos, el percentil 10 tiene 95 y solo el 0,8% de los eventos cae en un
estrato con menos de 100. No hizo falta bajar los deciles a quintiles.

### Resultado: NO funciono

| | antes | ahora |
|---|---:|---:|
| familia principal, tasa bruta | 0,0675 | **0,085** |
| familia principal, IC 95% | [0,047, 0,096] | **[0,061, 0,116]** |
| familia principal, p-valor medio | 0,4625 | 0,4571 |
| **celda reingreso a 120 minutos** | 0,16 | **0,14** |
| familia moderadores, tasa bruta | 0,0483 | 0,0483 |

La celda de 120 minutos bajo de 0,16 a 0,14, que con 50 mercados es ruido, y la
familia entera empeoro: su intervalo ya **no contiene el 5%**. La hipotesis
queda descartada igual que la anterior.

(La familia de moderadores no se movio ni un decimal, como debe ser: sale de
regresiones y no toca la nula emparejada.)

### Se aplica la regla: el horizonte de 120 minutos pasa a DESCRIPTIVO

Segun lo acordado de antemano, el horizonte de 120 minutos **sale de
`FAMILIA_PRINCIPAL`**, que queda con 6 pruebas (2 tipos x 3 horizontes). En
config eso es `HORIZONTES_DESCRIPTIVOS = [120]`. El horizonte se sigue
calculando y se sigue reportando en todas las tablas, y sigue dentro de
`FAMILIA_MODERADORES` y de `FAMILIA_H4`, que si estan calibradas. Lo que ya no
hace es confirmar nada.

La frase para el pre-registro, tal cual: *en nuestro control negativo esa celda
rechaza entre el 14% y el 16% de las veces bajo la hipotesis nula, asi que no
la usamos para confirmar. No la escondemos: la reportamos con su medicion.*

### PERO: sacar el 120 no arregla la familia

Volviendo a leer los CSV ya guardados, sin correr nada nuevo:

| configuracion | familia completa (8) | sin el horizonte 120 (6) |
|---|---:|---:|
| antes, tasa bruta | 0,0675 | 0,0633 |
| antes, mercados con algun rechazo | 0,080 | 0,100 |
| ahora, tasa bruta | 0,0850 | 0,0767 |
| ahora, mercados con algun rechazo | 0,120 | 0,100 |

El exceso **no estaba concentrado en esa celda**: esta repartido por toda la
familia. Sacar el peor horizonte baja la tasa bruta uno o dos puntos y deja la
tasa por familia en 0,10. Asi que la limitacion que hay que declarar no es
"una celda mala" sino "la prueba principal corre al 6-8% en vez del 5%".

### El hallazgo que importa de verdad

Mirando el efecto medio en mercados SIN NINGUN PATRON, celda por celda:

| tipo | 30 min | 60 min | 120 min | fin de franja |
|---|---:|---:|---:|---:|
| sostenida | **+0,0049** | **+0,0057** | **+0,0074** | **+0,0084** |
| reingreso | −0,0002 | **−0,0027** | **−0,0063** | **−0,0029** |

**Las ocho celdas tienen el signo que predicen H1 y H2.** Las sostenidas
continuan y los reingresos se devuelven, en un mercado donde por construccion
no hay nada que continuar ni que devolver. Los errores de Monte Carlo son de
0,003 a 0,005, asi que cada celda por separado esta al borde; pero ocho de ocho
con el signo esperado no es casualidad.

O sea: **la propia definicion de los eventos produce un sesgo pequeno en la
direccion de las hipotesis**. La nula emparejada absorbe la mayor parte, pero no
toda, y ese resto es lo que hace que los p-valores se inclinen (promedio 0,457
en vez de 0,50) y que la tasa de rechazo quede en 6-8%.

**Consecuencia practica, y es la parte util**: un efecto real tiene que superar
ese artefacto para ser creible. El artefacto mide entre 0,005 y 0,008 unidades
de retorno normalizado. Eso pone un piso al tamano minimo que tiene sentido
declarar como hallazgo, y hay que decirlo en el pre-registro.

**Aviso para el punto E**: `TAMANOS_EFECTO` empieza en 0,02, que es solo dos o
tres veces el artefacto. La curva de potencia en ese extremo va a estar medida
sobre un suelo que no es cero, y conviene leerla con esa advertencia o agregar
un tamano intermedio.

No se busco el mecanismo exacto del sesgo: la regla acordada decia que este era
el ultimo intento sobre calibracion. Queda como pregunta abierta y declarada.

### Decisiones de esta parte

1. **`HORIZONTES_DESCRIPTIVOS = [120]`**, por la regla escrita de antemano.
2. **Se mantienen los dos cambios probados** aunque no mejoraran la
   calibracion, por las mismas razones que el tercio: emparejar por volatilidad
   reciente es a priori correcto (un evento llega despues de una expansion) y
   los estratos siguen holgados; y estudentizar deja el estadistico de H1 y H2
   consistente con el de H4 y con lo que recomiendan MacKinnon y Webb para
   inferencia por aleatorizacion. **Ninguno de los dos compra calibracion**, y
   los dos son reversibles: `PRINCIPAL_ESTUDENTIZADO = False` y quitar un
   termino de la clave. Si el grupo prefiere la version mas simple, se revierte.
3. No se probaron mas variantes. Fin de los intentos de calibracion.

### Pendientes al cerrar el punto D

- Declarar en el pre-registro la limitacion de la familia principal (6-8% en
  vez de 5%) y el piso de 0,005 a 0,008 en unidades de retorno normalizado.
- `CORRECCION_PRINCIPAL` se decide en el punto E por potencia.
- Revisar si conviene agregar un tamano de efecto intermedio en el punto E.
- Sigue todo lo anterior, ahora con 21 parametros `# POR DECIDIR`.
