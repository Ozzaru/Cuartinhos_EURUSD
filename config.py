# -*- coding: utf-8 -*-
"""
CONFIGURACION UNICA del proyecto.

Aqui vive TODO parametro que pueda cambiar un resultado. Ningun otro archivo
puede inventar un numero: si un modulo necesita un valor, lo lee de aqui.

Marcas usadas en los comentarios:
  # POR DECIDIR            -> valor provisional; el grupo debe fijarlo antes
                              de pre-registrar.
  # PARAMETRO DE SIMULACION -> solo afecta al mercado artificial de pruebas;
                              NO se pre-registra (los resultados se normalizan
                              por sigma_ref, asi que la escala no importa).
"""

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
COBERTURA_MIN_REFERENCIA = 0.90              # minutos presentes / esperados exigidos a la franja de REFERENCIA  # POR DECIDIR
HUECO_CIERRE_MIN = 60                        # hueco de datos (minutos) a partir del cual se considera mercado cerrado
REFERENCIA_CRUZA_CIERRE = False              # False = si entre la franja k-1 y la k hay un cierre, la franja k no genera eventos

# =============================================================================
#  4. DETECCION DE EVENTOS
# =============================================================================
UMBRAL_MODO = "pips"                         # "pips" (principal) o "vol" (robustez: umbral proporcional a la volatilidad)  # POR DECIDIR
UMBRAL_PIPS = 1.0                            # penetracion minima del extremo, en pips, si UMBRAL_MODO == "pips"  # POR DECIDIR
UMBRAL_VOL = 1.0                             # umbral_precio = UMBRAL_VOL * sigma_ref * extremo_referencia, si UMBRAL_MODO == "vol"  # POR DECIDIR

M_SOSTENIDA_MIN = 15                         # minutos que debe aguantar la ruptura para considerarse sostenida  # POR DECIDIR
REGLA_SOSTENIDA = "sin_reingreso"            # "sin_reingreso" (ninguna barra vuelve dentro en (t, t+M]) o "fuera_en_t_mas_m" (solo se mira t+M)  # POR DECIDIR
VENTANA_REINGRESO_MIN = None                 # minutos maximos para buscar el reingreso; None = hasta el fin de la franja  # POR DECIDIR
EXCLUIR_BARRA_AMBIGUA = True                 # True = si una misma barra rompe los dos lados, esa franja no genera eventos

TIPOS_EVENTO = ("ruptura", "sostenida", "reingreso")   # tipos de evento que produce el motor

# =============================================================================
#  5. RESULTADOS (RETORNOS POSTERIORES)
# =============================================================================
HORIZONTES_MIN = [30, 60, 120]               # horizontes fijos en minutos para medir el retorno posterior
INCLUIR_FIN_FRANJA = True                    # True = agrega el horizonte variable "hasta el fin de la franja del evento"
HORIZONTE_PRINCIPAL = 60                     # horizonte unico al que se podria reducir la familia principal  # POR DECIDIR

DIAS_VOL_REF = 20                            # dias pasados validos usados para estimar sigma_ref (volatilidad de referencia)
DIAS_VOL_REF_MIN = 10                        # dias validos minimos; con menos, sigma_ref = NaN y el evento se descarta  # POR DECIDIR
TOLERANCIA_PRECIO_MIN = 2                    # si falta la barra que cierra en t, se acepta la ultima cerrada hasta 2 minutos antes  # POR DECIDIR

# Lista de horizontes tal como la usan resultados.py, nula.py e inferencia.py.
HORIZONTES = list(HORIZONTES_MIN) + (["fin_franja"] if INCLUIR_FIN_FRANJA else [])

# =============================================================================
#  6. MODERADORES (H3 y H4)
# =============================================================================
PASO_REDONDO = 0.0050                        # rejilla de numeros redondos (0.0050 = terminaciones 00 y 50)  # POR DECIDIR
RADIO_REDONDO_PIPS = 5                       # distancia maxima, en pips, para considerar el extremo "cerca de un numero redondo"  # POR DECIDIR
RADIO_EXTREMO_PREVIO_PIPS = 3                # distancia maxima, en pips, al extremo del dia de Londres anterior  # POR DECIDIR
DIA_PREVIO_MIN_COBERTURA = 0.50              # cobertura minima del dia de Londres anterior para que sus extremos cuenten  # POR DECIDIR
DIAS_COMPRESION = 20                         # dias pasados validos para la mediana del rango del mismo tipo de franja
DIAS_COMPRESION_MIN = 10                     # dias validos minimos; con menos, ratio_compresion = NaN  # POR DECIDIR
CORTE_COMPRESION = 0.75                      # ratio por debajo del cual la franja de referencia se considera comprimida  # POR DECIDIR
VENTANA_NOTICIAS_MIN = 60                    # minutos previos al evento en los que un anuncio macro cuenta como "noticia"  # POR DECIDIR
NOTICIA_MODO = "ventana"                     # "ventana" (principal) o "franja" (robustez: toda la franja con anuncio cuenta como tratada)

