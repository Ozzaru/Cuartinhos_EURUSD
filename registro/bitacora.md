# Bitacora de trabajo

Registro por punto de control. Con leer `README.md` y este archivo se puede
retomar el trabajo en una sesion nueva sin mas contexto.

**Convencion de hashes**: el hash anotado es el del commit que cierra el punto
de control. Como el hash solo existe despues de commitear, cada entrada se
completa con un segundo commit pequeno (`bitacora: hash del punto X`).

**Regla de git** (actualizada en el punto E): existe el remoto `origin` en
GitHub. Se sube con `git push origin main` al cerrar cada parte aprobada por el
grupo, despues del commit con el hash. Nunca se suben datos, resultados ni PDFs
(`datos/`, `resultados/` y los PDF de `docs/papers/` estan ignorados por git).
Nunca se usa `--force`.

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
- **Commit**: `1751489` (`punto D (3a parte): ultimo intento de calibracion y el sesgo de fondo`)
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
- Sigue todo lo anterior, ahora con 21 parametros `# POR DECIDIR`
  (`NULA_GRUPOS_VOL_RECIENTE` y `VENTANA_VOL_RECIENTE_MIN` son los nuevos).

---

## TRASPASO — cierre de la sesion del 2026-09-23

Esta seccion es el punto de entrada para quien abra el punto E. Todo lo de
arriba es el detalle; esto es lo que no se puede perder en el camino.

**Estado**: puntos 0, A, B, C y D cerrados. 154 tests pasan, 0 fallan, 0
avisos. Rama `main` limpia, sin remoto, nada subido a internet. 21 parametros
marcados `# POR DECIDIR`. **El punto E no esta empezado.**

### 1. El piso: los eventos traen un sesgo propio, de 0,005 a 0,008

> **CORREGIDO en el punto E.** Con 200 mercados de 3 anos (los 50 del punto D
> mas 150 nuevos) el piso NO aparece. Las ocho celdas quedan en cero dentro de
> su error: sostenida -0,0003 / -0,0019 / -0,0013 / +0,0034 y reingreso
> -0,0011 / -0,0006 / -0,0004 / +0,0001 (30, 60, 120 y fin de franja), con
> errores de Monte Carlo de 0,0015 a 0,0024. Prueba conjunta de Hotelling de
> las 8 celdas contra cero: p = 0,45. Promedio en la direccion de H1/H2:
> +0,0003 +- 0,0011; en los 50 mercados del punto D daba +0,0049 +- 0,0019 y en
> los 150 nuevos da -0,0013 +- 0,0013. El "ocho de ocho" fue de esos 50
> mercados, y las celdas de un mismo tipo estan correlacionadas entre 0,4 y
> 0,7, asi que nunca fueron ocho pruebas independientes. Intervalos al 95% por
> celda: hasta unas +-0,005 (hasta +0,008 en sostenida a fin de franja). Lo que
> sigue en este punto es lo que se creia al cerrar el punto D; el detalle esta
> en "Punto E (primera parte)".

En 50 mercados simulados **sin ningun patron** — camino aleatorio, donde por
construccion no hay nada que continuar ni nada que devolverse — el efecto medio
celda por celda es:

| tipo | 30 min | 60 min | 120 min | fin de franja |
|---|---:|---:|---:|---:|
| sostenida | **+0,0049** | **+0,0057** | **+0,0074** | **+0,0084** |
| reingreso | −0,0002 | **−0,0027** | **−0,0063** | **−0,0029** |

**Las ocho celdas tienen el signo que predicen H1 y H2.** Con errores de Monte
Carlo de 0,003 a 0,005, cada celda por separado esta al borde; el patron
completo no lo esta. La conclusion es que **la definicion misma de los eventos
produce un sesgo pequeno en la direccion de las hipotesis**: la nula emparejada
absorbe la mayor parte, y el resto es lo que inclina los p-valores (promedio
0,457 en vez de 0,50) y lo que deja la tasa de rechazo en 6-8%.

**Consecuencia que hay que arrastrar a todo lo que venga**: un efecto medido
por debajo de **0,008 unidades de retorno normalizado no se distingue del
artefacto**. Ese es el piso de lo que se puede declarar como hallazgo. Va al
pre-registro (punto F) y hay que leer con el a la vista la curva de potencia
del punto E, porque `TAMANOS_EFECTO` empieza en 0,02: solo dos o tres veces el
artefacto.

No se busco el mecanismo exacto del sesgo. Es una pregunta abierta y declarada,
no un cabo suelto olvidado: la regla acordada de antemano cerro los intentos de
calibracion despues del segundo fracaso.

### 2. El horizonte de 120 minutos es descriptivo, y la familia corre al 6-8%

> **CORREGIDO en el punto E.** Con 200 mercados el piso no aparece (nota del
> punto 1), asi que el exceso de la familia principal no se puede atribuir a un
> sesgo demostrado de los eventos. La frase del 6-8% queda reemplazada por:
> **"tasa por prueba 7,7% (IC95 por mercados 4,3%-11,7%) con alfa nominal 5%; no
> se demuestra exceso, pero tampoco se descarta uno de hasta ~12%"**. El
> intervalo remuestrea mercados, porque las pruebas de un mismo mercado no son
> independientes. El horizonte de 120 minutos sigue descriptivo.

`HORIZONTES_DESCRIPTIVOS = [120]`. El horizonte salio de `FAMILIA_PRINCIPAL`,
que quedo con 6 pruebas, porque en el control negativo esa celda rechaza entre
el 14% y el 16% bajo la nula. Se sigue calculando, se sigue reportando en todas
las tablas y sigue dentro de `FAMILIA_MODERADORES` y `FAMILIA_H4`, que si estan
calibradas. Lo unico que ya no hace es confirmar.

**Y esto es lo importante: sacarlo NO arregla la familia.** Sin el horizonte de
120 la tasa bruta baja a 0,0767 y la tasa por familia se queda en 0,10, igual
que con el. El exceso esta repartido, no concentrado en una celda. Por lo
tanto **la limitacion que se declara en el pre-registro no es "una celda mala"
sino: "tasa por prueba 7,7% (IC95 por mercados 4,3%-11,7%) con alfa nominal
5%; no se demuestra exceso, pero tampoco se descarta uno de hasta ~12%"**
(frase corregida en el punto E). Quien escriba el punto F no debe suavizar esa
frase.

### 3. Se mantienen dos cambios que no mejoraron nada medible

El emparejamiento por **volatilidad reciente** (quinta variable de la clave) y
el **estadistico estudentizado** de la familia principal
(`PRINCIPAL_ESTUDENTIZADO = True`) se conservan aunque no compraron
calibracion:

- son correctos **a priori**, no por resultado: un evento llega justo despues
  de una expansion, asi que su volatilidad reciente es alta por construccion, y
  estudentizar deja H1 y H2 consistentes con H4 y con MacKinnon y Webb (2020);
- los estratos siguen holgados: 1.462 con datos, mediana de 433 candidatos,
  solo 0,8% de eventos bajo 100;
- **ninguno de los dos se adopto para mejorar un numero**, que es justo lo que
  un pre-registro busca impedir.

Los dos son reversibles en una linea (`PRINCIPAL_ESTUDENTIZADO = False` y
quitar un termino de `nula._clave`). Si el grupo prefiere la version simple, se
revierte y se vuelve a correr el control negativo; la decision sigue abierta.

### 4. Pendientes para el punto E

> Nota: el mensaje que pidio este traspaso anunciaba una lista de pendientes
> "escritos abajo" que no llego. Lo que sigue esta reconstruido del encargo
> original y de lo acordado en los puntos A a D. **El grupo la reemplaza o la
> completa antes de empezar.**

Lo que el punto E tiene que producir:

1. `simulacion/inyeccion.py`: efecto conocido inyectado sobre el mercado
   simulado, en unidades de retorno normalizado.
2. `experimentos/control_positivo.py`: curva de potencia sobre
   `TAMANOS_EFECTO` x `ANIOS_POTENCIA`, con sesgo del estimador, efecto minimo
   detectable al 80% de potencia y su grafico PNG.
3. `motor/auditoria.py` y `experimentos/auditoria_causal.py`: auditoria de
   truncamiento con 40 cortes al azar, incluyendo cortes **dentro** de una
   franja. Con una version deliberadamente filtrada del motor que viva **solo
   en el test** y que la auditoria tenga que DETECTAR; si no la detecta, la
   auditoria no sirve.

Decisiones que el punto E tiene que cerrar:

4. **`CORRECCION_PRINCIPAL`** (Holm contra Romano-Wolf): se decide comparando
   **potencia** sobre la misma curva, no tamano. Holm es valido bajo
   dependencia arbitraria; Romano-Wolf aprovecha la correlacion entre pruebas y
   deberia dar mas potencia. Se reportan las dos igual
   (`REPORTAR_AMBAS_CORRECCIONES = True`).
5. **Tamano de efecto intermedio**: con el piso de 0,005-0,008 medido, el salto
   de 0 a 0,02 deja sin cubrir justo la zona donde el artefacto y el efecto
   real se confunden. Evaluar agregar 0,01 (y quiza 0,035) a
   `TAMANOS_EFECTO`.
6. **Confirmar `MIN_DIAS_TRATADOS = 15`**: la evidencia del punto D lo respalda
   (el minimo observado de dias tratados fue 18).
7. **Decidir si se revierten los dos cambios del punto 3** de arriba.

Reglas de procedimiento que siguen vigentes en el punto E:

8. **Piloto primero**, midiendo tiempo **y** memoria, con los procesos
   limitados por `experimentos/recursos.py` a ~70% de la RAM disponible.
   **Detenerse y esperar OK** antes de la corrida completa.
9. Si una corrida amenaza con pasar de una hora: reducir repeticiones o
   duraciones, decirlo en el informe con su error de Monte Carlo, y seguir. **No
   se sacrifican los controles, se sacrifica tamano de muestra.**
10. Si un control falla, **no se ajustan umbrales ni metodos para que pase**: se
    explica la causa probable y se proponen opciones.

### Como retomar

```
cd C:\WorkSpace\10_Code\Cuartinhos_EURUSD
.venv\Scripts\activate
pytest                                            154 pasan, 0 avisos
python -m experimentos.control_negativo --piloto  tiempo y memoria
python -m experimentos.control_negativo           corrida completa (~18 min)
python -m experimentos.control_negativo --solo-reporte   rehace el informe
```

Los resultados guardados del punto D estan en `resultados/` (ignorada por git):
los CSV permiten rehacer cualquier tabla de arriba sin volver a correr nada.

**Lo que no cambia**: no se descargan ni se miran datos reales; no se toca nada
dentro de `Cuartinhos_Goty` ni se importa desde ahi; `docs/papers/` es del
grupo y solo se lee si se pide; ~~git es local y no se sube nada~~
(ACTUALIZADO en el punto E: ver la regla de git al inicio de la bitacora).

---

## Punto E (primera parte) — Auditoria, piso, unidades y regla de alfa

