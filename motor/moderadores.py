# -*- coding: utf-8 -*-
"""
MODERADORES — variables que pueden cambiar la fuerza del efecto (H3 y H4).

Todas se calculan con informacion que ya existe en el instante del evento:

  cerca_redondo         el extremo roto esta a menos de RADIO_REDONDO_PIPS de un
                        numero redondo (multiplo de PASO_REDONDO). El extremo
                        viene de la franja anterior, asi que es pasado puro.
  cerca_extremo_previo  el extremo roto esta pegado al maximo (si la ruptura es
                        alcista) o al minimo (si es bajista) del dia de Londres
                        anterior. Un dia de Londres termina a las 00:00 de
                        Londres, o sea antes de cualquier evento del dia
                        siguiente.
  comprimida            la franja de referencia fue estrecha comparada con la
                        mediana de ese mismo tipo de franja en los dias previos.
  noticia               hubo un anuncio macro en los VENTANA_NOTICIAS_MIN
                        minutos previos al evento.

El decil de volatilidad NO esta aqui a proposito: para calcularlo hay que mirar
la distribucion de toda la muestra, o sea informacion que en el instante t no
existe. Vive en nula.py y sirve solo para emparejar.

Las variables binarias van como 1.0 / 0.0 y quedan en NaN cuando no se pueden
calcular (por ejemplo, un evento sin dia de Londres anterior utilizable). Se
usan numeros y no booleanos porque las regresiones necesitan poder descartar
las filas incompletas.
"""
import numpy as np
import pandas as pd

from . import resultados, tiempo

NOMBRES = ["cerca_redondo", "cerca_extremo_previo", "comprimida", "noticia"]


def _extremos_del_dia(cal, cfg):
    """
    Maximo, minimo y cobertura de cada dia de Londres, a partir del calendario.

    La cobertura del dia se usa para no comparar contra un domingo, que en la
    practica trae solo una o dos horas de mercado.
    """
    tabla = cal.groupby("fecha_londres").agg(
        maximo=("H", "max"), minimo=("L", "min"),
        presentes=("minutos_presentes", "sum"), esperados=("minutos_esperados", "sum"))
    tabla["cobertura"] = tabla["presentes"] / tabla["esperados"]
    usable = tabla["cobertura"] >= cfg.DIA_PREVIO_MIN_COBERTURA
    tabla.loc[~usable, ["maximo", "minimo"]] = np.nan
    return tabla


def agregar(barras, cal, eventos, cfg, noticias=None):
    """
    Agrega las cuatro columnas de moderadores (mas las dos continuas de apoyo:
    `dist_redondo_pips` y `ratio_compresion`).

    `noticias` es un DataFrame con columnas `t_utc` (con zona) y `tipo`, o None
    si no hay calendario de anuncios.
    """
    eventos = eventos.reset_index(drop=True).copy()
    if len(eventos) == 0:
        for col in ["dist_redondo_pips", "ratio_compresion"] + NOMBRES:
            eventos[col] = np.array([], dtype=float)
        return eventos

    extremo = eventos["extremo_roto"].to_numpy(float)
    direccion = eventos["direccion"].to_numpy(int)
    pos = eventos["pos_franja"].to_numpy(int)
    t_evento = eventos["t_evento_ns"].to_numpy(np.int64)

    # --- numeros redondos ---------------------------------------------------
    mas_cercano = np.round(extremo / cfg.PASO_REDONDO) * cfg.PASO_REDONDO
    dist_pips = np.abs(extremo - mas_cercano) / cfg.PIP
    eventos["dist_redondo_pips"] = dist_pips
    eventos["cerca_redondo"] = (dist_pips <= cfg.RADIO_REDONDO_PIPS).astype(float)

    # --- extremos del dia de Londres anterior -------------------------------
    dias = _extremos_del_dia(cal, cfg)
    fecha = pd.DatetimeIndex(eventos["fecha_londres"])
    previo = fecha - pd.Timedelta(days=1)
    maximo_previo = dias["maximo"].reindex(previo).to_numpy(float)
    minimo_previo = dias["minimo"].reindex(previo).to_numpy(float)

    referencia = np.where(direccion == 1, maximo_previo, minimo_previo)
    distancia = np.abs(extremo - referencia) / cfg.PIP
    eventos["cerca_extremo_previo"] = np.where(
        np.isfinite(distancia), (distancia <= cfg.RADIO_EXTREMO_PREVIO_PIPS).astype(float), np.nan)

    # --- compresion de la franja de referencia ------------------------------
    mediana = resultados.mediana_rango_pasada(cal, cfg)
    rango = cal["rango"].to_numpy(float)
    ref = pos - 1
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(mediana[ref] > 0, rango[ref] / mediana[ref], np.nan)
    eventos["ratio_compresion"] = ratio
    eventos["comprimida"] = np.where(np.isfinite(ratio),
                                     (ratio < cfg.CORTE_COMPRESION).astype(float), np.nan)

    # --- noticias macro -----------------------------------------------------
    eventos["noticia"] = _hubo_noticia(t_evento, noticias, cfg)
    return eventos


def _hubo_noticia(t_evento, noticias, cfg):
    """1.0 si hubo un anuncio en (t - VENTANA_NOTICIAS_MIN, t], si no 0.0."""
    if noticias is None or len(noticias) == 0:
        return np.zeros(len(t_evento))
    t_anuncio = np.sort(tiempo.a_ns(pd.DatetimeIndex(noticias["t_utc"])))
    desde = t_evento - cfg.VENTANA_NOTICIAS_MIN * tiempo.NS_MIN
    cuantos = (np.searchsorted(t_anuncio, t_evento, side="right")
               - np.searchsorted(t_anuncio, desde, side="right"))
    return (cuantos > 0).astype(float)
