# -*- coding: utf-8 -*-
"""
CONFIGURACION UNICA del proyecto.

Aqui vive TODO parametro que pueda cambiar un resultado. Ningun otro archivo
puede inventar un numero: si un modulo necesita un valor, lo lee de aqui.

Marca usada en los comentarios:
  # PARAMETRO DE SIMULACION -> solo afecta al mercado artificial de pruebas;
                              NO se pre-registra (los resultados se normalizan
                              por sigma_ref, asi que la escala no importa).

Todo lo demas quedo fijado en el punto F y va al pre-registro
(registro/prerregistro.md). Hasta el punto E habia una segunda marca, POR
DECIDIR, para los valores provisionales: el grupo los fijo todos en el punto F
(registro/decisiones_F.md) y la marca ya no se usa.
"""

import os
from types import SimpleNamespace


def copia(**cambios):
    """
    Una copia de esta configuracion con los cambios que se pidan.

    Sirve para correr variantes (otro UMBRAL_PIPS, otro NOTICIA_MODO) sin tocar
    el archivo ni contaminar al resto del programa, y para pasar la
    configuracion a procesos paralelos, que necesitan algo que se pueda
    empaquetar y un modulo no lo es.
    """
    base = {k: v for k, v in globals().items() if k.isupper()}
    base.update(cambios)
    return SimpleNamespace(**base)


# =============================================================================
#  1. CORTES DE MUESTRA
#     El tramo SELLADO no se descarga ni se mira hasta la etapa final.
# =============================================================================
DESARROLLO_HASTA = "2016-12-31"              # fin del tramo de desarrollo (se explora libremente)
VALIDACION = ("2017-01-01", "2020-12-31")    # tramo de confirmacion, se abre una sola vez
SELLADO = ("2021-01-01", "2026-08-31")       # tramo sellado, no se descarga hasta el final

# =============================================================================
#  2. FRANJAS HORARIAS
# =============================================================================
ZONA = "Europe/London"                       # zona horaria que define las franjas (con horario de verano)
LIMITES_HORAS = [0, 6, 12, 18, 24]           # cortes de las 4 franjas de 6 horas en hora local de Londres

# =============================================================================
#  3. DATOS Y COBERTURA
# =============================================================================
PIP = 0.0001                                 # tamano de un pip en EUR/USD
COBERTURA_MIN_REFERENCIA = 0.90              # minutos presentes / esperados exigidos a la franja de REFERENCIA
HUECO_CIERRE_MIN = 60                        # hueco de datos (minutos) a partir del cual se considera mercado cerrado
REFERENCIA_CRUZA_CIERRE = False              # False = si entre la franja k-1 y la k hay un cierre, la franja k no genera eventos

# =============================================================================
#  4. DETECCION DE EVENTOS
# =============================================================================
UMBRAL_MODO = "pips"                         # "pips" (principal) o "vol" (robustez: umbral proporcional a la volatilidad)
UMBRAL_PIPS = 1.0                            # penetracion minima del extremo, en pips, si UMBRAL_MODO == "pips"
UMBRAL_VOL = 1.0                             # umbral_precio = UMBRAL_VOL * sigma_ref * extremo_referencia, si UMBRAL_MODO == "vol"

M_SOSTENIDA_MIN = 15                         # minutos que debe aguantar la ruptura para considerarse sostenida
REGLA_SOSTENIDA = "sin_reingreso"            # "sin_reingreso" (ninguna barra vuelve dentro en (t, t+M]) o "fuera_en_t_mas_m" (solo se mira t+M)
VENTANA_REINGRESO_MIN = None                 # minutos maximos para buscar el reingreso; None = hasta el fin de la franja
EXCLUIR_BARRA_AMBIGUA = True                 # True = si una misma barra rompe los dos lados, esa franja no genera eventos

TIPOS_EVENTO = ("ruptura", "sostenida", "reingreso")   # tipos de evento que produce el motor

# =============================================================================
#  5. RESULTADOS (RETORNOS POSTERIORES)
# =============================================================================
HORIZONTES_MIN = [30, 60, 120]               # horizontes fijos en minutos para medir el retorno posterior
INCLUIR_FIN_FRANJA = True                    # True = agrega el horizonte variable "hasta el fin de la franja del evento"