- **Fecha**: 2026-09-23
- **Commit**: `6950074` (`punto E (1a parte): auditoria, piso, unidades y regla de alfa`)
- **Tests**: `pytest` -> 197 pasan, 0 fallan, 0 avisos.
- **Estado**: hechos la regla del alfa, la auditoria causal, el piso, las
  unidades y el piloto del diseno de inyeccion aprobado originalmente. El grupo
  decidio como medir la curva (ver "Decisiones del grupo al cerrar esta
  parte"). **La curva de potencia NO se corrio todavia**: queda para la segunda
  parte.

### La lista de pendientes que vale

La seccion 4 del TRASPASO la reconstruyo la sesion anterior porque la lista
original no llego. **La reemplaza la lista del mensaje del grupo que abrio este
punto**: (1) agregar 0,01 y 0,03 a los tamanos; (2) definir por escrito que se
inyecta y que es potencia; (3) medir el piso con precision, sin la nula; (4)
traducir las unidades a pips; (5) Holm contra Romano-Wolf y el alfa, con regla
escrita antes de la curva; (6) auditoria de causalidad con una fuga de prueba
que tiene que detectar; (7) piloto de tiempo y memoria antes de la corrida
larga. Queda constancia aqui, como pidio el grupo.

### Decisiones fijadas ANTES de ver la curva, con su razon

1. **`CORRECCION_PRINCIPAL = "holm"`, fijada sin mirar la curva.** Tal como
   estan implementadas, Holm y Romano-Wolf no son dos correcciones del mismo
   test sino dos tests distintos: Holm corrige los p-valores de la nula
   emparejada, a una cola; Romano-Wolf prueba el promedio contra cero con el t
   de la regresion, a dos colas y sin la nula (su bootstrap de dias necesita un
   estadistico comun y no puede usar los p de la nula). Comparar su potencia
   responderia "que test usar", no "que correccion usar", y el test que va al
   pre-registro ya estaba decidido: la nula emparejada. Holm vale con cualquier
   dependencia entre pruebas, asi que la correlacion entre horizontes no lo
   invalida. Romano-Wolf se sigue reportando como prueba **secundaria**, y en
   toda tabla se rotula como lo que es (`inferencia.ETIQUETA_ROMANO_WOLF`). La
   regla 8(b) del plan (elegir la correccion por potencia) queda eliminada; en
   la curva las cuatro combinaciones se reportan solo como descripcion. Sale un
   `# POR DECIDIR` de config.
2. **`ALFA_PRINCIPAL` sale de una regla escrita antes de la curva**
   (`python -m experimentos.control_negativo --alfa-principal`):
   - se calcula la tasa POR PRUEBA de la familia principal (6 pruebas, sin el
     120) con los CSV del punto D, con su intervalo al 95% remuestreando
     MERCADOS, para alfa 0,05 y 0,025;
   - si con 0,05 el intervalo queda entero por encima de 0,05 (exceso
     demostrado) y con 0,025 no se demuestra exceso, `ALFA_PRINCIPAL = 0,025`;
     si con 0,05 el intervalo contiene 0,05, se queda en 0,05; cualquier otro
     caso no esta previsto y se consulta.

   | alfa | tasa por prueba | IC95 por mercados | exceso demostrado | Wilson (referencia) |
   |---|---:|---|---|---|
   | 0,05 | 0,0767 | [0,0433; 0,1167] | no | [0,0516; 0,1124] |
   | 0,025 | 0,0400 | [0,0200; 0,0600] | no | [0,0230; 0,0686] |

   **Resultado: `ALFA_PRINCIPAL = 0,05`.** Solo aplica a la familia principal;
   moderadores y H4 siguen con `ALFA = 0,05`, porque estan calibradas. Wilson,
   que trata como independientes pruebas que no lo son, habria mostrado un
   exceso (borde inferior 0,0516); por eso la regla remuestrea mercados. La
   regla anterior del plan (8(a)) se descarto porque premiaba la imprecision:
   0,05 pasaba por tener un intervalo ancho y 0,025 fallaba aunque su tasa
   medida era menor. La curva no reabre esta decision.
3. **Tamanos**: `TAMANOS_EFECTO = [0, 0,01, 0,02, 0,03, 0,05, 0,10, 0,20]`. No
   se agregan tamanos mayores por los costos: la curva mide deteccion del
   efecto BRUTO. Para leerla contra un costo c, la potencia de un test neto en
   delta se aproxima por la potencia bruta en delta - c (el error estandar casi
   no depende de delta); es una aproximacion y se declara como tal.
4. **Que se inyecta y que es potencia** (aprobado por el grupo): solo en
   sostenida (+delta, continuacion) y reingreso (-delta, reversion), en la
   direccion de la ruptura; al log-precio en t + tau se suma
   direccion * signo * delta * sigma_ref * raiz(tau) hasta el fin de la franja
   y despues queda fijo, asi que el retorno normalizado sube delta en todo
   horizonte dentro de la franja (y delta * raiz(T/h) si el horizonte cruza el
   fin, POR CONSTRUCCION). Se desplazan todas las columnas de precio de cada
   barra y hay tests de que las barras siguen coherentes. Potencia por celda =
   proporcion de mercados que rechazan con el signo correcto; por familia =
   proporcion con al menos un rechazo correcto. Eje de la curva: delta nominal,
   con el realizado al lado. Semillas comunes para todos los delta.
5. **No se reabren**: el emparejamiento por volatilidad reciente,
   `PRINCIPAL_ESTUDENTIZADO = True` (la curva se mide con el metodo que ira al
   pre-registro) y **`MIN_DIAS_TRATADOS = 15`, que queda confirmado** (el minimo
   observado en el punto D fue 18).

### Auditoria causal: pasa, y atrapa una fuga de un minuto

`motor/auditoria.py` y `experimentos/auditoria_causal.py`. En cada corte se
comparan los eventos con t_evento <= corte de la muestra completa contra la
muestra truncada y contra la muestra con el futuro reemplazado (por el de otro
mercado simulado, empalmado en el corte). Se compara TODO lo que el motor
declara en t (tipo, direccion, instantes, extremo, precio del evento,
sigma_ref, moderadores, volatilidad reciente) con **igualdad exacta, sin
tolerancia**.

Los 40 cortes (config): **20 en el instante exacto de un evento sorteado**
(7 rupturas, 7 sostenidas, 6 reingresos), 10 en la mitad de una franja con
eventos y 10 al azar. La razon, que puso el grupo: `precio_en` solo se usa para
fechar la sostenida, asi que una fuga de t + 1 minuto solo altera algo si el
corte cae justo en el instante de una sostenida; con cortes al azar eso pasa en
~3% de los casos.

- **Motor real, 1 ano simulado: PASA 40 de 40 cortes** (20 segundos).
- **Motor con fuga** (solo en `tests/test_auditoria.py`: `precio_en` lee la
  barra que cierra en t + 1, via monkeypatch), con el MISMO generador de cortes
  y semilla fija: **NO PASA**. En la corrida de prueba la detectan los 7 cortes
  anclados en sostenidas, en las dos variantes (truncada: la sostenida
  desaparece; reemplazada: cambia su precio), y **ninguno de los 20 cortes al
  azar o de mitad de franja la ve**. Sin los cortes anclados, la auditoria no
  habria servido.

Declarado: no se auditan los grupos de emparejamiento de la nula (deciles,
tercios de volatilidad reciente, tercio de la franja). Se calculan con la
muestra completa por diseno; el tercio usa el fin real de la franja, que
depende de hasta donde llegan los datos. Sus insumos que existen en t si se
auditan. El calendario de anuncios se entrega completo porque tiene fecha
publicada de antemano.

### El piso: con 200 mercados NO hay sesgo (corrige el TRASPASO)

`python -m experimentos.control_positivo --piso`: 200 mercados de 3 anos sin
ningun patron, deteccion y retornos sin la nula (1,1 minutos). Los primeros 50
tienen las mismas semillas que el punto D.

| tipo | horizonte | piso (200 mercados) | error MC | los 50 del punto D |
|---|---|---:|---:|---:|
| sostenida | 30 | -0,0003 | 0,0024 | +0,0045 |
| sostenida | 60 | -0,0019 | 0,0024 | +0,0054 |
| sostenida | 120 | -0,0013 | 0,0023 | +0,0071 |
| sostenida | fin_franja | +0,0034 | 0,0024 | +0,0088 |
| reingreso | 30 | -0,0011 | 0,0017 | -0,0001 |
| reingreso | 60 | -0,0006 | 0,0015 | -0,0029 |
| reingreso | 120 | -0,0004 | 0,0018 | -0,0067 |
| reingreso | fin_franja | +0,0001 | 0,0017 | -0,0034 |

- Sobre los 50 mercados del punto D, el calculo sin la nula **reproduce**
  aquella tabla (+0,0049, +0,0057, +0,0074, +0,0084 / -0,0002, -0,0027,
  -0,0063, -0,0029); la diferencia es que aqui entran tambien los pocos eventos
  sin pareja en la nula.
- Con 200 mercados las ocho celdas quedan en cero dentro de su error, y los
  signos dejan de coincidir con H1 y H2. Prueba conjunta de Hotelling de las
  8 celdas contra cero: **p = 0,45**. Promedio de las 8 celdas en la direccion
  de H1/H2: **+0,0003 +- 0,0011** (error estandar); en los 50 del punto D daba
  +0,0049 +- 0,0019 y en los 150 nuevos da -0,0013 +- 0,0013.
- Por que el "ocho de ocho" del punto D no era evidencia: las celdas de un
  mismo tipo estan correlacionadas entre 0,4 y 0,7 (son los mismos eventos a
  distintos horizontes), asi que no eran ocho monedas independientes sino
  poco mas de dos.

**Consecuencia para el pre-registro**: la frase "un efecto por debajo de 0,008
no se distingue del artefacto" del TRASPASO ya no tiene respaldo como
artefacto demostrado. Lo que se puede decir con 200 mercados: no se detecta
ningun sesgo propio de los eventos (Hotelling p = 0,45); los intervalos al 95%
por celda llegan hasta unas +-0,005 unidades, y hasta +0,008 en sostenida a fin
de franja (la celda con el punto mas alto, +0,0034); el promedio en la
direccion de H1/H2 queda en [-0,002; +0,002]. Queda tambien sin respaldo la
explicacion "el sesgo de los eventos es lo que inclina los p-valores": la tasa
de rechazo de la familia principal cae dentro de lo que el azar permite
(intervalo por mercados [0,043; 0,117] con alfa 0,05). El grupo acepto la
correccion y reemplazo la frase del 6-8% por: **"tasa por prueba 7,7% (IC95
por mercados 4,3%-11,7%) con alfa nominal 5%; no se demuestra exceso, pero
tampoco se descarta uno de hasta ~12%"**. El TRASPASO no se borro: sus puntos 1
y 2 llevan al inicio una nota visible "CORREGIDO en el punto E" con estos
numeros.

### Unidades: cuantos pips vale una unidad de retorno normalizado

**Es un orden de magnitud**: el factor es sigma_ref * raiz(h) * precio / pip, y
sigma_ref sale aqui de `VOL_ANUAL_SIMULACION`, un parametro de simulacion. La
traduccion definitiva se hara evento por evento con el sigma_ref de los datos
reales. Medianas sobre sostenidas y reingresos (20 mercados por volatilidad;
por franja y cuartiles en `resultados/control_positivo_piso.md`):

| vol anual | 30 min | 60 min | 120 min | fin de franja |
|---|---:|---:|---:|---:|
| 0,05 | 4,1 pips | 5,8 | 8,2 | 11,6 |
| 0,07 | 5,7 pips | 8,0 | 11,4 | 16,3 |
| 0,10 | 8,1 pips | 11,4 | 16,2 | 23,5 |

Con 7%, un costo de ida y vuelta de 0,5 / 1 / 2 pips vale 0,09 / 0,18 / 0,35
unidades a 30 minutos y 0,06 / 0,12 / 0,25 a 60 minutos. **Siete
combinaciones de costo, horizonte y volatilidad quedan por encima del mayor
tamano de la curva (0,20)**, entre ellas 2 pips a 30 y 60 minutos con 7%. Por
decision del grupo no se agregan tamanos: la curva se lee contra el costo con
la aproximacion de la decision 3.

### Inyeccion: lo que aparecio al programarla (decidido, ver mas abajo)

Dos problemas, medidos antes de la curva, que hacen que el delta nominal no
sea el efecto que llega a las celdas:

1. **La retroalimentacion en dos pasadas desalinea los eventos.** El plan
   aprobado detecta los eventos en el mercado limpio, inyecta y vuelve a correr
   todo. Pero la deriva mueve los extremos de cada franja, y en la franja
   siguiente el motor detecta OTROS eventos: con delta = 0,2, en un ano, solo
   el 51% de los reingresos y el 69% de las sostenidas del mercado inyectado
   coinciden con un evento del limpio. Los nuevos no traen efecto, y parte de
   la deriva queda pegada a eventos que ya no existen. En el plan se dijo que
   esto era "lo que pasaria con un efecto real"; no lo es: con un efecto real,
   todo evento detectado lo trae.
2. **Sostenida y reingreso se pisan.** El 71-73% de las sostenidas tiene un
   reingreso POSTERIOR en la misma franja, y la reversion de ese reingreso
   anula parte de la continuacion (y al reves). Aun con la inyeccion hecha
   autoconsistente, el delta realizado por evento queda en 0,71-0,77 delta a 30
   minutos para las sostenidas, 0,37-0,46 delta a fin de franja; y 0,76-0,87
   delta para los reingresos.

La inyeccion autoconsistente (iterar inyectar -> detectar hasta que los eventos
que se inyectan son los que se detectan) converge: por causalidad, el primer
desacuerdo avanza en cada vuelta. Se midio en un prototipo desechable: 4
iteraciones con delta = 0,01, 7 con 0,05 y 14-15 con 0,20; con 13 anos, 30 y 66
segundos por delta. Las opciones que se presentaron y la decision del grupo
estan mas abajo.

### Piloto (del diseno aprobado, dos pasadas)

`python -m experimentos.control_positivo --piloto`: 3 mercados por duracion,
cada uno con los 7 tamanos, de a uno y cada uno en un proceso nuevo (asi la
memoria medida es la de un proceso entero). Nula y Romano-Wolf con 500
repeticiones.

| duracion | segundos por mercado (7 delta) | pico de memoria | procesos que caben (70% de ~5 GB libres) | 30 mercados |
|---|---:|---:|---:|---:|
| 4 anos | 42 | 0,64-0,87 GB | 4 | 5 min |
| 13 anos | 119-129 | 2,08-2,29 GB | 1 | 61 min |

**Total estimado: 67 minutos**, por encima de la hora. El cuello es la memoria
libre del equipo en ese momento (unos 5 GB de 16,8): con 13 anos cabe un solo
proceso.

Primera mirada (3 mercados, solo para revisar la maquina): la mediana del p de
Holm baja con delta como debe (4 anos: 1, 1, 0,79, 0,45, 0,23, 0,015, 0,012;
13 anos: 0,96 ... 0,012). Pero confirma la dilucion del diseno aprobado: con
delta = 0,10 el delta realizado por celda va de 0,07 a 0,09 en reingresos y de
0,02 a 0,06 en sostenidas; con delta = 0,05 solo el 75% de los reingresos y el
84% de las sostenidas del mercado inyectado recibieron el efecto. El cambio de
sigma_ref es despreciable (menos de 0,5%) y la cantidad de eventos cambia menos
de 2,5%.

### Opciones que se presentaron para la inyeccion

- **A. Dejar lo aprobado (dos pasadas).** El eje nominal queda lejos del efecto
  que llega a las celdas, y el efecto minimo detectable sobre ese eje no se
  puede comparar con la referencia de 0,07-0,11. 67 minutos: habria que bajar
  13 anos a 25 mercados (~56 min; error de Monte Carlo de una potencia de 0,5:
  0,100 en vez de 0,091).
- **B. Inyeccion de precio autoconsistente.** Todo evento detectado trae su
  efecto; queda la superposicion (sostenidas 0,37-0,77 delta, reingresos
  0,76-0,87 delta). ~98 s por mercado de 4 anos y ~300 s por mercado de 13:
  unas 2,7 horas con un proceso. Solo cabe con recortes grandes o con mas
  memoria libre.