MODERADORES = ["cerca_redondo", "cerca_extremo_previo", "comprimida", "noticia"]  # regresores de la regresion
MODERADORES_PROBADOS = ["cerca_redondo", "cerca_extremo_previo", "comprimida"]    # los que se PRUEBAN (H3); noticia entra solo como control

# =============================================================================
#  7. HIPOTESIS NULA EMPAREJADA
# =============================================================================
NULA_REPETICIONES = 1000                     # repeticiones de la nula en las corridas normales
NULA_REPETICIONES_POTENCIA = 500             # repeticiones en el control positivo (mas rapido; se reporta el error de Monte Carlo)
NULA_DECILES_VOL = 10                        # numero de grupos de volatilidad usados para emparejar

# =============================================================================
#  8. INFERENCIA Y PRUEBAS MULTIPLES
# =============================================================================
ALFA = 0.05                                  # nivel de significancia
CORRECCION_PRINCIPAL = "holm"                # provisional; se decide en el punto E comparando POTENCIA, no tamano  # POR DECIDIR
REPORTAR_AMBAS_CORRECCIONES = True           # True = toda tabla trae Holm y Romano-Wolf, para no elegir a ciegas
TIPO_ERRORES = "cluster"                     # "cluster" (agrupado por fecha de Londres) o "HAC" (Newey-West)
RW_REPETICIONES = 1000                       # remuestreos de dias del bootstrap de Romano-Wolf

# Familia PRINCIPAL: H1 y H2. Cada prueba es (tipo, horizonte, cantidad, cola).
#   cola "mayor" = se espera continuacion (> 0);  "menor" = se espera reversion (< 0).
FAMILIA_PRINCIPAL = (
    [("sostenida", h, "media", "mayor") for h in HORIZONTES]
    + [("reingreso", h, "media", "menor") for h in HORIZONTES]
)

# Familia MODERADORES: H3. Cada prueba es (tipo, horizonte, coeficiente, cola).
#   Dos colas: el signo del efecto moderador no se pre-especifica.
#   `noticia` NO esta aqui: se estima como control pero se prueba en FAMILIA_H4.
FAMILIA_MODERADORES = [
    (tipo, h, mod, "dos")
    for tipo in ("sostenida", "reingreso")
    for h in HORIZONTES
    for mod in MODERADORES_PROBADOS
]

# Familia H4: el efecto de los anuncios macro, medido por inferencia de
# aleatorizacion y no por un coeficiente de la regresion (ver motor/nula.py).
#   Una cola "mayor": H4 predice MAS continuacion cuando hay anuncio.
FAMILIA_H4 = [
    (tipo, h, "dif_noticia", "mayor")
    for tipo in ("sostenida", "reingreso")
    for h in HORIZONTES
]
MIN_DIAS_TRATADOS = 15                       # dias distintos con evento "con anuncio" para que la prueba de H4 entre a la familia  # POR DECIDIR
H4_ESTUDENTIZADO = True                      # True = el estadistico principal es el t; la version sin estudentizar se reporta como comparacion

# "ruptura" queda como tipo DESCRIPTIVO: se reporta a dos colas, fuera de las
# familias corregidas, porque no corresponde a ninguna hipotesis direccional.
TIPOS_DESCRIPTIVOS = ("ruptura",)

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
TAMANOS_EFECTO = [0, 0.02, 0.05, 0.10, 0.20] # deltas inyectados en el control positivo (en unidades de retorno normalizado)
ANIOS_POTENCIA = [4, 13]                     # duraciones evaluadas: 4 ~ validacion, 13 ~ desarrollo (6 ~ sellado si el tiempo lo permite)
REPETICIONES_POTENCIA = 30                   # mercados por combinacion (delta, duracion)
MERCADOS_PILOTO = 3                          # mercados del piloto que estima el tiempo total antes de la corrida larga

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
FOMC_POR_ANIO = 8                            # reuniones FOMC simuladas por ano  # PARAMETRO DE SIMULACION
ZONA_MERCADO = "America/New_York"            # zona que define la semana de mercado (domingo 17:00 a viernes 17:00)  # PARAMETRO DE SIMULACION

# Multiplicador de volatilidad por hora de Londres (0..23): bajo en Asia, sube
# en la apertura de Londres, maximo entre 13:00 y 16:00, bajo tras las 18:00.
PERFIL_HORARIO_VOL = [
    0.55, 0.50, 0.50, 0.55, 0.60, 0.70,      # 00-05  madrugada / Asia
    0.90, 1.10, 1.25, 1.20, 1.10, 1.05,      # 06-11  apertura de Londres
    1.15, 1.60, 1.70, 1.60, 1.35, 1.10,      # 12-17  solape Londres-Nueva York
    0.80, 0.70, 0.65, 0.60, 0.60, 0.55,      # 18-23  tarde y cierre
]                                            # PARAMETRO DE SIMULACION