DIAS_VOL_REF = 20                            # dias pasados validos usados para estimar sigma_ref (volatilidad de referencia)
DIAS_VOL_REF_MIN = 10                        # dias validos minimos; con menos, sigma_ref = NaN y el evento se descarta
TOLERANCIA_PRECIO_MIN = 2                    # si falta la barra que cierra en t, se acepta la ultima cerrada hasta 2 minutos antes

# Lista de horizontes tal como la usan resultados.py, nula.py e inferencia.py.
HORIZONTES = list(HORIZONTES_MIN) + (["fin_franja"] if INCLUIR_FIN_FRANJA else [])

# =============================================================================
#  6. MODERADORES (H3 y H4)
# =============================================================================
PASO_REDONDO = 0.0050                        # rejilla de numeros redondos (0.0050 = terminaciones 00 y 50)
RADIO_REDONDO_PIPS = 5                       # distancia maxima, en pips, para considerar el extremo "cerca de un numero redondo"
RADIO_EXTREMO_PREVIO_PIPS = 3                # distancia maxima, en pips, al extremo del dia de Londres anterior
DIA_PREVIO_MIN_COBERTURA = 0.50              # cobertura minima del dia de Londres anterior para que sus extremos cuenten
DIAS_COMPRESION = 20                         # dias pasados validos para la mediana del rango del mismo tipo de franja
DIAS_COMPRESION_MIN = 10                     # dias validos minimos; con menos, ratio_compresion = NaN
CORTE_COMPRESION = 0.75                      # ratio por debajo del cual la franja de referencia se considera comprimida
VENTANA_NOTICIAS_MIN = 60                    # minutos previos al evento en los que un anuncio macro cuenta como "noticia"
NOTICIA_MODO = "ventana"                     # "ventana" (principal) o "franja" (robustez: toda la franja con anuncio cuenta como tratada)

MODERADORES = ["cerca_redondo", "cerca_extremo_previo", "comprimida", "noticia"]  # regresores de la regresion
MODERADORES_PROBADOS = ["cerca_redondo", "cerca_extremo_previo", "comprimida"]    # los que se PRUEBAN (H3); noticia entra solo como control

# =============================================================================
#  7. HIPOTESIS NULA EMPAREJADA
# =============================================================================
NULA_REPETICIONES = 1000                     # repeticiones de la nula en las corridas normales
NULA_REPETICIONES_POTENCIA = 500             # repeticiones en el control positivo (mas rapido; se reporta el error de Monte Carlo)
NULA_DECILES_VOL = 10                        # grupos de volatilidad de referencia (20 dias) usados para emparejar
NULA_GRUPOS_VOL_RECIENTE = 3                 # grupos de volatilidad de los ultimos minutos usados para emparejar
VENTANA_VOL_RECIENTE_MIN = 60                # minutos previos con los que se mide la volatilidad reciente
MIN_BARRAS_VOL_RECIENTE = 30                 # barras minimas en esa ventana; con menos, el minuto va al grupo "sin dato"
PRINCIPAL_ESTUDENTIZADO = True               # True = el estadistico de H1 y H2 es el t de la media, no la media cruda

# =============================================================================
#  8. INFERENCIA Y PRUEBAS MULTIPLES
# =============================================================================
ALFA = 0.05                                  # nivel de la familia de moderadores (H3, calibrada) y del analisis secundario de H4
ALFA_ESTRICTO = 0.025                        # la alternativa que la regla del punto E puede elegir para la familia principal
ALFA_PRINCIPAL = 0.025                       # nivel de la familia principal (H1 y H2); lo fijo la regla del punto E, 2a parte: delta = 0 del bloque de 4 anos del control positivo (tasa por prueba 7,4% [5,5%-9,4%] con 0,05; ver bitacora)
REMUESTREOS_IC_MERCADOS = 10000              # remuestreos de MERCADOS para el intervalo de una tasa por prueba

