# -*- coding: utf-8 -*-
"""
FORMATOS — como se interpreta el texto de cada fuente.

No abre archivos ni conoce rutas: recibe un flujo de texto que abre el
cargador, que es el unico modulo que toca archivos de precios. Tampoco decide
que barra sirve: devuelve lo que dice el archivo, tal cual, con el indice en
UTC. Si algo no calza con el formato esperado, revienta (FormatoError) en vez
de adivinar.

HistData, "Generic ASCII" de 1 minuto (especificacion publicada en
histdata.com/f-a-q/data-files-detailed-specification/):

    AAAAMMDD HHMMSS;apertura;maximo;minimo;cierre;volumen

  - precios del BID;
  - hora EST FIJA: UTC-5 todo el ano, sin horario de verano. Por eso
    UTC = EST + HISTDATA_HORAS_A_UTC, sin pasar por ninguna base de zonas;
  - la marca es la APERTURA de la barra (el control de calidad lo verifica con
    la correlacion contra Dukascopy en desfases de -120 a +120 minutos).

Dukascopy, CSV del Historical Data Manager de JForex (un archivo por lado):

  - encabezado con la columna de hora, que TIENE que declarar UTC o GMT (si no,
    no se sabe en que reloj esta y el archivo se rechaza), y Open, High, Low,
    Close, Volume;
  - sin filtro de velas planas: los minutos sin ticks vienen como velas con
    volumen 0. Aqui se conservan; el cargador los trata como faltantes.
"""
import re

import pandas as pd

LADOS = ("open", "high", "low", "close")
COLUMNAS = list(LADOS) + ["volumen"]

# Formatos de fecha que se aceptan en el CSV de Dukascopy. Solo formatos sin
# ambiguedad entre dia y mes: un "01/02/2016" no se interpreta.
FORMATOS_FECHA_DUKASCOPY = (
    "%d.%m.%Y %H:%M:%S.%f",
    "%d.%m.%Y %H:%M:%S",
    "%Y.%m.%d %H:%M:%S.%f",
    "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
)

# Sufijo de zona que algunas exportaciones pegan a cada fecha.
_SUFIJO_ZONA = re.compile(r"\s*(GMT|UTC)([+-]0{2}:?0{2})?\s*$", re.IGNORECASE)


class FormatoError(ValueError):
    """El archivo no tiene el formato esperado."""


def _sin_nulos(tabla, nombre):
    if tabla.isna().any().any():
        filas = int(tabla.isna().any(axis=1).sum())
        raise FormatoError(f"{nombre}: {filas} filas con campos vacios o no numericos")


def histdata_m1(flujo, horas_a_utc):
    """
    Lee un CSV Generic ASCII M1 de HistData.

    Devuelve un DataFrame con open, high, low, close (del BID) y volumen, con
    indice `apertura_utc` en UTC.
    """
    tabla = pd.read_csv(flujo, sep=";", header=None, names=["marca"] + COLUMNAS,
                        dtype={"marca": str}, float_precision="round_trip")
    if tabla.empty:
        raise FormatoError("HistData: archivo vacio")
    _sin_nulos(tabla, "HistData")
    est = pd.to_datetime(tabla["marca"], format="%Y%m%d %H%M%S")
    indice = pd.DatetimeIndex(est + pd.Timedelta(hours=horas_a_utc)).tz_localize("UTC")
    salida = tabla[COLUMNAS].astype(float)
    salida.index = indice.rename("apertura_utc")
    return salida


def _encabezado_dukascopy(linea):
    """Separador y nombres del encabezado; exige que la hora declare UTC o GMT."""
    linea = linea.strip().lstrip("﻿")
    sep = ";" if linea.count(";") > linea.count(",") else ","
    nombres = [c.strip() for c in linea.split(sep)]
    if len(nombres) != 6:
        raise FormatoError(f"Dukascopy: se esperaban 6 columnas y el encabezado trae {nombres}")
    hora = nombres[0].lower()
    if "utc" not in hora and "gmt" not in hora:
        raise FormatoError(
            f"Dukascopy: la columna de hora es '{nombres[0]}' y no declara UTC ni GMT. "
            "Hay que exportar con la zona de la plataforma en UTC.")
    esperadas = ["open", "high", "low", "close", "volume"]
    if [c.lower() for c in nombres[1:]] != esperadas:
        raise FormatoError(f"Dukascopy: columnas {nombres[1:]}, se esperaban {esperadas}")
    return sep


def _formato_de_fecha(ejemplo):
    for formato in FORMATOS_FECHA_DUKASCOPY:
        try:
            pd.to_datetime(pd.Series([ejemplo]), format=formato)
            return formato
        except ValueError:
            continue
    raise FormatoError(f"Dukascopy: no reconozco el formato de fecha '{ejemplo}'")


def dukascopy_jforex(flujo, filas_por_trozo=1_000_000):
    """
    Lee un CSV de Dukascopy (un lado: bid o ask) por trozos.

    Genera DataFrames con open, high, low, close y volumen, con indice
    `apertura_utc` en UTC. Los trozos permiten convertir decenas de millones
    de filas sin cargarlas todas a la vez.
    """
    sep = _encabezado_dukascopy(flujo.readline())
    lector = pd.read_csv(flujo, sep=sep, header=None, names=["marca"] + COLUMNAS,
                         dtype={"marca": str}, float_precision="round_trip",
                         chunksize=filas_por_trozo)
    formato = None
    for trozo in lector:
        _sin_nulos(trozo, "Dukascopy")
        marca = trozo["marca"].str.replace(_SUFIJO_ZONA, "", regex=True).str.strip()
        if formato is None:
            formato = _formato_de_fecha(marca.iloc[0])
        indice = pd.DatetimeIndex(pd.to_datetime(marca, format=formato)).tz_localize("UTC")
        salida = trozo[COLUMNAS].astype(float)
        salida.index = indice.rename("apertura_utc")
        yield salida
