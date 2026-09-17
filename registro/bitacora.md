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