# Holm sobre los p-valores de la nula emparejada, fijado en el punto E SIN mirar
# la curva de potencia. Romano-Wolf, tal como esta implementado, no es otra
# correccion del mismo test sino otro test (t de la regresion contra cero, a dos
# colas, sin la nula), asi que comparar potencias no decidia nada. Se sigue
# reportando como prueba SECUNDARIA, rotulada como lo que es.
CORRECCION_PRINCIPAL = "holm"
REPORTAR_AMBAS_CORRECCIONES = True           # True = toda tabla trae Holm y, como prueba secundaria, Romano-Wolf
TIPO_ERRORES = "cluster"                     # "cluster" (agrupado por fecha de Londres) o "HAC" (Newey-West)
# Newey-West, solo como contraste de H3: rezagos = piso(FACTOR * (n / 100) ** EXPONENTE),
# la regla de Newey y West (1994), con n = eventos de la celda en orden de tiempo.
NW_REZAGOS_FACTOR = 4
NW_REZAGOS_EXPONENTE = 2 / 9
RW_REPETICIONES = 1000                       # remuestreos de dias del bootstrap de Romano-Wolf

# Horizontes que se REPORTAN pero no confirman nada. El de 120 minutos salio de
# la familia principal porque en el control negativo rechaza entre el 14% y el
# 16% de las veces bajo la hipotesis nula: con esa tasa no sirve para confirmar.
# Se sigue informando en todas las tablas, con su medicion, no se esconde.
HORIZONTES_DESCRIPTIVOS = [120]

# Familia PRINCIPAL: H1 y H2. Cada prueba es (tipo, horizonte, cantidad, cola).
#   cola "mayor" = se espera continuacion (> 0);  "menor" = se espera reversion (< 0).
HORIZONTES_CONFIRMATORIOS = [h for h in HORIZONTES if h not in HORIZONTES_DESCRIPTIVOS]
FAMILIA_PRINCIPAL = (
    [("sostenida", h, "media", "mayor") for h in HORIZONTES_CONFIRMATORIOS]
    + [("reingreso", h, "media", "menor") for h in HORIZONTES_CONFIRMATORIOS]
)

# Familia MODERADORES: H3, confirmatoria. Cada prueba es (tipo, horizonte,
# coeficiente, cola).
#   La direccion esperada es la de la propuesta (los efectos se intensifican),
#   pero la prueba es a dos colas, que es la que se calibro; un efecto
#   significativo en sentido contrario se reporta como tal.
#   `noticia` NO esta aqui: se estima como control; los anuncios se miden en
#   FAMILIA_H4.
FAMILIA_MODERADORES = [
    (tipo, h, mod, "dos")
    for tipo in ("sostenida", "reingreso")
    for h in HORIZONTES
    for mod in MODERADORES_PROBADOS
]

# H4: el efecto de los anuncios macro, medido por inferencia de aleatorizacion
# y no por un coeficiente de la regresion (ver motor/nula.py). Desde el punto F
# es un analisis SECUNDARIO pre-especificado: se corre igual en cada tramo y se
# reporta con estimacion, IC y p-valor, pero NO confirma nada. Con 4 anos no
# esta calibrada (10,8% por prueba con alfa 0,05, exceso simetrico) ni tiene
# potencia (ver registro/decisiones_F.md).
#   Una cola "mayor": H4 se operacionaliza como la diferencia, MAS
#   continuacion con anuncio que sin el.
FAMILIA_H4 = [
    (tipo, h, "dif_noticia", "mayor")
    for tipo in ("sostenida", "reingreso")
    for h in HORIZONTES
]
MIN_DIAS_TRATADOS = 15                       # dias distintos con evento "con anuncio" para que la prueba de H4 tenga p-valor; con menos, solo estimacion
H4_ESTUDENTIZADO = True                      # True = el estadistico principal es el t; la version sin estudentizar se reporta como comparacion

# "ruptura" queda como tipo DESCRIPTIVO: se reporta a dos colas, fuera de las
# familias corregidas, porque no corresponde a ninguna hipotesis direccional.
TIPOS_DESCRIPTIVOS = ("ruptura",)

# =============================================================================
#  8b. COSTOS DE EJECUCION (criterio de paso a la Etapa 4 y H5)
#      El efecto neto se calcula evento por evento con el bid/ask observado de
#      Dukascopy, esta comision y una vela de latencia en la entrada.
# =============================================================================
COMISION_USD_POR_MILLON_LADO = 35            # tarifa publicada de Dukascopy, tramo mas bajo, cobrada al abrir y al cerrar (0,70 pb ida y vuelta)
COMISIONES_SENSIBILIDAD = [0, 70]            # comisiones (USD por millon por lado) con que se repite el efecto neto, como sensibilidad declarada
LATENCIA_VELAS = 1                           # velas entre la senal (cierre de la barra del evento) y la entrada