- **C. Como B, una hipotesis por corrida** (solo sostenidas, solo reingresos):
  delta realizado ~ delta salvo los horizontes que cruzan el fin de la franja;
  el doble de B.
- **D. Inyectar en el resultado**: el mercado queda limpio y a cada evento se
  le suma exactamente signo * delta * raiz(min(h, T) / h) en el retorno
  normalizado de cada celda (lo mismo que daria la deriva de precio de un
  evento aislado). Delta exacto por celda por construccion, sin
  retroalimentacion ni superposicion; responde directo "si el efecto en la
  celda es delta, con que probabilidad se detecta", comparable con la
  referencia. ~23 s por mercado de 4 anos y ~66 s por mercado de 13: unos 36
  minutos en total, sin recortes. Pierde lo que el mecanismo de precio le hace
  a las celdas.

**Recomendacion**: D para la curva, y B como control descriptivo con
delta = 0,05 y 0,10, 4 anos, 30 mercados (~5 minutos mas): mide cuanto de un
efecto de precio llega a cada celda cuando las dos hipotesis actuan a la vez.
Total ~41 minutos, dentro de la hora.

**Aparte, para la discusion del pre-registro** (no es del control positivo):
el 71-73% de las sostenidas tiene un reingreso posterior en la misma franja, o
sea que H1 y H2 miden trayectorias de precio que se pisan. Si los dos efectos
existieran, se anularian en parte en las celdas medidas, sobre todo en
sostenida a 120 minutos y a fin de franja. Es una pregunta sobre como se define
H1, no sobre la curva; no se propone ningun cambio.

### Decisiones del grupo al cerrar esta parte

1. **Inyeccion: D para la curva y B como control descriptivo.** La curva se
   mide sumando delta al retorno normalizado de cada evento de la celda, sobre
   el mercado limpio. Razon del grupo: D mide la potencia en la unidad en que
   estan escritas las hipotesis, que es el procedimiento habitual en estudios
   de eventos (MacKinlay, 1997, seccion de potencia). B (inyeccion de precio
   autoconsistente, con delta = 0,05 y 0,10 y 4 anos) documenta cuanto de un
   efecto en precios llega a las celdas; se reporta y **no decide nada**.
2. **Queda anotado para el pre-registro (punto F)**: el 71-73% de las
   sostenidas reingresa despues en la misma franja, asi que H1 y H2 miden
   trayectorias que se pisan. Hoy no se cambia nada.
3. **Se acepta la correccion del piso.** El TRASPASO no se borra: sus puntos 1
   y 2 llevan al inicio una nota "CORREGIDO en el punto E" con los numeros de
   los 200 mercados, y la frase del 6-8% se reemplaza por: "tasa por prueba
   7,7% (IC95 por mercados 4,3%-11,7%) con alfa nominal 5%; no se demuestra
   exceso, pero tampoco se descarta uno de hasta ~12%".
4. **Regla de git actualizada** (al inicio de la bitacora): existe el remoto
   `origin` en GitHub; se sube al cerrar cada parte aprobada; nunca se suben
   datos, resultados ni PDFs; nunca se usa `--force`.
5. Esta parte se cierra sin correr nada mas: la curva va en la segunda parte.

### Romano-Wolf con 6 pruebas, exacto (solo descripcion)

El plan daba una cota (los p de Romano-Wolf del punto D eran de la familia de 8
pruebas). Recalculado con un script desechable sobre los mismos 50 mercados y
los mismos remuestreos (33 segundos): **3 de 50 mercados (0,06) con alfa 0,05 y
2 de 50 (0,04) con 0,025**, todos con el signo de H1/H2; la cota era 2 y 1.
Como se esperaba, con 6 pruebas ningun p subio. Ya no decide nada: Holm quedo
fijado.

### Parametros nuevos en config

