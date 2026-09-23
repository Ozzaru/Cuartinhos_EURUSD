# -*- coding: utf-8 -*-
"""
RESULTADOS — volatilidad de referencia y retornos posteriores al evento.

Dos piezas:

1. `sigma_por_franja`: la volatilidad tipica de un minuto en ese tipo de franja,
   estimada SOLO con dias anteriores. Es la vara con la que se normalizan los
   retornos, y tambien el umbral cuando se usa el modo "vol".

2. `agregar_retornos`: lo que pasa DESPUES del evento. Aqui si se mira el
   futuro, porque el futuro es justamente lo que se quiere medir. Lo que nunca
   puede pasar es que este archivo influya en la deteccion de eventos.

Convencion de signo: el retorno se multiplica por la direccion de la ruptura.
Positivo = el precio SIGUE en la direccion de la ruptura. Negativo = se devuelve.

Precio en un instante t: es el mid_close de la barra que CIERRA en t, o sea la
barra de indice t - 1 minuto. Si esa barra falta, se acepta la ultima que haya
cerrado dentro de los TOLERANCIA_PRECIO_MIN minutos previos; si tampoco hay,
queda NaN. Nunca se mira hacia adelante para rellenar.
"""
import numpy as np
import pandas as pd

from . import franjas, tiempo


def precio_en(barras, t_ns, cfg, tolerancia_min=None):
    """
    Precio medio en el instante t (ver la regla en el docstring del modulo).

    `tolerancia_min` permite exigir la barra exacta (0). La deteccion de
    eventos lo usa asi: la tolerancia es una comodidad para MEDIR resultados,
    no para declarar que un evento ocurrio.
    """
    tolerancia = cfg.TOLERANCIA_PRECIO_MIN if tolerancia_min is None else tolerancia_min
    j = barras.indice_al_cierre(t_ns, tolerancia)
    j = np.asarray(j)
    seguro = np.maximum(j, 0)
    return np.where(j >= 0, barras.mid_c[seguro], np.nan)


def _ventana_pasada(valores, valido, n_ventana, n_min, como):
    """
    Para cada fila, el resumen de las ultimas `n_ventana` filas VALIDAS que
    vinieron ANTES de ella. La fila actual nunca entra.

    Esta es la trampa clasica de pandas: `rolling()` incluye la fila actual. Aqui
    el corrimiento es explicito: se cuenta cuantas filas validas hubo
    estrictamente antes y se lee el acumulado en esa posicion.

    `como` es "sum" o "median".
    """
    valores = np.asarray(valores, dtype=float)
    valido = np.asarray(valido, dtype=bool)
    salida = np.full(len(valores), np.nan)

    pos_validas = np.flatnonzero(valido)
    if pos_validas.size == 0:
        return salida

    serie = pd.Series(valores[pos_validas]).rolling(n_ventana, min_periods=n_min)
    acumulado = (serie.sum() if como == "sum" else serie.median()).to_numpy()

    # cuantas filas validas hay ESTRICTAMENTE antes de cada fila
    antes = np.concatenate([[0], np.cumsum(valido)[:-1]])
    hay = antes > 0
    salida[hay] = acumulado[antes[hay] - 1]
    return salida


def _insumos_de_volatilidad(barras, cal):
    """
    Por franja: suma de retornos logaritmicos al cuadrado y cuantos son.

    Solo cuenta pares de barras consecutivas de verdad (un minuto de distancia)
    y dentro de la misma franja: asi ningun hueco de datos ni ningun salto de
    fin de semana se cuela como si fuera un movimiento de un minuto.
    """
    n = len(cal)
    if len(barras) < 2:
        return np.zeros(n), np.zeros(n, dtype=int)

    pos = np.searchsorted(cal["inicio_ns"].to_numpy(), barras.apertura_ns, side="right") - 1
    log_mid = np.log(barras.mid_c)
    ret = np.diff(log_mid)
    contiguo = np.diff(barras.apertura_ns) == tiempo.NS_MIN
    misma_franja = pos[1:] == pos[:-1]
    sirve = contiguo & misma_franja

    tabla = pd.DataFrame({"pos": pos[1:], "sq": np.where(sirve, ret ** 2, 0.0),
                          "n": sirve.astype(int)})
    agregado = tabla.groupby("pos").agg(sq=("sq", "sum"), n=("n", "sum")).reindex(range(n))
    return (agregado["sq"].fillna(0.0).to_numpy(float),
            agregado["n"].fillna(0).to_numpy(int))