# =============================================================================
#  9. ALEATORIEDAD
# =============================================================================
SEMILLA = 20260916                           # semilla maestra; cada corrida deriva la suya de esta

# =============================================================================
#  10. SIMULACION (mercado artificial para los controles)
#      Nada de esta seccion se pre-registra: solo define el banco de pruebas.
# =============================================================================
ANIOS = 3                                    # duracion de cada mercado simulado del control negativo
MERCADOS_CONTROL_NEGATIVO = 50               # mercados independientes del control negativo
TAMANOS_EFECTO = [0, 0.01, 0.02, 0.03, 0.05, 0.10, 0.20]  # deltas inyectados en el control positivo (en unidades de retorno normalizado)
ANIOS_POTENCIA = [4, 6, 13]                  # duraciones evaluadas: 4 ~ validacion, 6 ~ sellado, 13 ~ desarrollo
# Mercados por duracion. 4 anos es la duracion que CONFIRMA: con 200 mercados
# da un efecto minimo detectable preciso y, en delta = 0, la medicion del
# tamano que usa la regla de ALFA_PRINCIPAL.
MERCADOS_POR_DURACION = {4: 200, 6: 100, 13: 30}
ANIOS_REGLA_ALFA = 4                         # duracion cuyo punto delta = 0 alimenta la regla de ALFA_PRINCIPAL
MINUTOS_MAX_CORRIDA = 60                     # si la estimacion pasa de esto, se recortan primero los mercados de la duracion mas larga
ALFAS_POTENCIA = [ALFA, ALFA_ESTRICTO]       # niveles con que se DESCRIBE la curva (la decision usa ALFA_PRINCIPAL)
POTENCIA_OBJETIVO = 0.80                     # potencia con la que se define el efecto minimo detectable
MERCADOS_PILOTO = 2                          # mercados del piloto (por duracion) que estiman el tiempo total antes de la corrida larga

# Diseno D (curva): el efecto se suma al retorno normalizado de cada evento, asi
# que cada delta extra cuesta casi nada. La curva se evalua tambien sobre esta
# grilla fina, para que el efecto minimo detectable no dependa de interpolar
# entre puntos lejanos de TAMANOS_EFECTO. Es resolucion de calculo, no una
# decision del estudio.
GRILLA_POTENCIA = [round(0.005 * k, 3) for k in range(41)]   # de 0 a 0,20 cada 0,005

# Control B (descriptivo, no decide nada): el efecto se inyecta en los PRECIOS
# y se itera inyectar -> detectar hasta que los eventos que reciben el efecto
# son los que el motor detecta. Mide cuanto de un efecto de precio llega a las
# celdas cuando H1 y H2 actuan a la vez.
DELTAS_CONTROL_B = [0.05, 0.10]              # tamanos inyectados en precios
ANIOS_CONTROL_B = 4                          # duracion de cada mercado
MERCADOS_CONTROL_B = 10                      # pocos: el delta realizado promedia miles de eventos por mercado
# Escenarios de B: que tipos reciben el efecto. En los escenarios "solo" se
# mide tambien la celda NO inyectada: cuanto se le contagia por la
# superposicion de sostenidas y reingresos.
ESCENARIOS_CONTROL_B = {
    "ambos": ["sostenida", "reingreso"],
    "solo_sostenidas": ["sostenida"],
    "solo_reingresos": ["reingreso"],
}
ITERACIONES_MAX_CONTROL_B = 50               # tope de la iteracion; si no converge, se informa (en los ensayos: 4 a 15)

# Potencia de H3 y H4 (punto F). Mismo principio que el diseno D: el mercado
# queda limpio y el efecto se suma al retorno normalizado, aqui solo al
# SUBGRUPO que la hipotesis senala (moderador encendido en H3, "con anuncio" en
# H4). Se mide en la duracion que confirma y con el calendario de la lista
# cerrada. Las grillas son mas anchas que GRILLA_POTENCIA porque una diferencia
# entre subgrupos necesita mucho mas efecto que una media de celda.
ANIOS_POTENCIA_MODERADORES = 4
MERCADOS_POTENCIA_MODERADORES = 200
GRILLA_POTENCIA_H3 = [round(0.01 * k, 3) for k in range(61)]    # de 0 a 0,60 cada 0,01
GRILLA_POTENCIA_H4 = [round(0.02 * k, 3) for k in range(101)]   # de 0 a 2,00 cada 0,02