`ALFA_ESTRICTO`, `ALFA_PRINCIPAL`, `REMUESTREOS_IC_MERCADOS`, `ALFAS_POTENCIA`,
`POTENCIA_OBJETIVO`, `MERCADOS_PISO`, `ANIOS_PISO`, `MERCADOS_UNIDADES`,
`VOLS_TRADUCCION` (# PARAMETRO DE SIMULACION), `COSTOS_IDA_VUELTA_PIPS`
(# POR DECIDIR), `CORTES_AUDITORIA_EVENTO`, `CORTES_AUDITORIA_MITAD_FRANJA`,
`CORTES_AUDITORIA_AZAR`, `ANIOS_AUDITORIA`. `CORRECCION_PRINCIPAL` deja de
estar POR DECIDIR y `COSTOS_IDA_VUELTA_PIPS` entra: siguen **21** parametros
`# POR DECIDIR`.

### TRASPASO corto (para abrir la segunda parte del punto E)

**Estado**: primera parte cerrada con commit y subida a `origin`. 197 tests, 0
fallos, 0 avisos. 21 parametros `# POR DECIDIR`. La curva de potencia **no se
corrio**.

**Ojo con el codigo**: `experimentos/control_positivo.py` todavia programa la
curva con la inyeccion en precios EN DOS PASADAS (el diseno A, descartado). Hay
que reemplazarla antes de correr nada.

**Siguiente paso, en este orden:**

1. Programar el diseno D: sobre el mercado limpio, a cada sostenida y reingreso
   se le suma signo * delta * raiz(min(h, T) / h) al retorno normalizado de
   cada horizonte (T = `h_fin_franja`; signo +1 sostenida, -1 reingreso, en la
   direccion de la ruptura). La nula y los candidatos no cambian; por cada
   delta se corren la nula, Holm y Romano-Wolf sobre los mismos candidatos.
   Reportar el delta realizado igual (es delta salvo los horizontes que cruzan
   el fin de la franja).
2. Programar B como control descriptivo: inyeccion de precio autoconsistente
   (iterar inyectar -> detectar hasta que los eventos que se inyectan son los
   que se detectan), delta = 0,05 y 0,10, 4 anos, 30 mercados. Reporta delta
   realizado por celda y potencia; no decide nada.
3. **Piloto corto del diseno D** (tiempo y memoria), y **detenerse a esperar el
   OK**. Estimado de esta parte: D ~36 min y B ~5 min con la memoria de hoy.
4. Con el OK, la corrida larga (D + B), el reporte y el grafico. Cerrar el
   punto E con commit, commit del hash y `git push origin main`.

**Anotado para el punto F**: la redaccion del piso y de la limitacion de la
familia principal (frase corregida en el TRASPASO anterior) y la superposicion
de H1 y H2.

**Reglas que siguen**: sin datos reales; causalidad estricta; todo parametro
nuevo a config (POR DECIDIR si corresponde); si un control falla no se ajusta
nada para que pase; tests con 0 avisos; si una corrida pasa de una hora se
recorta tamano de muestra y se dice con su error de Monte Carlo; regla de git
al inicio de la bitacora.

**Como retomar**:

```
python -m experimentos.control_negativo --alfa-principal   la regla del alfa (lee CSV del D)
python -m experimentos.auditoria_causal                    40 cortes, ~20 s
python -m experimentos.control_positivo --piso             piso y unidades, ~1 min
python -m experimentos.control_positivo --piloto           piloto (hoy: diseno A, a reemplazar por D)
```

---

## Punto E (segunda parte) — Diseno D, control B y piloto

- **Fecha**: 2026-09-25
- **Commits**: `91b3ea2` (codigo y regla del alfa, ANTES de la corrida) y el de
  cierre, con los resultados (hash anotado al final de esta seccion). **Sin push**:
  se sube cuando el grupo revise los resultados.
- **Tests**: `pytest` -> 216 pasan, 0 fallan, 0 avisos (con el `.venv`: el
  Python del sistema trae pandas 3 y ahi falla `test_mercado.py`, como se
  preveia en `requirements.txt`).
- **Estado**: D y B programados, piloto y corrida larga hechos. La regla fijo
  **`ALFA_PRINCIPAL = 0,025`**. 21 parametros `# POR DECIDIR` (sin cambios).

### Que se programo

- **Diseno D** (`experimentos/control_positivo.py`, `corrida_curva`): por cada
  mercado limpio se hace UNA vez lo caro (eventos, candidatos, sorteo de la
  nula y remuestreos de Romano-Wolf). Despues, para cada delta, se suma +delta
  al retorno normalizado de las sostenidas y -delta al de los reingresos, en
  los 4 horizontes, y se recalculan lo observado, los p, Holm y Romano-Wolf.
- **Por que vale reutilizar**:
  - La distribucion nula sale solo de los minutos sorteados (direccion del
    evento, retorno y dia del minuto sorteado), asi que no depende de los
    retornos de los eventos.
  - En Romano-Wolf, sumar una constante a una celda de solo constante mueve
    igual la estimacion de la muestra y la de cada remuestreo, y no toca
    residuos ni errores: los estadisticos centrados `w` no cambian. Solo se
    mueve el t observado.
  - Las dos cosas estan probadas en los tests.
- **Reorganizacion del motor, sin cambiar resultados**:
  - `nula.correr` = `sortear_nula` + `resumir_nula`.
  - `inferencia.romano_wolf` = `romano_wolf_remuestreos` +
    `romano_wolf_stepdown` (con `t_de`).
  - Comprobado contra `HEAD` en un mercado simulado de 2 anos: tabla de la
    nula, distribuciones y p de Romano-Wolf **identicos bit a bit**.
- **Grilla fina**: `GRILLA_POTENCIA` (de 0 a 0,20 cada 0,005) mas
  `TAMANOS_EFECTO` dan 41 delta. Romano-Wolf tambien se evalua en la grilla
  fina porque, por la invariancia de `w`, no cuesta nada. Las tablas de
  potencia se muestran en `TAMANOS_EFECTO`; el efecto minimo detectable sale de
  la grilla fina, con intervalo al 95% remuestreando mercados.
- **Reporte de D**:
  1. Potencia por familia y por celda (Holm, `ALFA_PRINCIPAL`) con su error de
     Monte Carlo. Las 4 combinaciones van como descripcion.
  2. Efecto minimo detectable al 80%.
  3. Sesgo por celda del estimador del informe (observado menos nulo, en la
     direccion de la hipotesis), mas el de la media cruda. En D el sesgo no
     depende de delta, y se reporta la variacion maxima como control.
  4. Tasa de rechazo en delta = 0 por duracion, **aparte** de la del punto D,
     sin mezclarlas.
  5. Tabla de potencia contra costo, con la potencia bruta en delta - c,
     declarada como aproximacion.
  6. Grafico.
- **Control B** (`corrida_control_b`): inyeccion de precio autoconsistente con
  `DELTAS_CONTROL_B` = 0,05 y 0,10, `ANIOS_CONTROL_B` = 4 y
  `MERCADOS_CONTROL_B` = 10.
  - Se itera inyectar -> detectar hasta que los eventos (instante, tipo y
    direccion) coinciden, con un tope de `ITERACIONES_MAX_CONTROL_B` = 50.
  - Reporta el delta realizado por celda de dos formas:
    - **por evento**: los mismos eventos, en el mercado inyectado contra el
      limpio;
    - **de celda**: lo que se movio el promedio de la celda.
  - **No corre la nula** y no decide nada.
  - Declarado: la amplitud de la deriva usa el sigma_ref de la vuelta anterior.
    Al converger coinciden los eventos, pero sigma_ref puede diferir en la
    cuarta cifra.

### Diferencias con el TRASPASO (a revisar por el grupo)

1. El TRASPASO escribia D como signo * delta * raiz(min(h, T) / h). El mensaje
   que abrio esta parte pide **+delta en los 4 horizontes**, con un test de que
   la media se mueve exactamente delta, y eso es lo que coincide con la
   decision 1 del grupo ("sumar delta al retorno normalizado"). Se programo
   asi. Consecuencia: en D, un horizonte que cruza el fin de la franja tambien
   recibe delta completo.
2. B: el TRASPASO decia 30 mercados y "delta realizado y potencia". El mensaje
   pide "pocos mercados" y "delta realizado por celda". Quedo en 10 mercados,
   sin la nula ni potencia. Si se quiere la potencia de B, hay que agregar la
   nula: ~3 veces mas caro por mercado.
3. `MERCADOS_PILOTO` bajo de 3 a 2, como pidio el mensaje.

### Piloto (2 mercados de D por duracion y 2 de B; 500 repeticiones)

| etapa | anios | s por mercado | pico GB |
|---|---|---|---|
| D | 4 | 7,9 | 0,51 |
| D | 13 | 22,1 | 1,57 |
| B | 4 | 21,4 | 0,79 |

El diseno A tardaba 42 s y 122 s por mercado con 7 delta; D tarda 8 s y 22 s
con 41 delta.

**Estimacion de la corrida completa** (30 mercados de D por duracion y 10 de B),
con 3,0 GB disponibles, que es poco:

| bloque | procesos | minutos |
|---|---|---|
| D, 4 anos | 4 | ~1 |
| D, 13 anos | 1 | ~11 |
| B | 2 | ~2 |

**Total: ~14 minutos**, dentro de la hora y sin recortes. Con mas memoria libre
se reparte en mas procesos y baja.

**Primera mirada** (2 mercados: no es la curva):

- El delta realizado en D se aparta del nominal en 6e-17 como maximo, y el
  sesgo varia entre delta en 6e-17: cero salvo redondeo, como debe ser.
- La mediana del p de Holm baja con delta:
  - 4 anos: 1; 0,78; 0,64; 0,56; 0,10; 0,012; 0,012.
  - 13 anos: 0,91; 0,36; 0,11; 0,021; 0,012; 0,012; 0,012.
- B convergio en 4 de 4 casos, en 5 a 9 iteraciones. Razon realizado / nominal
  por evento:
  - reingresos: 0,78-0,85;
  - sostenidas: 0,39-0,75 (la mas baja es la de fin de franja).
  - Coincide con lo que se habia medido antes: la superposicion con el
    reingreso diluye sobre todo a las sostenidas.
- El reporte final y el grafico se probaron con los datos del piloto (en el
  scratchpad, sin escribir en `resultados/`).

### Siguiente paso

Con el OK del grupo: `python -m experimentos.control_positivo`, que corre D
(4 y 13 anos) y B. Despues, reporte, grafico y bitacora; commit, commit del
hash y `git push origin main`.

### Aprobacion y cambios antes de la corrida larga (2026-09-25)

El grupo aprobo D y B tal como quedaron y los tres puntos en que se aparto del
TRASPASO (siguen el mensaje que abrio esta parte). Verifico que el bootstrap de
Romano-Wolf esta centrado, asi que mover solo el t observado es correcto.
Como D salio barato, se gasta en precision:

1. **4 anos con 200 mercados** (antes 30). Es la duracion que confirma:
   - da un efecto minimo detectable preciso;
   - en delta = 0 mide el tamano con cuatro veces mas mercados que el punto D.
2. **Se agrega 6 anos** (el tramo sellado) con 100 mercados; 13 anos queda en
   30. Los mercados por duracion van a config: `MERCADOS_POR_DURACION` =
   {4: 200, 6: 100, 13: 30}. `REPETICIONES_POTENCIA` se elimina.
3. **B con tres escenarios** (`ESCENARIOS_CONTROL_B`): ambos tipos a la vez,
   solo sostenidas y solo reingresos, con delta = 0,05 y 0,10.
   - Se mide el delta realizado en las DOS celdas, incluida la no inyectada:
     eso es el contagio por la superposicion.
   - Lectura aproximada: la potencia de B es la de D en el delta realizado.
4. **Nueva regla de `ALFA_PRINCIPAL`**, escrita antes de correr (ver abajo).
5. **Tiempo**: el total se estima con el piloto; 6 anos se interpola entre 4 y
   13, y B se escala por 3 (el piloto midio un escenario).
   - Si pasa de `MINUTOS_MAX_CORRIDA` = 60, se recortan primero los mercados
     de 13 anos y se dice en el informe.
   - Estimado: ~34 minutos, sin recorte.

### Regla de ALFA_PRINCIPAL para la corrida larga (ESCRITA ANTES DE CORRER)

**Reemplaza a la medicion del punto D.**
- El punto D decidia con la tasa por prueba de 50 mercados de 3 anos.
- Desde ahora decide la tasa por prueba en delta = 0 del bloque de 4 anos del
  control positivo (`ANIOS_REGLA_ALFA` = 4, 200 mercados).
- Por que: es el mismo test (la nula emparejada, en mercados sin efecto), con
  cuatro veces mas mercados, y en la duracion que confirma.

**Objetivo explicito**: que el tamano real POR PRUEBA de la familia principal
no pase del 5%.

**Medicion**: tasa por prueba (p bruto de la nula <= alfa, en las 6 pruebas
confirmatorias), con su IC95 remuestreando mercados (10.000 remuestreos).

**Regla**:
- Si con alfa 0,05 el IC queda entero sobre 0,05, y con 0,025 su limite
  inferior no pasa de 0,05: `ALFA_PRINCIPAL = 0,025`.
- Si con alfa 0,05 el IC contiene a 0,05: se queda en 0,05.
- Si incluso con 0,025 el limite inferior pasa de 0,05: **el control falla**.
  El programa escribe solo la regla y se detiene; se explica y no se sigue.
- Caso que el grupo no listo, IC con 0,05 entero BAJO 0,05: el objetivo se
  cumple, asi que se queda 0,05. Es una interpretacion propia, escrita aqui
  antes de correr para que no dependa del resultado.

**Que se reporta**: la potencia con los dos alfas, marcando como principal el
que resulte de la regla. Aparte, sin mezclarlas, la tasa familiar con Holm y
las tasas de 6 y 13 anos. El codigo es `regla_alfa_principal` y
`aplicar_regla_alfa` en `experimentos/control_positivo.py`, con tests.

### Resultados de la corrida larga

Datos en `resultados/control_positivo.md`, `control_positivo.csv`,
`control_positivo_b.csv` y `control_positivo_potencia.png` (no se versionan).

- 27,3 minutos contra 32 estimados, sin recorte.
- Mercados: 4 anos x 200, 6 anos x 100, 13 anos x 30 y B x 10.
- 500 repeticiones de la nula y de Romano-Wolf.

**1. La regla fijo `ALFA_PRINCIPAL = 0,025`.** Tasa por prueba en delta = 0, 4
anos, 1.200 pruebas en 200 mercados:

| alfa | tasa | IC95 por mercados |
|---|---|---|
| 0,05 | 7,4% | 5,5%-9,4% (entero sobre 5%: exceso demostrado) |
| 0,025 | 4,25% | 2,8%-5,8% (el borde inferior no pasa de 5%) |

- Con 0,025, el tamano real por prueba cumple el objetivo del 5%.
- Coincide con el punto D: 7,7% con IC 4,3%-11,7% en 50 mercados. Ahora, con
  cuatro veces mas mercados, el exceso con 0,05 queda demostrado.
- `config.py` ya dice 0,025. La regla del control negativo
  (`--alfa-principal`) queda como historica.

**2. Potencia por familia con Holm y alfa 0,025 (principal).** Efecto minimo
detectable al 80%, con IC95 por mercados:

| duracion | efecto minimo | IC95 | con alfa 0,05 (descripcion) |
|---|---|---|---|
| 4 anos | 0,050 | [0,046; 0,054] | 0,043 |
| 6 anos | 0,041 | [0,038; 0,043] | 0,035 |
| 13 anos | 0,028 | [0,024; 0,035] | 0,026 |

Por celda, 4 anos:
- reingresos: 0,067-0,069;
- sostenidas: 0,085-0,090.

Las sostenidas necesitan mas efecto: su retorno es mas ruidoso (error de su
media mayor).

**3. Sesgo del estimador (observado menos nulo).**
- 4 y 6 anos: todas las celdas entre -0,0015 y +0,0034, con error de Monte
  Carlo de 0,0014-0,0027. Ninguna se distingue de cero con claridad.
- 13 anos, sostenidas: de -0,004 a -0,007 (error ~0,003). Es la unica zona a
  unos 2 errores de cero, con solo 30 mercados; se reporta y no se interpreta.
- En D el sesgo no depende de delta: variacion maxima de 3e-17.

**4. Tasas en delta = 0, cada una por separado** (no se mezclan entre si ni con
el punto D):

| duracion | por prueba, alfa 0,05 | por prueba, alfa 0,025 | familiar Holm, alfa 0,05 | familiar Holm, alfa 0,025 |
|---|---|---|---|---|
| 4 anos | (la de la regla) | (la de la regla) | 9,5% [6,2%-14,4%] | 3,5% [1,7%-7,0%] |
| 6 anos | 4,3% | 1,5% | 2,0% | 1,0% |
| 13 anos | 6,7% [2,8%-11,7%] | 4,4% | 13,3% [5,3%-29,7%] | 6,7% [1,8%-21,3%] |

- La tasa familiar con 0,05 y 4 anos (9,5%) pasa de 5%: es otra razon para el
  alfa estricto, aunque la regla decide con la tasa por prueba.

**5. Costos (aproximacion).** En 4 anos, medio pip de ida y vuelta vale 0,03 a
0,09 unidades segun el horizonte, del mismo orden que el efecto minimo
detectable. El efecto minimo neto aproximado va de ~0,10 (reingreso a fin de
franja, 0,5 pip) a ~0,44 (sostenida a 30 minutos, 2 pips).

**6. Control B (descriptivo)**: 10 mercados de 4 anos, error de Monte Carlo
<= 0,0005, todos convergieron (mediana de 4 a 7 iteraciones, maximo 12).
Delta realizado / nominal por evento:

| escenario | sostenida | reingreso |
|---|---|---|
| ambos | 0,72 (30) / 0,60 (60) / 0,39 (fin) | 0,86 / 0,82 / 0,79 |
| solo sostenidas | 0,99 / 0,99 / 1,00 | **-0,14 / -0,17 / -0,21** (contagio) |
| solo reingresos | **-0,29 / -0,41 / -0,63** (contagio) | 0,99 / 0,99 / 1,00 |

- Cuando solo un tipo tiene efecto, casi todo el delta llega a su celda.
- El contagio va en CONTRA de la hipotesis de la otra celda y es proporcional a
  delta: la razon es la misma con 0,05 y 0,10.
- Los efectos se suman: ambos ~ solo + contagio (sostenida a fin de franja:
  1,00 - 0,63 = 0,37, contra 0,39 medido).
- El contagio mas fuerte es el de un reingreso sobre la sostenida anterior de
  la misma franja: sostenida a fin de franja pierde el 63% del delta. Es la
  superposicion ya anotada para el punto F (el 71-73% de las sostenidas
  reingresa despues).
- Lectura aproximada (potencia de D en el delta realizado, 4 anos, alfa 0,025),
  con los dos tipos a la vez y delta = 0,10:
  - reingresos: ~0,95;
  - sostenidas: 0,63 (30 minutos), 0,39 (60) y 0,15 (fin de franja).

**Para el punto F**: si H1 y H2 fueran ciertas a la vez, la sostenida a fin de
franja perderia buena parte de su potencia por el contagio del reingreso. Es
una pregunta sobre como se define H1; no se cambia nada.

**Hash de cierre de esta parte**: `b2337cb` (`punto E (2a parte): curva de potencia (D), control B y ALFA_PRINCIPAL = 0,025`). Sin push hasta que el grupo revise los resultados.

---

## Cierre del punto E — diagnostico del tamano y declaraciones

- **Fecha**: 2026-09-25
- **Que se hizo**: sin correr ningun mercado.
  - `experimentos/diagnostico_tamano.py`: diagnostico del tamano con los CSV
    guardados.
  - Tabla del efecto minimo detectable POR CELDA en pips, dentro del reporte
    del control positivo, regenerado con `--solo-reporte` (mismos numeros).
  - Declaraciones y TRASPASO para el punto F.
- **Tests**: 220 pasan, 0 fallan, 0 avisos (con el `.venv`).

### Diagnostico del tamano (solo para declarar; NO cambia ALFA_PRINCIPAL)

- **Datos**: CSV del punto D (familia principal, 50 mercados de 3 anos, R =
  1000) y del punto E (delta = 0: 4 anos x 200, 6 x 100, 13 x 30, R = 500).
  Solo pruebas confirmatorias.
- **La cola opuesta sale del mismo CSV**: p_opuesto = (R + 2)/(R + 1) - p.
  - Es exacto sin empates. Se verifico que todos los p caen en la grilla
    k/(R + 1), y un test lo compara con el calculo directo.

**1. Simetria del exceso.** Tasa por prueba en la cola de H1/H2 contra la cola
opuesta, con alfa 0,05. IC95 de la diferencia remuestreando mercados:

| duracion | cola de la hipotesis | cola opuesta | diferencia [IC95] | p medio |
|---|---|---|---|---|
| D, 3 anos | 7,7% | 3,7% | +4,0 [-0,7; +8,7] | 0,467 |
| E, 4 anos | 7,4% | 6,6% | +0,8 [-1,7; +3,3] | 0,494 |
| E, 6 anos | 4,3% | 5,3% | -1,0 [-4,2; +2,0] | 0,498 |
| E, 13 anos | 6,7% | 11,7% | -5,0 [-12,8; +2,8] | 0,520 |

- **4 anos**: el exceso esta en las DOS colas (6,6% tambien en la opuesta). No
  se demuestra que favorezca a H1/H2. Con alfa 0,025: 4,25% contra 3,2%,
  diferencia [-0,8; +2,9].
- **Punto D, 3 anos**: con 0,025 la asimetria si sale distinta de cero
  (+2,7 [+0,3; +5,0]), con 50 mercados. Con 0,05, no.
- **p medio**: queda entre 0,47 y 0,52 en todos los bloques.
- **13 anos**: el p medio de las sostenidas es 0,58-0,62, coherente con su
  sesgo negativo (declarado abajo).

**2. 4 anos contra 6 anos.** Diferencia de la tasa por prueba, cada bloque
remuestreado por su lado:

| cola | alfa | 4 anos | 6 anos | 4 - 6 [IC95] |
|---|---|---|---|---|
| hipotesis | 0,05 | 7,4% | 4,3% | +3,1 [+0,4; +5,8] |
| hipotesis | 0,025 | 4,25% | 1,5% | +2,75 [+1,0; +4,6] |
| opuesta | 0,05 | 6,6% | 5,3% | +1,25 [-1,5; +4,0] |
| opuesta | 0,025 | 3,2% | 2,7% | +0,5 [-1,4; +2,4] |

- En la cola de la hipotesis, la diferencia entre 4 y 6 anos es mayor que el
  azar con los dos alfas. En la opuesta, no.
- Son cuatro intervalos mirados a la vez y ninguno se corrigio por
  multiplicidad. No hay una explicacion mecanica a la vista: los dos bloques
  usan el mismo codigo y la misma nula, y solo cambian la duracion y las
  semillas. Se declara tal cual.

### Declaraciones al cerrar E

1. **El efecto minimo detectable que va al pre-registro es el POR CELDA.**
   Holm con alfa 0,025, potencia 80%, en unidades normalizadas y en pips. Los
   pips usan el factor mediano pips/unidad con volatilidad 7% y son **un orden
   de magnitud**: la traduccion definitiva sera evento por evento con el
   sigma_ref real.

   | celda | 4 anos (confirma) | 6 anos | 13 anos |
   |---|---|---|---|
   | reingreso 30 | 0,069 (0,39 pips) | 0,056 (0,32) | 0,036 (0,21) |
   | reingreso 60 | 0,067 (0,54) | 0,054 (0,43) | 0,042 (0,33) |
   | reingreso fin de franja | 0,067 (1,10) | 0,054 (0,88) | 0,038 (0,61) |
   | sostenida 30 | 0,086 (0,49) | 0,075 (0,43) | 0,062 (0,35) |
   | sostenida 60 | 0,085 (0,68) | 0,074 (0,60) | 0,060 (0,48) |
   | sostenida fin de franja | 0,090 (1,47) | 0,072 (1,17) | 0,057 (0,92) |

   - IC95 por mercados en 4 anos: unos +-0,004 a +-0,005 (ver el reporte).
   - Factores pips/unidad: 5,68 (30 min), 8,04 (60) y 16,28 (fin de franja).
   - El de **familia** (0,050 / 0,041 / 0,028) se reporta pero **no es el
     titular**: supone que las 6 celdas tienen el efecto y cuenta cualquier
     rechazo.
2. **El tamano medido no es igual entre bloques**, y se declaran todos, sin
   promediarlos:
   - 4 anos tiene exceso: 7,4% con 0,05 y 4,25% con 0,025.
   - 6 anos no: 4,3% con 0,05 y 1,5% con 0,025.
   - 13 anos: 6,7% y 4,4%, con 30 mercados.
   - Punto D, 3 anos: 7,7% con 0,05.
   - `ALFA_PRINCIPAL = 0,025` se mantiene por la regla escrita antes de correr.
     El diagnostico de arriba no la cambia.
3. **Lectura de B.**
   - El contagio entre celdas siempre va EN CONTRA de la otra hipotesis, asi
     que la superposicion no crea falsos positivos.
   - Pero si solo existiera la reversion (H2), la celda de sostenidas saldria
     negativa: -29% a -63% del delta segun el horizonte.
   - Con ambos mecanismos, H1 a fin de franja conserva cerca del 40% del delta.
4. **Sesgo de 13 anos en sostenidas**: -0,004 a -0,007, unos 2 errores de
   Monte Carlo, con 30 mercados. Se declara: va contra H1 y es chico frente al
   efecto minimo detectable (0,057-0,062 en esas celdas). No se investiga mas.

### TRASPASO — para abrir el punto F en una sesion nueva

**Estado**:
- Fase 1 (motor y controles con datos simulados) completa hasta el punto E.
  NO se descargaron ni se miraron datos reales.
- 220 tests, 0 avisos, con el `.venv` (pandas 2.2.3; con el Python del sistema
  falla un test por pandas 3).
- Todo subido a `origin/main`.
- Controles hechos:
  - negativo (D);
  - auditoria causal (E: 40 cortes con igualdad exacta, y detecta una fuga
    sembrada);
  - piso sin sesgo (E: 200 mercados);
  - positivo con el diseno D y el control B (E).

**Numeros que van al pre-registro**:
- `ALFA_PRINCIPAL = 0,025` (Holm sobre la nula emparejada, a una cola), fijado
  por la regla escrita antes de la corrida larga.
  - Tasa por prueba con 0,05: 7,4% [5,5%-9,4%].
  - Con 0,025: 4,25% [2,8%-5,8%].
  - Datos: 4 anos, 200 mercados.
- Efecto minimo detectable POR CELDA (tabla de arriba).
  - Titular: 4 anos, 0,067-0,069 en reingresos y 0,085-0,090 en sostenidas.
  - En pips: ~0,4-1,5 como orden de magnitud.
- Tamanos medidos por bloque, declarados por separado (declaracion 2) y el
  diagnostico de simetria.
- Romano-Wolf: prueba secundaria (t de la regresion, dos colas, sin la nula).
- Horizonte de 120: descriptivo.
- Lectura de costos: aproximacion por potencia bruta en delta - c. Medio pip
  de ida y vuelta vale 0,03-0,09 unidades, del mismo orden que el efecto minimo
  detectable.

**Lo que F tiene que decidir**:
1. **Las cuatro preguntas abiertas**:
   - Que se prueba: efecto > 0 (lo actual) o efecto > costo.
   - La superposicion de eventos: el 71-73% de las sostenidas reingresa en la
     misma franja; el contagio medido en B es de -29% a -63% del delta sobre
     H1. Hay que decidir si se redefine H1, se separan eventos o se declara.
   - Donde y como registrar (plataforma y formato del pre-registro; el PDF va
     en `registro/`, que es lo unico que el `.gitignore` deja versionar).
   - Calendario: cuando se descarga el tramo de validacion y cuando se abre el
     sellado.
2. **Los 21 parametros `# POR DECIDIR` de `config.py`**:
   - Datos y eventos: `COBERTURA_MIN_REFERENCIA`, `UMBRAL_MODO`,
     `UMBRAL_PIPS`, `UMBRAL_VOL`, `M_SOSTENIDA_MIN`, `REGLA_SOSTENIDA`,
     `VENTANA_REINGRESO_MIN`, `HORIZONTE_PRINCIPAL`, `DIAS_VOL_REF_MIN`,
     `TOLERANCIA_PRECIO_MIN`.
   - Moderadores: `PASO_REDONDO`, `RADIO_REDONDO_PIPS`,
     `RADIO_EXTREMO_PREVIO_PIPS`, `DIA_PREVIO_MIN_COBERTURA`,
     `DIAS_COMPRESION_MIN`, `CORTE_COMPRESION`, `VENTANA_NOTICIAS_MIN`.
   - Nula: `NULA_GRUPOS_VOL_RECIENTE`, `VENTANA_VOL_RECIENTE_MIN`.
   - H4: `MIN_DIAS_TRATADOS`. El grupo ya lo confirmo en 15; falta quitarle la
     marca.
   - Costos: `COSTOS_IDA_VUELTA_PIPS`.
3. **La potencia de H3 y H4**: el punto E solo midio la familia principal (H1 y
   H2). Falta decidir si se mide y con que diseno (H3: coeficientes de la
   regresion con moderadores; H4: inferencia de aleatorizacion con pocos dias
   tratados).
4. **La definicion del costo**: bid/ask observado + comision + una vela de
   latencia. Hay que fijar como se mide cada parte con los datos reales y con
   que valor entra en `COSTOS_IDA_VUELTA_PIPS`, o si se reemplaza por un costo
   evento por evento.

**Reglas que siguen**:
- Sin datos reales hasta que F cierre el pre-registro.
- Causalidad estricta.
- Todo parametro nuevo va a config.
- Si un control falla, no se ajusta nada para que pase.
- Tests con 0 avisos.
- Si una corrida pasa de una hora, se recorta tamano de muestra y se dice.
- Regla de git al inicio de la bitacora.
- No se toca `Cuartinhos_Goty`; `docs/papers/` solo se lee si se pide.

**Como retomar**:

```
.venv\Scripts\activate
pytest                                                  220 pasan, 0 avisos
python -m experimentos.control_positivo --solo-reporte  reporte de la curva desde los CSV
python -m experimentos.diagnostico_tamano               diagnostico del tamano desde los CSV
```

(Los CSV de `resultados/` no se versionan: en una maquina nueva hay que volver a
correr `--piso`, `--piloto` y la curva, unos 30 minutos.)

**Hash de cierre del punto E**: `e2854b8` (`punto E (cierre): diagnostico del tamano, efecto minimo por celda en pips y traspaso a F`).

---

## Punto F, paso 1 — Tabla de decisiones para el pre-registro

- **Fecha**: 2026-09-25
- **Documento**: `registro/decisiones_F.md` (la tabla completa, con evidencia y
  recomendación por parámetro, las decisiones de protocolo y los números de
  abajo).
- **Tests**: `pytest` -> 238 pasan, 0 fallan, 0 avisos (con el `.venv`).
- **Sin datos reales. Sin push**: se sube en el paso 3, con la etiqueta.

### Que se hizo

- `MIN_DIAS_TRATADOS` pierde la marca (confirmado en 15 en el punto E). Quedan
  20 parametros `# POR DECIDIR`; la tabla recomienda mantener todos los valores
  actuales, eliminar `HORIZONTE_PRINCIPAL` (decision 3) y agregar
  `COMISION_USD_POR_MILLON_LADO = 35` (tarifa publicada de Dukascopy, tramo mas
  bajo, por lado) y `LATENCIA_VELAS = 1`. Nada de eso se aplico todavia: espera
  la decision del grupo (paso 2).
- **Simulador**: el BCE como anuncio opcional (`ANUNCIOS_SIMULADOS`; 8 al ano,
  segundo jueves, 12:45 UTC). El calendario por defecto quedo identico al de D
  y E (comparado contra `HEAD`, mercado y anuncios iguales).
- `nula.correr_h4(..., con_distribuciones=True)` devuelve los t nulos; la
  salida por defecto no cambia (test).
- **Nuevo** `experimentos/potencia_moderadores.py`: potencia de H3 y H4 con el
  principio del diseno D aplicado al subgrupo, mas dias tratados y
  prevalencias. Piloto: 13 min estimados; corrida: 10,6 min, 200 mercados de 4
  anos con el calendario de la lista cerrada (40 anuncios al ano).
- **Nuevo** `experimentos/anexo_sensibilidad.py`: el anexo pendiente del punto
  B (solo deteccion, 18 variantes, 5 mercados de 4 anos).

### Resultados

1. **Efecto minimo detectable por celda, 4 anos, alfa 0,05**:
   - H3: 0,15-0,32 unidades (reingresos 0,15-0,24; sostenidas 0,22-0,32);
     entre 2 y 4 veces el de H1/H2.
   - H4 en reingresos: 0,63-0,82. H4 en sostenidas: no llega.
   - La aproximacion normal con Bonferroni calza con la simulacion (salvo
     compresion, donde la simulacion da menos).
2. **Dias tratados** con la lista cerrada: sostenidas 2,8 por ano (11 en 4
   anos, 18% de los mercados llega a 15); reingresos 6,9 por ano. H4 en
   validacion queda, en la practica, en 4 pruebas sobre reingresos.
3. **H3 esta calibrada** en 4 anos: 5,4% por prueba, 1,5% por familia.
4. **H4 NO esta calibrada en 4 anos** (control que falla; no se ajusto nada):
   10,8% por prueba (IC95 7,6%-14,4%) y 12,0% por familia con alfa 0,05. El
   exceso es simetrico (cola opuesta 11,1%) y baja con mas dias tratados (2,7%
   con 30 o mas). En el punto D (13 anos, ~66 dias) no se veia: 7,5%. Causa
   probable, sin verificar: la nula sortea los tratados en toda la ventana de
   60 minutos y los eventos reales se concentran justo despues del anuncio.
   Opciones y recomendacion (extender la regla del alfa del punto E, que daria
   0,025 para H4) en `decisiones_F.md`, seccion e.
5. **Anexo**: con 1 pip y M = 15 rompe el 79,5% de las franjas y aguanta el
   40,5% de las rupturas. El "17%" del punto B venia de un paseo aleatorio
   simple anterior al simulador. La superposicion (73% de las sostenidas
   reingresa) no desaparece en ninguna variante (50%-83%).

### Datos externos verificados (para el pre-registro)

- BCE: decisiones a las 14:15 CET desde el 21 de julio de 2022 (antes 13:45).
- HistData: EST fijo (UTC-5, sin horario de verano) y solo bid.
- Dukascopy: 35 USD por millon por lado en el tramo mas bajo; IBKR: 0,20 pb.

### Siguiente

Esperar las decisiones del grupo sobre la tabla (en especial la seccion e, H4)
antes del paso 2.

**Hash del paso 1**: `ecb01fb` (`punto F (paso 1): tabla de decisiones, potencia de H3 y H4 y anexo de sensibilidad`). Sin push.

---

## Punto F, paso 2 — Borrador del pre-registro

- **Fecha**: 2026-09-25
- **Documento**: `registro/prerregistro.md` (borrador para la revision del
  grupo; se congela en el paso 3 con la etiqueta `prerregistro-v1`).
- **Decisiones del grupo sobre el paso 1**: al final de
  `registro/decisiones_F.md`.
- **Sin push.**

### Que se hizo

- `config.py` **sin ninguna marca POR DECIDIR**: se mantienen los 20 valores.
  - `HORIZONTE_PRINCIPAL` se elimino, con su linea de test.
  - `FOMC_POR_ANIO`, sin uso, se borro.
  - Nuevos: `COMISION_USD_POR_MILLON_LADO = 35`, `COMISIONES_SENSIBILIDAD =
    [0, 70]` y `LATENCIA_VELAS = 1`.
  - `COSTOS_IDA_VUELTA_PIPS` queda como grilla de lectura.
  - `NW_REZAGOS_FACTOR` y `NW_REZAGOS_EXPONENTE`: la regla de Newey y West
    (1994) para el contraste, que no estaba fijada en ningun lado.
  - `VARIANTES_CONTROL_NEGATIVO`: las variantes de robustez que el control
    negativo corre cambiando solo config.
  - Comentarios: H3 confirmatoria a dos colas con direccion esperada; H4
    secundaria.
  - Test nuevo: ninguna linea de config puede quedar marcada POR DECIDIR.
- **Ningun valor cambio respecto de D y E**, asi que no hubo que volver a
  correr ningun control: los numeros de D, E y del paso 1 siguen valiendo.
- `inferencia.rezagos_newey_west` y `nula.ic_h4` (IC de H4 por inversion de la
  prueba de aleatorizacion), con tests.
- `control_negativo --variante NOMBRE`: corre una variante y escribe
  `control_negativo_<variante>_*`, sin pisar la corrida principal (que leen la
  regla del alfa y el diagnostico).
- `diagnostico_tamano`: nueva seccion 4, el tamano de las variantes al lado de
  la corrida principal.
- **Tests**: 244 pasan, 0 fallan, 0 avisos (con el `.venv`).

### Control negativo de las variantes de robustez (pedido g)

Mismas semillas que el punto D. 25,2 min ("vol") y 23,6 min (UTC), con 2
procesos en el bloque corto y 1 en el largo por la poca memoria libre (2-3 GB).
Cada corrida por separado quedo bajo la hora; no se hizo piloto.

| corrida | principal, 0,05 | principal, 0,025 | familiar Holm, 0,025 | moderadores, por prueba | moderadores, familiar | H4 ventana |
|---|---|---|---|---|---|---|
| principal (D) | 7,7% [4,3; 11,7] | 4,0% [2,0; 6,0] | 8% | 4,8% | 0% | 7,5% |
| umbral "vol" | 7,0% [4,3; 10,0] | 4,0% [2,0; 6,3] | 4% | 4,4% | 2% | 8,3% |
| particion UTC | 6,7% [4,0; 9,7] | 3,3% [1,3; 5,7] | 2% | 5,0% | **10%** [4,3; 21,4] | 4,2% |

- **Nada falla de forma demostrada.** Se declaran dos cosas y **no se ajusto
  nada**:
  - con la particion UTC, la familia de moderadores rechaza en 5 de 50
    mercados (el IC de Wilson contiene el 5%);
  - con "vol", la asimetria de la cola de la hipotesis contra la opuesta sale
    distinta de cero con 0,05 (+5,0 [+0,7; +9,0]), en los mismos 50 mercados
    que en la corrida principal daban +4,0 [-0,7; +8,7].
- **La particion UTC se pudo correr cambiando solo `ZONA`**, pero el simulador
  ancla su perfil horario y su regimen diario a `ZONA`. Por eso el mercado
  simulado de esa variante sigue el reloj UTC, y el control no mide el desfase
  de una hora que el horario de verano produce contra un mercado anclado a
  Londres. Queda declarado en el pre-registro. Si el grupo quiere el control
  mas fiel, hay que separar la zona del simulador (un parametro nuevo de
  simulacion) y volver a correr (~25 min).
- Otro numero que faltaba declarar, del punto D recalculado sobre las 6 pruebas
  confirmatorias: la tasa familiar de Holm con 0,025 en 3 anos es 8% (4 de 50).
  Va al pre-registro, seccion 6.3.

### Siguiente

Revision del borrador por el grupo. Con su OK explicito: paso 3 (correcciones,
PDF, etiqueta `prerregistro-v1`, push).

**Hash del paso 2**: `599945e` (`punto F (paso 2): config sin marcas, variantes de robustez calibradas y borrador del pre-registro`). Sin push.

---

## Punto F, paso 2 (revision del grupo) — Ajustes al borrador

- **Fecha**: 2026-09-26
- **Sin push.** El paso 3 (congelar) se pide aparte.

### Decisiones del grupo

1. **Sin OSF.** El pre-registro se congela con la etiqueta anotada
   `prerregistro-v1` en el repositorio publico de GitHub.
   - Se quitaron todas las menciones a OSF, incluidas las marcas `[OSF: ...]` de
     los titulos.
   - Una **enmienda** es una seccion fechada en "Enmiendas", al final del
     pre-registro, con una etiqueta nueva (`prerregistro-v2`, ...) y su entrada
     en esta bitacora, siempre antes de abrir validacion.
   - La nota por un error de codigo despues de abrir validacion va en esta
     bitacora.
   - El hito del 29-09 es el congelamiento, antes de cualquier descarga.
   - Consecuencia de la regla general: una configuracion de H5 fuera del
     conjunto cerrado solo puede agregarse con una enmienda, o sea antes de abrir
     validacion. En `decisiones_F.md` (b.5) decia "antes de abrir el sellado".
2. **5.2**: se agrego la tabla de lectura de la pregunta 1 segun el resultado
   de H1 y H2 (con la regla 8.2 (a) en el caso "H1 no, H2 si").
3. **7.1**: se agrego el Reality Check de White (2000), que la propuesta citaba
   junto a Romano-Wolf. Tampoco se usa en las familias; la busqueda de H5 se
   penaliza con el DSR y la probabilidad de sobreajuste. Se agrego a las
   referencias.
4. **Particion UTC**: queda declarada como esta, sin parametro nuevo.
5. **Aprobadas**: las cinco decisiones de redaccion del paso 2, la regla de
   rezagos de Newey-West y el IC de H4 por inversion de la prueba.

### PDF de lectura

`resultados/prerregistro_lectura.pdf` (14 paginas; no se versiona, lo ignora
`*.pdf`).

- Lleva un aviso arriba: version de lectura, no congelada.
- Se genero con lo que hay en la maquina, sin agregar dependencias al proyecto:
  pandoc 3.10 (Markdown a HTML con una hoja de estilo de impresion) y Microsoft
  Edge sin interfaz (`--headless --print-to-pdf`).
- El paso 3 usara el mismo camino para `registro/prerregistro_v1.pdf`.

**Tests**: 244 pasan, 0 fallan, 0 avisos (con el `.venv`). No cambio codigo en
esta revision.

**Hash de la revision del paso 2**: `6f5afad` (`punto F (paso 2, revision): pre-registro sin OSF, lectura de la pregunta 1 y Reality Check de White`). Sin push.

---

## Punto G — Datos reales: candado, descarga y control de calidad (en curso)

- **Fecha**: 2026-10-01
- **Rama**: `etapa-datos` (worktree `Cuartinhos_EURUSD_datos`). El pre-registro
  NO esta congelado: el grupo lo afina en `main`. Esta etapa trabaja a ciegas:
  se obtienen los datos y se revisa su calidad, sin calcular ningun resultado.
- **Etiqueta de referencia**: `prerregistro-borrador-1` (el plan antes de
  descargar).

### Decisiones del grupo sobre el plan (paso 1)

1. **Dukascopy**: sus terminos de uso prohiben el acceso automatizado al sitio
   sin consentimiento escrito (seccion 3). No se automatiza: la exportacion la
   hace el grupo a mano con JForex (cuenta demo, Historical Data Manager),
   EUR/USD, 1 minuto, bid y ask por separado, hora UTC, sin filtro de velas
   planas. Primero enero de 2016 (piloto); el periodo completo (04-05-2003 a
   31-12-2020) despues del OK al piloto.
   - Las velas planas (minutos sin ticks, volumen 0) pasan a faltantes; el
     control de calidad reporta cuantas hay por ano.
2. **BLS**: no se bajan los ~430 comunicados. Se usan las paginas de archivo
   de Employment Situation y CPI (fecha real de cada comunicado) y se
   verifica la hora de 8:30 ET en una muestra. El contacto que pide el BLS va
   en una variable de entorno (`CUARTINHOS_CONTACTO`) y no se escribe en el
   repositorio ni en esta bitacora. Fed y BCE como se propuso, con pausas.
3. **Cambio en motor**: aprobado, con la condicion de comparar la deteccion
   antes y despues con igualdad exacta (abajo).
4. **HistData**: automatizada, con pausas, reintentos y retomable. No publica
   terminos de uso; no pide registro; el FTP pagado es solo por velocidad.
5. No se usa ni se modifica `20_Data\descarga_eurusd.py` (otro estudio).

### Cambio en motor (codigo que se va a congelar)

**Por que**: el control de calidad necesita el calendario de franjas y el
detector de rupturas, pero no puede importar `resultados`, `nula` ni
`inferencia`. `motor/__init__.py` importaba `resultados` siempre, y
`eventos.py` tambien (por sigma_ref y el precio en t + M).

**Que cambio** (sin cambiar el comportamiento):
- `motor/rupturas.py` (nuevo): `umbrales`, `primera`, `primera_ruptura`,
  `franjas_con_referencia` (la mascara de `franjas_utilizables` sin la
  condicion de sigma_ref) y `detectar` (solo la ruptura: si hay, direccion y
  minuto). Solo importa `tiempo`.
- `eventos.py` usa esas funciones; `franjas_utilizables` =
  `franjas_con_referencia` & sigma_ref finita.
- `motor/__init__.py` ya no importa los submodulos al cargarse; `preparar` los
  importa adentro. Nadie usaba `motor.<submodulo>` despues de un `import motor`
  (verificado con grep).

**Comparacion exacta antes/despues** (regla del punto E):
- 6 mercados simulados de 2 anos (semillas 20260916 a 20260921) x 6 variantes
  de config (principal, umbral "vol", particion UTC, sin excluir la barra
  ambigua, regla "fuera_en_t_mas_m", umbral de 3 pips) = 36 combinaciones.
- Se comparo la tabla completa de `motor.preparar` (eventos con retornos y
  moderadores) con `assert_frame_equal(check_exact=True)`, la mascara de
  franjas utilizables con `np.array_equal` y el largo del calendario.
- Foto tomada con el codigo de `debbfbb` (antes de tocar nada); comparacion
  despues del cambio: **36 de 36 identicas**. Ejemplo de huella (principal,
  semilla 20260916): 3.531 eventos (1.546 rupturas, 1.328 reingresos, 657
  sostenidas), sha256 de la tabla `e2f2d5324166e493...`, igual antes y
  despues.
- La rama ambigua no aparece en el simulador (sin_excluir_ambigua = principal
  en los 6 mercados); la cubren los tests de `test_eventos.py` y
  `test_rupturas.py`.
- Tests: 244 -> 244 pasan tras el cambio; `test_rupturas.py` amarra que
  `rupturas.detectar` da las mismas rupturas (franja, direccion y minuto) que
  `eventos.detectar` con el umbral de 1 pip, el "vol" y el de 3 pips.

### Candado (regla 3), antes de leer un solo dato

Commit `2292d7f`, anterior a la primera descarga.
- `fuentes/cargador.py` es la unica lectura de precios (un test revisa que
  ningun otro modulo lea parquet ni conozca las rutas de los precios, salvo los
  de datos).
- Sin la etiqueta `prerregistro-v1`: solo entrega datos a `fuentes.calidad`
  (proposito "calidad"; el cargador revisa el modulo que llama), en cualquier
  tramo menos el sellado. Todo otro pedido es un error.
- Lectura que toca validacion: exige arbol de git limpio y deja ANTES una
  linea "lectura de calidad" en `registro/aperturas.md` (fecha UTC, clase,
  tramo, fuente, proposito, rango, commit y usuario de git). Unica excepcion
  al arbol limpio: el propio `registro/aperturas.md`, que es lo que el
  cargador escribe (sin ella, la segunda lectura de una corrida no podria
  hacerse). La conversion de crudos a parquet sigue la misma regla.
- Con la etiqueta: seccion 2.4 (desarrollo libre; validacion y sellado con
  `abrir=`, linea "apertura").
- Descarga y conversion rechazan toda fecha desde el 01-01-2021.
- Crudos sin modificar: la conversion verifica tamano y sha256 contra
  `registro/manifiesto_datos.csv` antes de leer cada archivo.
- Rutas en `config.py` (seccion 12), cambiables con `CUARTINHOS_CRUDOS` y
  `CUARTINHOS_PROCESADOS`.
- Tests nuevos: `test_candado.py` (24), `test_fuentes.py` (17),
  `test_rupturas.py` (7): 292 pasan, 0 avisos.

### Registro de aperturas: solo crece (decision del grupo, 2026-10-01)

- Se confirma la excepcion del arbol limpio para `registro/aperturas.md`, con
  dos condiciones:
  1. a ese archivo solo se le agregan lineas; nunca se editan ni se borran;
  2. se commitea al cierre de cada sesion de trabajo.
- La condicion 1 la vigila el codigo: antes de cualquier lectura que lo exija
  y antes de anotar, el cargador compara el archivo con su version del ultimo
  commit (`git show HEAD:registro/aperturas.md`) y exige que empiece
  exactamente con ella. Si hay una linea editada o borrada, o el archivo no
  esta, no pasa nada. Test nuevo en `test_candado.py`; 293 pasan, 0 avisos.

### Piloto (paso 2), estado al 2026-10-01

- HistData, enero de 2016: bajado (zip anual de 2016, 3,4 MB, 14 s; HistData
  solo da archivos anuales para los anos cerrados), convertido solo enero
  (28.905 barras) y revisado (`resultados/calidad_piloto_histdata.md`): 5
  decimales, solo bid, volumen siempre 0, 0 barras invalidas, las 4 semanas
  abren y cierran a las 17:00 de Nueva York exactas, ningun hueco de mas de
  60 minutos fuera del fin de semana.
- Dukascopy: la exportacion de enero de 2016 no esta en esta maquina (la
  carpeta `Raw\Cuartinhos_EURUSD\dukascopy\` esta vacia; tampoco hay CSV
  recientes en el perfil ni instalacion de JForex). El piloto queda a la
  espera de esos dos archivos.

### Piloto (paso 2): resultado, enero de 2016

**Dukascopy, lo que trajo la exportacion de JForex** (dos CSV, Bid y Ask,
exportados por el grupo del 31-12-2015 al 02-02-2016 para cubrir enero):
- El computador esta en UTC-3 (hora de verano de Chile). El selector de fechas
  de JForex trabaja en hora local: los archivos parten el 31-12-2015 a las
  03:00 UTC y terminan el 02-02-2016 a las 02:59 UTC, o sea de medianoche a
  medianoche de Chile. El encabezado dice `Time (UTC)` y los datos SI estan en
  UTC (zona, abajo).
- **Coma decimal**: JForex en espanol escribe "1,08701" y separa los campos
  tambien con coma; las filas traen 10 u 11 campos contra 6 del encabezado. La
  primera conversion lo rechazo (520 filas "no numericas") y se agrego al
  lector el formato con coma decimal, con controles estrictos: 10 u 11 campos,
  solo digitos, precios dentro de `PRECIO_PLAUSIBLE` (0,5-2,5). Los cuatro
  precios siempre traen parte entera y decimales; el volumen entero viene sin
  decimales (una coma menos). Se reviso con los digitos enmascarados, sin
  mirar precios.
- **Sin sabados**: JForex no exporta el fin de semana (faltan el 1 de enero,
  feriado, y los cinco sabados); los domingos empiezan a las 22:00 UTC.
- 31.680 filas por lado; 28.920 en enero UTC (lo demas se descarta al
  convertir). Dentro de la semana, 10 velas planas (volumen 0): pasan a
  faltantes.

**Control de calidad del piloto** (`resultados/calidad_piloto.md`), las dos
fuentes, enero de 2016:

| chequeo | resultado | criterio |
|---|---|---|
| formato | 5 decimales en las dos; minutos exactos; Dukascopy 28.920 barras, HistData 28.905 | - |
| integridad | 0 barras invalidas en las dos; Dukascopy: 10 planas (mercado abierto) | < 0,1%: cumple |
| zona horaria | maximo en desfase 0 (correlacion 0,9925; en +-1 minuto, -0,02); barrido de +-15 h tambien en 0 | cumple |
| apertura y cierre | 4 semanas por fuente, todas a las 17:00 de Nueva York exactas | cumple |
| huecos | ninguno de mas de 60 minutos fuera del fin de semana; bajo cobertura solo las 4 franjas [18,24) de los viernes | informativo |
| horario de verano | enero no tiene cambios de hora (se vera en la corrida completa) | - |
| spread Dukascopy | mediana 0,2-0,3 pips; 1,1 pips a las 22 UTC (cierre de Nueva York); maximo 9,3; ninguna barra con mas de 10 | informativo |
| extremos por franja | mediana 0,1 pip y p95 0,3 pip, en H y en L (76 franjas) | informativo |
| rupturas coincidentes | 76 franjas comparables, acuerdo 100%; de las 62 que rompen igual, 93,5% a 2 minutos o menos y 88,7% en el mismo minuto | >= 90%: cumple |

**Estimacion para la corrida completa** (con los tamanos del piloto):
- Crudos: Dukascopy ~780 MB (CSV, ~22 MB por ano y lado); HistData ~60 MB.
- Procesados: Dukascopy ~320 MB; HistData ~120 MB.
- Maquina: HistData ~8 min de descarga; conversion ~5 min; control de calidad
  ~8-10 min (el barrido amplio de zona tarda ~16 s por ano). Mas la
  exportacion manual de Dukascopy.

Commits del piloto: `d196780` (barrido amplio de zona), `10dbfc7` (lector con
coma decimal). Tests: 299 pasan, 0 avisos. `registro/aperturas.md` sin
cambios en esta sesion (ninguna lectura toco validacion).

### INCIDENTE: exportacion accidental que incluye el tramo sellado (2026-10-01)

**Que paso.** Al exportar el periodo completo de Dukascopy en JForex, el rango
quedo por error en 01.01.2003 - 31.12.2026. JForex genero dos archivos que
incluyen el tramo sellado (desde el 01-01-2021), segun lo informo el grupo:

| archivo | bytes | modificado | sha256 |
|---|---|---|---|
| `EURUSD_1 Min_Ask_2003.05.04_2026.10.01.csv` | 513.842.886 | 2026-10-01 22:30:45 | `68195c30431667a6f8555e0cfefce3bc8623ae632284ff16a17f90ba46ff9995` |
| `EURUSD_1 Min_Bid_2003.05.04_2026.10.01.csv` | 513.940.194 | 2026-10-01 22:32:33 | `a7f782ffdf26afe71984d3344e546da239fc5da5c7de802c0ece35012f6d03e0` |

Las horas son las que informo el grupo y calzan con UTC: los archivos
re-exportados se escribieron a las 22:44 UTC (19:44 hora local, UTC-3).

**No se leyeron con codigo.** Ningun programa del proyecto los abrio: no se
registraron en el manifiesto, no se convirtieron y el cargador nunca los vio.
Cuando Claude retomo el trabajo ya no existian.

**Excel (complemento informado despues).** La primera version del grupo decia
que nadie los habia abierto. Despues se informo que, antes de borrarlos, se
abrieron por error unos segundos en Excel: segun los recientes de Windows, a
las 22:41, el Bid y el Ask de 2003-2026 y el Ask del piloto. Excel solo carga
el primer millon de filas (1.048.576), o sea desde mayo de 2003: con unas
370.000 filas por ano, eso llega hasta comienzos de 2006, dentro del
desarrollo. No se mostro nada del sellado.

**Verificaciones de Claude:**
- El Ask del piloto (`EURUSD_1 Min_Ask_2015.12.31_2016.02.02.csv`) sigue
  coincidiendo con su sha256 del manifiesto (`77012e3d...f8da3`, 1.872.436
  bytes): Excel no lo modifico. El Bid del piloto tambien coincide
  (`2c7409c6...19e3`).
- Los dos archivos del incidente no estan: busqueda por nombre en
  `C:\WorkSpace` y en el perfil (Descargas, Documentos, Escritorio), sin
  resultados; la papelera (11 elementos) no tiene ninguno; el cache de JForex
  (`C:\Users\sanch\AppData\Local\Programs\JForex4\.cache`) ya no existe. Solo
  se miraron nombres y metadatos.

**Se borraron y se re-exporto solo hasta 2020:**
`EURUSD_1 Min_Ask_2003.05.04_2020.12.31.csv` (387.656.145 bytes) y
`EURUSD_1 Min_Bid_2003.05.04_2020.12.31.csv` (387.704.988 bytes). Todavia no
se registran ni se leen: eso es el paso 3.

**Registro.** Linea "incidente: descarga accidental que incluye el sellado; no
leída; borrada" en `registro/aperturas.md` (2026-10-01 23:08:44 UTC, commit
`86dc1ae`). Esa linea usa el texto que pidio el grupo; el episodio de Excel
queda descrito aqui.

**Proteccion nueva** (commit `86dc1ae`): el registro de crudos rechaza, sin
leerlo, todo CSV de Dukascopy cuyo nombre no declare una fecha final anterior
al 2021-01-01 (`manifiesto.exigir_nombre_antes_del_sellado`). Se revisa antes
de calcular la huella, en `registrar` y en `registrar_manuales` (si un archivo
falla no se registra ninguno), y el cargador lo repite antes de convertir. Un
nombre sin fecha final tambien se rechaza. Tests en `test_fuentes.py` (el test
falla si se intenta leer el archivo); 309 pasan, 0 avisos.
- Lo que el nombre no garantiza: en el piloto, un archivo con fecha final
  "2016.02.02" llego hasta las 02:59 UTC de ese dia (el selector trabaja en
  hora local). Con "2020.12.31" el contenido queda dentro de 2020, pero la
  conversion igual revisa cada minuto y rechaza cualquiera desde el
  2021-01-01.

**Pendiente para el grupo.** El pre-registro (2.2 y 2.3) dice que el sellado
no se descarga hasta la Etapa 5. Como se declara este incidente es decision
del grupo (el pre-registro se edita en `main`, no en esta rama).

### Paso 3: descarga completa, conversion y control de calidad (2026-10-01)

**Registro de aperturas.** Se agrego la linea que completa la del incidente
("complemento al incidente del 01-10-2026: ... Excel ...; ningun programa del
proyecto los leyo"), 23:13:52 UTC.

**Dukascopy (exportacion manual del grupo, 2003-05-04 a 2020-12-31).**
- `EURUSD_1 Min_Bid_2003.05.04_2020.12.31.csv` (387.704.988 bytes) y
  `EURUSD_1 Min_Ask_2003.05.04_2020.12.31.csv` (387.656.145 bytes), en el
  manifiesto (el registro reviso antes el nombre: fecha final 2020-12-31).
- **Primera pasada, solo horas, antes de interpretar un precio** (nuevo en el
  cargador, `revisar_minutos_dukascopy`, con sus tests):
  - ningun minuto desde el 2021-01-01: la primera barra es el 2003-05-04
    21:00 UTC y la ultima el 2020-12-31 21:59 UTC (cierre de Nueva York; el
    ano viene completo);
  - Bid y Ask traen exactamente los mismos minutos todos los anos (0 minutos
    en un solo lado); 6.619.380 filas por lado, sin repetidas;
  - JForex trae todos los minutos de la semana de mercado (373.560 a 377.160
    por ano completo): los feriados vienen como velas planas.
- Los CSV del piloto se solapan con la exportacion completa en enero de 2016
  y coinciden fila por fila (la conversion se habria detenido si no).
- Conversion: 2 min 05 s; 18 parquet por ano. Anotada en `aperturas.md`
  (lectura de calidad, conversion a parquet, 23:17:23 UTC, commit `8b25362`).

**HistData.** 18 zip anuales (2003-2020), 51 MB, 414 s con pausas de 10 s,
todos en el manifiesto. Conversion desde el 2003-05-04 (el primer dia de
Dukascopy): 21 s, ningun minuto desde el 2021-01-01. Anotada en
`aperturas.md` (23:28:07 UTC, commit `1cc5728`). HistData trae menos barras en
los anos antiguos (300.000 a 358.000 por ano entre 2004 y 2011, contra
~375.000 de Dukascopy): no rellena los minutos sin ticks.

**Control de calidad completo** (`python -m fuentes.calidad --desde 2003-05-04
--hasta 2020-12-31`; 216 s; `resultados/calidad.md` y sus CSV, no
versionados). Las 8 lecturas de validacion (2017-2020, dos fuentes, con 3 dias
de margen) quedaron en `aperturas.md` (23:32-23:33 UTC, commit `5d4e0b6`). Ese
registro se commiteo (`5b4e3f5`).

| chequeo | resultado | criterio |
|---|---|---|
| integridad | Dukascopy: 125 barras invalidas en 6.619.380 (todas en 2013, spread <= 0; 0,034%); 10.469 planas (pasan a faltantes). HistData: 0 invalidas | < 0,1%: **cumple** todos los anos |
| **zona horaria** | maximo en **+60 minutos** todos los anos (2016: 0,54 en +60, 0,45 en 0); el barrido de +-15 h tambien da +60 | **FALLA** todos los anos |
| apertura y cierre | Dukascopy: 5 de 920 semanas fuera de rango (feriados, un hueco en 2003); HistData: 44 de 916 | se listan |
| huecos | > 60 min fuera del fin de semana: Dukascopy 20, HistData 125 (sobre todo 2004-2005) | informativo |
| cobertura (sin la franja [18,24) del viernes) | Dukascopy 0%-1,4% de franjas bajo 0,90 por ano; HistData 11%-68% en 2003-2011, 0,6%-1,8% desde 2012 | informativo |
| horario de verano | 35 franjas de 5 o 7 horas, todas en domingos de cambio del Reino Unido | **cumple** |
| spread Dukascopy | mediana 1,0 pip hasta 2009, 0,3 desde 2013; mas ancho a las 21-22 UTC desde 2007; 716 barras con mas de 10 pips | informativo |
| extremos por franja | mediana de la diferencia 0,0-0,2 pips desde 2015; 2-5 pips antes de 2010 (HistData mas alto) | informativo |
| rupturas coincidentes | acuerdo 85,9%-94,7%; 7 anos entre 80% y 90% (2003-2006, 2008, 2009, 2011); a 2 minutos o menos solo 27%-45% | advertencia en 7 anos |

**Causa de la falla de zona (diagnosticada con lo ya calculado, sin leer
precios de nuevo).** La apertura del domingo de Dukascopy sigue a Nueva York
todo el ano: 21:00 UTC en el verano de EE. UU. (559 semanas) y 22:00 en
invierno (320). HistData, convertido con +5 h fijas, abre a las 22:00 UTC
tambien en verano (526 de 555 semanas): la mediana de su apertura y su cierre
queda 60 minutos tarde en verano, todos los anos. Los archivos de HistData
estan en hora de Nueva York CON horario de verano, no en "EST fijo sin horario
de verano" como dice su documentacion y como quedo escrito en el pre-registro
(3.1) y en `decisiones_F.md` (b.4). El piloto de enero no podia verlo (enero
es invierno).

**No se cambio ninguna definicion.** La conversion oficial sigue en EST fijo.
Se agrego `HISTDATA_ZONA` (por defecto None = EST fijo) solo para
diagnosticar.

**Diagnostico, solo desarrollo (2003-05-04 a 2016-12-31), en carpetas
temporales** (`scratchpad`; no toca validacion ni deja lineas en el registro):
HistData convertido con America/New_York.
- Zona por ano: maximo en 0 en 2004-2016 (correlacion 0,45 a 0,99); 2003 en
  +1 minuto (0,209 contra 0,198 en 0).
- Zona por mes: 153 de 164 meses en 0; todos desde 2007. Los 11 que no:
  mayo-julio de 2003 en -60 (esos meses HistData estaba en EST fijo),
  octubre-diciembre de 2003, febrero, marzo y junio de 2004 en +1 o +2
  minutos, noviembre de 2004 en -1, octubre de 2006 en +1.
- Rupturas coincidentes: acuerdo de 91,0% a 99,8%, **todos los anos cumplen**
  el 90%; a 2 minutos o menos, 59%-97%.
- Extremos: 0,1-0,7 pips desde 2010; HistData sigue 2-5 pips mas alto antes de
  2009 (su "bid" antiguo parece venir de otro proveedor; ademas viene con 4
  decimales en 2003-2008 y 2010).

**Calendario de anuncios** (`python -m fuentes.calendario`; 489 paginas
oficiales guardadas en `Raw\Cuartinhos_EURUSD\calendario\` y registradas en
el manifiesto; el contacto que pide el BLS se paso solo por la variable de
entorno, no esta en ningun archivo):
- `calendario/anuncios.csv`: 738 anuncios de 2003 a 2020. BLS: 12 de empleo
  y 12 de IPC por ano. BCE: 12 por ano hasta 2014 y 8 desde 2015. Fed: 8 por
  ano (7 en 2020, por la reunion cancelada de marzo). En validacion, 40 por
  ano, como dice el pre-registro (4.8).
- Horas: Fed, 39 del propio comunicado (14:00) y 75 de las minutas de la
  reunion (44 a las 14:15, 23 a las 14:00 y 8 a las 12:30, las reuniones con
  conferencia de prensa de 2011-2012); BLS, 8:30 ET, verificada en la linea de
  embargo de 10 comunicados (primero de 2003, 2008, 2013 y 2018 de cada serie,
  y los atrasados de octubre de 2013); BCE, 13:45 CET por la regla publicada
  (el comunicado no dice su hora).
- `calendario/excluidos.csv` (39): de la Fed, las conferencias telefonicas y
  lo marcado "(unscheduled)", "(cancelled)" o "(notation vote)", y la
  reunion del 15-09-2003, sin comunicado; del BCE, la decision del 08-10-2008
  (recorte coordinado) y entradas de la lista que no son decisiones de
  politica monetaria (TARGET2-Securities 2007; PEPP y operaciones de 2020).
- Ajustes de lectura en el camino (ninguno cambia la lista cerrada):
  comunicados del BLS en texto hasta 2007 y con enlace absoluto en 2019;
  URL de la Fed con barra final o sufijo "b"; regla del BCE: es programada
  si el comunicado dice "At today's meeting" o anuncia la conferencia de prensa
  del dia (el dia de la semana no servia: varias reuniones programadas fueron
  en miercoles).
- **Pendientes (`calendario/pendientes.csv`, 29)**: 28 comunicados de la Fed de
  2003 a junio de 2006 dicen "For immediate release" y sus minutas solo "to be
  released shortly after the meeting"; el del 25-06-2008 tiene las minutas
  solo en PDF. Todos de desarrollo. No entran a `anuncios.csv` hasta que el
  grupo decida: no se adivina la hora.

### Decisiones pendientes del grupo (paso 3 detenido)

1. **Zona horaria de HistData** (falla un criterio de 3.3; no se cambio
   ninguna definicion). Opciones:
   - (a, recomendada) convertir HistData con la hora de Nueva York CON horario
     de verano (`HISTDATA_ZONA = "America/New_York"`) y repetir la conversion
     y el control de calidad completos. Es lo que el pre-registro manda para la
     zona ("error de manejo: se corrige y se repite"), pero obliga a corregir
     en `main` la frase de 3.1 ("EST fija ... sumando 5 horas"). Con el
     diagnostico de desarrollo, la zona queda en 0 desde 2004 (todos los meses
     desde 2007) y el acuerdo de rupturas pasa el 90% todos los anos. Quedan
     11 meses de 2003-2006 con el maximo fuera de 0 (HistData antiguo), y 2003
     como ano completo en +1 minuto: hay que decidir como se declaran.
   - (b) mantener EST fijo y declarar la falla: la replica con HistData
     quedaria corrida una hora en el verano de EE. UU.
   - (c) desfase empirico por semana: da lo mismo que (a) con una regla ad hoc.
2. **Hora de 29 comunicados de la Fed** (todos de desarrollo):
   - (a, recomendada) 2:15 p.m. ET, la hora que la Fed uso en todas las
     reuniones programadas desde que las minutas la registran (2006) hasta 2012,
     rotulada en `fuente_hora` como practica de la Fed y no como dicha por la
     fuente. El de 2008-06-25 puede leerse a mano en el PDF de sus minutas.
   - (b) buscar la hora a mano en las transcripciones del FOMC (PDF).
   - (c) dejarlos fuera: esos dias contarian como "sin anuncio" en desarrollo.
3. **Push** de la rama: pendiente del OK del grupo (el paso 3 no termino).

**Tests**: 323 pasan, 0 avisos. Ningun resultado posterior a eventos ni
sostenidas o reingresos: el control de calidad solo uso rupturas (si hay,
direccion y minuto), y el diagnostico, lo mismo, en carpetas temporales.
`registro/aperturas.md` commiteado al cierre de la sesion.

### Paso 3, decisiones del grupo aplicadas (2026-10-02)

Decisiones (sobre el reporte anterior):
1. **Zona de HistData**: se convierte con la hora de Nueva York con horario de
   verano (`HISTDATA_ZONA = "America/New_York"`) en todos los anos. Es un error
   de manejo de la segunda fuente (3.3), no un cambio de definiciones. La frase
   de 3.1 del pre-registro la corrige el grupo en `main`.
   - Los 11 meses de 2003-2006 que no quedan en desfase 0 NO se corrigen con
     desfases calculados: quedan "fuera de alineacion"
     (`HISTDATA_MESES_FUERA_DE_ALINEACION`) y el cargador no los entrega para
     el analisis (`limpiar`). El analisis principal (Dukascopy) no cambia.
2. **Fed**: 2:15 p.m. ET ("practica de la Fed") para los 29 comunicados
   anteriores a 2009 sin hora en la fuente. El PDF de las minutas del
   25-06-2008 lo confirma: "The vote encompassed approval of the statement
   below to be released at 2:15 p.m." (leido con la biblioteca estandar:
   zlib sobre los bloques de texto del PDF, sin dependencias nuevas).

Codigo (commit `6d680c5`): `cargador.diagnostico` marca `fuera_de_alineacion`;
`limpiar` (analisis) los saca y `limpiar_barras` (la fuente tal cual) no. El
control de calidad usa la fuente con todos sus meses en los chequeos de una
sola fuente y la replica (sin esos meses) en los que comparan fuentes, y mide
la zona mes por mes con todos los meses. Calendario: `hora_por_practica`.
Tests: 325 pasan, 0 avisos.

**Conversion repetida** (HistData, 2003-05-04 a 2020-12-31, 23 s; anotada en
`aperturas.md`, 00:25:45 UTC) y **control de calidad completo repetido**
(`resultados/calidad.md`; 8 lecturas de validacion anotadas):

| chequeo | resultado |
|---|---|
| zona por ano (replica) | maximo en 0 los 18 anos (barrido de +-15 h tambien); correlacion 0,51-0,77 en 2003-2007 y 0,71-0,99 desde 2008 | **cumple** |
| rupturas coincidentes (replica) | 91,6%-99,8%, todos los anos >= 90%; a 2 min o menos, 69%-90% hasta 2011 y 93%-97% desde 2012 | **cumple** |
| integridad | sin cambios (Dukascopy 125 invalidas, 0,034% max.; HistData 0) | **cumple** |
| extremos | mediana 0,0-0,1 pips desde 2015; 2-5 pips antes de 2010 (HistData mas alto) | informativo |
| zona mes por mes | 212 meses; 199 con el maximo en 0; los 11 de la lista coinciden con la medicion | ver abajo |

**Hallazgo nuevo (no cubierto por la decision): 2019 y 2020.** La zona mes por
mes marca tambien **marzo de 2019 y marzo de 2020** en -60, y no estan en la
lista. La tabla de aperturas y cierres semanales (ya calculada, sin leer
precios de nuevo) muestra que en esos dos anos HistData cambia de horario en
las fechas EUROPEAS (ultimo domingo de marzo y de octubre), no en las de EE.
UU. Entre unas y otras queda corrido -60 minutos (8 semanas, todas de
validacion):

| periodo | semanas | evidencia |
|---|---|---|
| 10 al 31 de marzo de 2019 | 3 | apertura del domingo 60 min antes y cierre del viernes 60 min antes que Nueva York |
| 27 de octubre al 3 de noviembre de 2019 | 1 | idem |
| 8 al 29 de marzo de 2020 | 3 | idem |
| 25 de octubre al 1 de noviembre de 2020 | 1 | idem |

Las semanas de octubre y noviembre no se ven en la tabla mensual (una semana
no mueve el maximo del mes). De 2005 a 2018 no hay ninguna semana asi. Los
criterios anuales igual se cumplen (2019: zona en 0 con 0,92 y acuerdo 98,9%;
2020: zona en 0 con 0,71 y acuerdo 98,5%).

**Calendario** (sin pendientes): 767 anuncios; Fed 8 por ano (7 en 2020); 29
con "practica de la Fed" (uno de ellos, "confirmada en el PDF de las minutas").

**Push: NO se hizo.** El control repetido cumple los criterios anuales, pero la
lista exacta de periodos fuera de alineacion no coincide con la decision: falta
que el grupo decida sobre 2019-2020. Opciones:
- (a, recomendada) marcar como fuera de alineacion exactamente esas 8 semanas
  (las de diferencia entre el cambio de hora de EE. UU. y el europeo en 2019 y
  2020) y excluirlas de la replica, igual que los 11 meses; sin corregirlas.
- (b) marcar los meses completos (2019-03, 2019-10, 2019-11, 2020-03,
  2020-10, 2020-11): mas simple, pero saca ~5 semanas alineadas por cada una
  desalineada en octubre y noviembre.
- (c) dejarlas dentro y declararlo: los criterios anuales se cumplen igual.

### Paso 3, regla de alineacion de HistData (decision del grupo, 2026-10-02)

**Decision.** Se excluye de la replica con HistData, sin corregirlo con
desfases calculados (el analisis principal, Dukascopy, no cambia):
1. **Semana con el reloj corrido**: la apertura del domingo y el cierre del
   viernes de HistData, en la misma semana, estan ambos corridos una hora
   respecto de Nueva York (60 +- 10 minutos, mismo signo;
   `CALIDAD_RELOJ_CORRIDO_MIN`, `CALIDAD_RELOJ_TOLERANCIA_MIN`).
2. **Mes fuera de alineacion**: su desfase con Dukascopy no es 0, medido
   despues de quitar las semanas del punto 1.
Las demas desviaciones (datos ralos que empiezan tarde, dias faltantes,
feriados) se informan y no se excluyen.

**Declaracion.** La regla se preciso despues de ver las tablas de calidad de
2003-2020 (solo horas de apertura y cierre semanales y la zona mes a mes;
ningun resultado), para separar un reloj corrido de un dato faltante. La
redaccion literal anterior ("toda semana cuya apertura o cierre no calce con
Nueva York") marcaba 54 semanas con 45 minutos de tolerancia y 297 sin
tolerancia (datos ralos de 2004-2005, feriados, cierres media hora antes), y
"todo mes con desfase distinto de 0", 13 meses (sumaba marzo de 2019 y de
2020 completos). **La regla se aplicara sin cambios al tramo sellado en la
Etapa 5.**

**Codigo** (commit `672781a`): las tolerancias y las dos listas en config.py
(`HISTDATA_SEMANAS_FUERA_DE_ALINEACION`, `HISTDATA_MESES_FUERA_DE_ALINEACION`);
el cargador excluye de la replica meses y semanas (`semana_de`, `en_semanas`);
el control de calidad aplica la regla en cada corrida
(`semanas_reloj_corrido`, `chequeo_zona_mensual` sin esas semanas) y verifica
que encuentre exactamente las dos listas. Tests: 327 pasan, 0 avisos.

**Verificacion (control completo, 2003-2020; 8 lecturas de validacion
anotadas):** la regla encuentra **exactamente las 8 semanas de 2019-2020**
(10, 17 y 24 de marzo y 27 de octubre de 2019; 8, 15 y 22 de marzo y 25 de
octubre de 2020) y **exactamente los 11 meses de 2003-2006**. Sin esas
semanas, marzo de 2019 y de 2020 quedan en desfase 0. El informe ya no tiene
el aviso. 46 semanas de HistData con desviaciones de 45 minutos o mas quedan
listadas en el informe, sin excluir.

**Resultado del control repetido** (todos los criterios cumplen):
- zona por ano: maximo en 0 los 18 anos (y en el barrido de +-15 h);
  correlacion 0,51-0,77 en 2003-2007 y 0,87-1,00 desde 2008;
- rupturas coincidentes: 91,6%-100% (todos >= 90%); a 2 minutos o menos,
  94%-100% desde 2012;
- integridad: sin cambios (Dukascopy 125 invalidas, 0,034% max.).

**Hallazgo (limite de la replica, no es un criterio de 3.3).** En 2019 y 2020
HistData coincide con el bid de Dukascopy: correlacion de los cambios de 1
minuto 1,00000 en todos los meses y extremos de franja iguales (diferencia
0,0 pips en la mediana y en el p95). En esos dos anos de validacion la replica
con HistData no es una fuente independiente (parece salir del mismo
proveedor). De 2015 a 2018 la correlacion es 0,99 y los extremos difieren 0,1
pips. Se declara en el resumen para la N1; el grupo decidira si lo agrega a
las limitaciones del pre-registro (8.7 ya dice que la segunda fuente solo
tiene bid).

**Resumen para la Entrega N1**: `resultados/calidad_resumen_N1.md` (no se
versiona), con la linea de que HistData viene en hora de Nueva York con
horario de verano y se corrigio, la regla de alineacion con las 8 semanas y
los 11 meses, y el limite de 2019-2020.

**Hash del paso 3**: `81edd05` (`punto G (paso 3): regla de alineacion verificada (8 semanas y 11 meses exactos), control de calidad repetido y bitacora`). Push de `etapa-datos` a `origin`.