def volatilidad_reciente(barras, cfg):
    """
    Volatilidad realizada de los ultimos minutos, barra por barra.

    Para el instante en que cierra la barra i, se mide con los retornos de 1
    minuto de las ultimas VENTANA_VOL_RECIENTE_MIN barras terminando en la i.
    Todas esas barras ya cerraron en ese instante, asi que es informacion
    disponible: no mira ni un minuto hacia adelante.

    Es distinta de `sigma_por_franja`, que resume veinte dias. Esta captura si
    el mercado viene movido AHORA, que es justo lo que distingue a un evento de
    un minuto cualquiera: un reingreso ocurre despues de una expansion, asi que
    por construccion llega con la volatilidad reciente alta.

    Los retornos que cruzan un hueco de datos o un cierre de mercado no cuentan.
    Si en la ventana no quedan al menos MIN_BARRAS_VOL_RECIENTE retornos
    validos, el resultado es NaN.
    """
    n = len(barras)
    if n < 2:
        return np.full(n, np.nan)

    ret = np.zeros(n)
    valido = np.zeros(n, dtype=bool)
    contiguo = np.diff(barras.apertura_ns) == tiempo.NS_MIN
    ret[1:] = np.where(contiguo, np.diff(np.log(barras.mid_c)), 0.0)
    valido[1:] = contiguo

    ventana = int(cfg.VENTANA_VOL_RECIENTE_MIN)
    suma_sq = _suma_movil(ret ** 2, ventana)
    cuenta = _suma_movil(valido.astype(float), ventana)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cuenta >= cfg.MIN_BARRAS_VOL_RECIENTE,
                        np.sqrt(suma_sq / np.maximum(cuenta, 1)), np.nan)


def _suma_movil(valores, ventana):
    """Suma de las ultimas `ventana` posiciones, incluida la actual."""
    acumulado = np.concatenate([[0.0], np.cumsum(valores)])
    posiciones = np.arange(len(valores)) + 1
    return acumulado[posiciones] - acumulado[np.maximum(posiciones - ventana, 0)]


def sigma_por_franja(barras, cal, cfg):
    """
    Volatilidad de referencia de cada franja: la desviacion tipica de un
    retorno de 1 minuto en ESE tipo de franja, medida en los DIAS_VOL_REF dias
    validos anteriores. El dia de la propia franja nunca entra.

    Un dia pasado cuenta para el tipo de franja j solo si esa franja j de ese
    dia cumple COBERTURA_MIN_REFERENCIA. Con menos de DIAS_VOL_REF_MIN dias
    validos el resultado es NaN y los eventos de esa franja se descartan.
    """
    suma_sq, n_ret = _insumos_de_volatilidad(barras, cal)
    valido = (cal["cobertura"].to_numpy() >= cfg.COBERTURA_MIN_REFERENCIA) & (n_ret > 0)

    sigma = np.full(len(cal), np.nan)
    idx_franja = cal["idx_franja"].to_numpy()
    for j in np.unique(idx_franja):
        filas = np.flatnonzero(idx_franja == j)          # ya vienen ordenadas en el tiempo
        sq = _ventana_pasada(suma_sq[filas], valido[filas],
                             cfg.DIAS_VOL_REF, cfg.DIAS_VOL_REF_MIN, "sum")
        nn = _ventana_pasada(n_ret[filas], valido[filas],
                             cfg.DIAS_VOL_REF, cfg.DIAS_VOL_REF_MIN, "sum")
        with np.errstate(invalid="ignore", divide="ignore"):
            sigma[filas] = np.sqrt(np.where(nn > 0, sq / nn, np.nan))
    return sigma


def mediana_rango_pasada(cal, cfg):
    """
    Mediana del rango (H - L) del mismo tipo de franja en los DIAS_COMPRESION
    dias validos anteriores. Es el denominador del ratio de compresion.
    """
    valido = cal["cobertura"].to_numpy() >= cfg.COBERTURA_MIN_REFERENCIA
    rango = cal["rango"].to_numpy(float)
    mediana = np.full(len(cal), np.nan)
    idx_franja = cal["idx_franja"].to_numpy()
    for j in np.unique(idx_franja):
        filas = np.flatnonzero(idx_franja == j)
        mediana[filas] = _ventana_pasada(rango[filas], valido[filas],
                                         cfg.DIAS_COMPRESION, cfg.DIAS_COMPRESION_MIN,
                                         "median")
    return mediana