# Anexo de sensibilidad (pendiente del punto B para el punto F): cuantas
# franjas rompen, aguantan y reingresan con otros umbrales y otros M. Solo
# describe los mercados simulados; no decide nada por si solo.
SENSIBILIDAD_UMBRAL_PIPS = [1.0, 3.0, 5.0]
SENSIBILIDAD_UMBRAL_VOL = [1.0, 2.0, 3.0]
SENSIBILIDAD_M = [5, 15, 30]
MERCADOS_SENSIBILIDAD = 5
ANIOS_SENSIBILIDAD = 4

# Variantes de robustez que el control negativo puede correr cambiando solo
# config (punto F): `python -m experimentos.control_negativo --variante NOMBRE`.
# Ojo: el simulador tambien ancla su perfil horario a ZONA, asi que en
# "particion_utc" el mercado simulado sigue el reloj UTC.
VARIANTES_CONTROL_NEGATIVO = {
    "umbral_vol": {"UMBRAL_MODO": "vol"},
    "particion_utc": {"ZONA": "UTC"},
}

# El piso: el sesgo propio de los eventos, medido sin la nula en muchos mercados.
MERCADOS_PISO = 200                          # mercados sin ningun patron para medir el piso con precision
ANIOS_PISO = 3                               # duracion de cada uno

# Traduccion de unidades normalizadas a pips. Es un orden de magnitud: la
# traduccion definitiva se hara evento por evento con el sigma_ref de los datos
# reales.
MERCADOS_UNIDADES = 20                       # mercados por volatilidad con los que se mide el factor pips / unidad
VOLS_TRADUCCION = [0.05, 0.07, 0.10]         # volatilidades anuales con que se repite la traduccion  # PARAMETRO DE SIMULACION
COSTOS_IDA_VUELTA_PIPS = [0.5, 1.0, 2.0]     # grilla de LECTURA de la curva de potencia contra un costo, en pips (el criterio de paso usa el costo medido evento por evento)

VOL_ANUAL_SIMULACION = 0.07                  # volatilidad anual del mercado simulado  # PARAMETRO DE SIMULACION
PRECIO_INICIAL = 1.10                        # precio medio inicial  # PARAMETRO DE SIMULACION
SUBPASOS_POR_MINUTO = 6                      # subpasos del paseo aleatorio dentro de cada minuto (para high y low)  # PARAMETRO DE SIMULACION
SPREAD_BASE_PIPS = 0.2                       # spread base bid-ask, en pips  # PARAMETRO DE SIMULACION
SPREAD_FACTOR_NOCTURNO = 3.0                 # multiplicador del spread entre 21:00 y 23:00 UTC  # PARAMETRO DE SIMULACION
SPREAD_HORAS_NOCTURNAS = (21, 23)            # franja UTC con spread ampliado  # PARAMETRO DE SIMULACION
AR1_VOL_DIARIA = 0.95                        # persistencia del regimen de volatilidad (AR(1) diario en log)  # PARAMETRO DE SIMULACION
AR1_SIGMA_DIARIA = 0.15                      # desviacion del choque diario del regimen de volatilidad  # PARAMETRO DE SIMULACION
NOTICIA_FACTOR_VOL = 3.0                     # multiplicador de volatilidad al momento del anuncio  # PARAMETRO DE SIMULACION
NOTICIA_DURACION_MIN = 5                     # minutos que dura el efecto del anuncio  # PARAMETRO DE SIMULACION
# Que anuncios trae el calendario simulado. El de los puntos D y E es el de
# empleo, IPC y FOMC (32 al ano). El punto F agrega el BCE (8 al ano) para
# medir con la frecuencia de la lista cerrada de anuncios del pre-registro; el
# calendario por defecto no cambia, asi D y E se siguen reproduciendo tal cual.
ANUNCIOS_SIMULADOS = ("empleo", "ipc", "fomc")                        # PARAMETRO DE SIMULACION
ANUNCIOS_SIMULADOS_LISTA_CERRADA = ("empleo", "ipc", "fomc", "bce")  # PARAMETRO DE SIMULACION
ZONA_MERCADO = "America/New_York"            # zona que define la semana de mercado (domingo 17:00 a viernes 17:00)  # PARAMETRO DE SIMULACION

