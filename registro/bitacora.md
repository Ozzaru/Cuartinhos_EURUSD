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