def agregar_retornos(barras, cal, eventos, cfg):
    """
    Agrega una columna de retorno normalizado por cada horizonte.

    Es una envoltura de `calcular_retornos` para la tabla de eventos. La
    hipotesis nula usa el MISMO nucleo sobre instantes sorteados, asi que la
    comparacion entre lo observado y lo nulo no puede desalinearse.
    """
    eventos = eventos.reset_index(drop=True).copy()
    if len(eventos) == 0:
        for h in cfg.HORIZONTES:
            eventos[f"ret_{h}"] = np.array([], dtype=float)
        eventos["h_fin_franja"] = np.array([], dtype=float)
        return eventos

    columnas = calcular_retornos(
        barras, cal, cfg,
        t_ns=eventos["t_evento_ns"].to_numpy(np.int64),
        direccion=eventos["direccion"].to_numpy(float),
        sigma=eventos["sigma_ref"].to_numpy(float),
        pos_franja=eventos["pos_franja"].to_numpy(int))
    for nombre, valores in columnas.items():
        eventos[nombre] = valores
    return eventos


def calcular_retornos(barras, cal, cfg, t_ns, direccion, sigma, pos_franja):
    """
    Nucleo del calculo de resultados, sobre arrays.

        ret_h = direccion * (ln P(t+h) - ln P(t)) / (sigma_ref * raiz(h))

    Queda NaN si falta el precio en alguna punta, si sigma_ref no existe, o si
    t+h cruza un cierre de mercado (el horizonte tendria dentro un fin de semana
    entero, que no es lo que se quiere medir).

    El horizonte "fin_franja" llega hasta el fin de la franja del instante o
    hasta la ultima barra antes del cierre de mercado, lo que ocurra primero.
    Por eso una ruptura del viernes por la tarde mide solo hasta el cierre.

    Devuelve un diccionario {nombre de columna: array}.
    """
    t = np.asarray(t_ns, dtype=np.int64)
    direccion = np.asarray(direccion, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    pos_franja = np.asarray(pos_franja, dtype=int)
    columnas = {}

    j_t = np.asarray(barras.indice_al_cierre(t, cfg.TOLERANCIA_PRECIO_MIN))
    precio_0 = np.where(j_t >= 0, barras.mid_c[np.maximum(j_t, 0)], np.nan)
    sesion_0 = np.where(j_t >= 0, barras.sesion[np.maximum(j_t, 0)], -1)

    # Horizonte variable: hasta el fin de la franja o hasta el cierre de mercado.
    fin_sesion = franjas.fin_de_sesion(barras)
    i1 = cal["i1"].to_numpy()[pos_franja]
    ultima = np.minimum(np.where(j_t >= 0, fin_sesion[np.maximum(j_t, 0)], 0), i1 - 1)
    t_fin = np.where(j_t >= 0, barras.cierre_ns[np.maximum(ultima, 0)], 0)
    h_fin = np.where(j_t >= 0, (t_fin - t) / tiempo.NS_MIN, np.nan)
    columnas["h_fin_franja"] = np.where(h_fin > 0, h_fin, np.nan)

    for h in cfg.HORIZONTES:
        if h == "fin_franja":
            minutos = columnas["h_fin_franja"]
            t_final = np.where(np.isfinite(minutos), t_fin, 0).astype(np.int64)
        else:
            minutos = np.full(len(t), float(h))
            t_final = t + int(h) * tiempo.NS_MIN

        j_h = np.asarray(barras.indice_al_cierre(t_final, cfg.TOLERANCIA_PRECIO_MIN))
        precio_h = np.where(j_h >= 0, barras.mid_c[np.maximum(j_h, 0)], np.nan)
        sesion_h = np.where(j_h >= 0, barras.sesion[np.maximum(j_h, 0)], -2)

        sirve = (
            np.isfinite(minutos) & (minutos > 0)
            & (j_t >= 0) & (j_h >= 0)
            & (sesion_0 == sesion_h)                 # el horizonte no cruza un cierre
            & np.isfinite(sigma) & (sigma > 0)
            & np.isfinite(precio_0) & np.isfinite(precio_h)
        )
        with np.errstate(invalid="ignore", divide="ignore"):
            bruto = direccion * (np.log(precio_h) - np.log(precio_0))
            valor = bruto / (sigma * np.sqrt(minutos))
        columnas[f"ret_{h}"] = np.where(sirve, valor, np.nan)

    return columnas