# Multiplicador de volatilidad por hora de Londres (0..23): bajo en Asia, sube
# en la apertura de Londres, maximo entre 13:00 y 16:00, bajo tras las 18:00.
PERFIL_HORARIO_VOL = [
    0.55, 0.50, 0.50, 0.55, 0.60, 0.70,      # 00-05  madrugada / Asia
    0.90, 1.10, 1.25, 1.20, 1.10, 1.05,      # 06-11  apertura de Londres
    1.15, 1.60, 1.70, 1.60, 1.35, 1.10,      # 12-17  solape Londres-Nueva York
    0.80, 0.70, 0.65, 0.60, 0.60, 0.55,      # 18-23  tarde y cierre
]                                            # PARAMETRO DE SIMULACION

# =============================================================================
#  11. AUDITORIA CAUSAL (prueba de truncamiento)
#      Los cortes al azar casi nunca caen en el instante de un evento, que es
#      justo donde una fuga de un minuto cambia algo. Por eso la mitad de los
#      cortes se ancla en instantes de eventos reales.
# =============================================================================
CORTES_AUDITORIA_EVENTO = 20                 # cortes en el instante EXACTO de un evento sorteado (mezcla los tres tipos)
CORTES_AUDITORIA_MITAD_FRANJA = 10           # cortes en la mitad de una franja que genero eventos
CORTES_AUDITORIA_AZAR = 10                   # cortes en un minuto cualquiera, despues del primer evento
ANIOS_AUDITORIA = 1                          # duracion del mercado simulado sobre el que se corre la auditoria

# =============================================================================
#  12. DATOS REALES (punto G): rutas, descarga, candado y control de calidad
#      Los precios viven FUERA del repositorio. En git solo va el manifiesto
#      (registro/manifiesto_datos.csv) y el registro de lecturas
#      (registro/aperturas.md). Toda lectura de precios pasa por
#      fuentes/cargador.py.
# =============================================================================
RUTA_CRUDOS = os.environ.get(                # archivos tal como se bajaron o exportaron, sin modificar
    "CUARTINHOS_CRUDOS", r"C:\WorkSpace\20_Data\Raw\Cuartinhos_EURUSD")
RUTA_PROCESADOS = os.environ.get(            # parquet en UTC, uno por fuente y ano
    "CUARTINHOS_PROCESADOS", r"C:\WorkSpace\20_Data\Processed\Cuartinhos_EURUSD")
FUENTES = ("dukascopy", "histdata")          # dukascopy = analisis principal (precio medio); histdata = control y replica (bid)

ETIQUETA_PRERREGISTRO = "prerregistro-v1"    # sin esta etiqueta, el cargador solo entrega datos al modulo de calidad
DESCARGA_TOPE = SELLADO[0]                   # nada desde esta fecha se descarga ni se convierte hasta la Etapa 5

HISTDATA_PAGINA = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/eurusd/{anio}"
HISTDATA_POST = "https://www.histdata.com/get.php"   # el formulario de la pagina pide el archivo con un token por pagina
HISTDATA_ANIOS = (2003, 2020)                # anos completos que se bajan (primer ano de Dukascopy hasta el fin de validacion)
HISTDATA_HORAS_A_UTC = 5                     # solo si HISTDATA_ZONA es None: UTC = hora del archivo + 5 h (EST fijo, lo que dice la documentacion de HistData)
# Decision del grupo (punto G, paso 3): HistData viene en hora de Nueva York CON
# horario de verano, contra lo que dice su documentacion. El control de calidad
# lo mostro (zona en +60 minutos todos los anos con EST fijo). Es un error de
# manejo de la segunda fuente (pre-registro 3.3), no un cambio de definiciones.
HISTDATA_ZONA = "America/New_York"
# Meses (UTC) en que HistData sigue sin alinearse con Dukascopy aun con la hora
# de Nueva York: mayo a julio de 2003 vinieron en EST fijo y los demas estan
# corridos 1 o 2 minutos. NO se corrigen con desfases calculados: quedan fuera
# de la replica con HistData (el cargador no los entrega para analisis). Los
# encontro el control de calidad mes a mes (fuentes/calidad.py).
HISTDATA_MESES_FUERA_DE_ALINEACION = (
    "2003-05", "2003-06", "2003-07", "2003-10", "2003-11", "2003-12",
    "2004-02", "2004-03", "2004-06", "2004-11", "2006-10",
)
PRECIO_PLAUSIBLE = (0.5, 2.5)                # el EUR/USD nunca salio de este rango: un precio fuera delata una linea mal leida
DESCARGA_PAUSA_SEG = 10                      # pausa entre pedidos a un mismo servidor
DESCARGA_REINTENTOS = 5                      # intentos por archivo; la espera crece con cada intento
DESCARGA_TIMEOUT_SEG = 120                   # tiempo maximo de un pedido

# Control de calidad (pre-registro, 3.3). Solo usa rupturas: si hay, direccion y minuto.
CALIDAD_MAX_INVALIDAS = 0.001                # fraccion maxima de barras invalidas por ano y fuente (0,1%)
CALIDAD_DESFASE_MAX_MIN = 120                # desfases de -120 a +120 minutos en la correlacion entre fuentes
CALIDAD_DESFASE_DIAGNOSTICO_MIN = 900        # barrido amplio (+-15 h), solo diagnostico: encuentra una zona equivocada que caiga fuera de +-120
CALIDAD_ZONA_NUEVA_YORK = "America/New_York" # el FX abre el domingo y cierra el viernes a las 17:00 de Nueva York
CALIDAD_CORTE_SEMANAL_NY = 17                # hora de Nueva York de la apertura del domingo y del cierre del viernes
CALIDAD_APERTURA_DOMINGO_UTC = (21, 23)      # la primera barra de la semana tiene que abrir entre estas horas UTC
CALIDAD_CIERRE_VIERNES_UTC = (20, 22)        # la ultima barra del viernes tiene que abrir entre estas horas UTC
CALIDAD_SPREAD_ALTO_PIPS = 10                # spread por encima del cual la barra se reporta (no se borra)
CALIDAD_ACUERDO_MIN = 0.90                   # acuerdo minimo en "hay ruptura y en que direccion"
CALIDAD_ACUERDO_ALERTA = 0.80                # por debajo de esto se detiene la etapa de datos
CALIDAD_TOLERANCIA_HORA_MIN = 2              # diferencia maxima de hora (minutos) para contar dos rupturas como simultaneas
CALIDAD_MARGEN_DIAS = 3                      # dias del ano anterior que se leen como contexto (referencia, primera semana); no se cuentan

# Lista cerrada de anuncios (pre-registro 4.8): calendario/anuncios.csv, armado
# desde las fuentes oficiales por fuentes/calendario.py. No tiene precios.
CALENDARIO_ANIOS = (2003, 2020)              # anos que cubre el calendario (los de los datos descargados)
CALENDARIO_PAUSA_SEG = 3                     # pausa entre pedidos a las fuentes del calendario
ZONA_BCE = "Europe/Berlin"                   # zona de la hora del BCE (CET / CEST)
HORA_BLS = (8, 30)                           # hora (ET) de Employment Situation y CPI; se verifica en una muestra de comunicados
VERIFICACION_BLS_ANIOS = (2003, 2008, 2013, 2018)   # anos de la muestra (primer comunicado del ano de cada serie, mas los atrasados de oct-2013)
HORA_BCE = (13, 45)                          # regla publicada del BCE para sus decisiones (CET), hasta el 20-07-2022
HORA_BCE_DESDE_2022 = ("2022-07-21", (14, 15))   # desde esa fecha, 14:15 CET
# Comunicados del FOMC anteriores a 2009 cuya hora no dicen ni el comunicado ni
# las minutas (2003 a junio de 2006, y el del 25-06-2008, con minutas solo en
# PDF): se usa la practica de la Fed en esos anos, 2:15 p.m. ET (decision del
# grupo). El PDF de las minutas del 25-06-2008 lo confirma ("to be released at
# 2:15 p.m.").
FOMC_HORA_PRACTICA = (14, 15)
FOMC_PRACTICA_HASTA = "2008-12-31"
FOMC_HORA_CONFIRMADA_EN_PDF = ("2008-06-25",)   # minutas en PDF leidas para confirmar la hora
