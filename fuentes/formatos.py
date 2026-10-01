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
    volumen 0. Aqui se conservan; el cargador los trata como faltantes;
  - con la configuracion regional en espanol, JForex escribe los decimales con
    COMA y separa los campos tambien con coma: "1,08701" ocupa dos campos. Se
    reconoce porque el encabezado trae 6 columnas y las filas 10 u 11 campos.
    Los cuatro precios siempre traen parte entera y decimales (2 campos cada
    uno); el volumen, 1 campo si es entero y 2 si no. Cada campo tiene que ser
    solo digitos y cada precio tiene que caer en un rango posible: una fila
    mal partida da un precio absurdo y se rechaza.
"""
import re

import numpy as np
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


def histdata_m1(flujo, horas_a_utc, zona=None):
    """
    Lee un CSV Generic ASCII M1 de HistData.

    Devuelve un DataFrame con open, high, low, close (del BID) y volumen, con
    indice `apertura_utc` en UTC. Con `zona` None, UTC = hora del archivo +
    `horas_a_utc` (EST fijo, la regla del pre-registro). Con un nombre de zona,
    la hora del archivo se lee en esa zona (con horario de verano); una hora
    ambigua o inexistente por el cambio de hora es un error, no se adivina.
    """
    tabla = pd.read_csv(flujo, sep=";", header=None, names=["marca"] + COLUMNAS,
                        dtype={"marca": str}, float_precision="round_trip")
    if tabla.empty:
        raise FormatoError("HistData: archivo vacio")
    _sin_nulos(tabla, "HistData")
    est = pd.to_datetime(tabla["marca"], format="%Y%m%d %H%M%S")
    if zona is None:
        indice = pd.DatetimeIndex(est + pd.Timedelta(hours=horas_a_utc)).tz_localize("UTC")
    else:
        indice = pd.DatetimeIndex(est).tz_localize(zona, ambiguous="raise",
                                                   nonexistent="raise").tz_convert("UTC")
    salida = tabla[COLUMNAS].astype(float)
    salida.index = indice.rename("apertura_utc")
    return salida


def _encabezado_dukascopy(linea):
    """Separador y nombres del encabezado; exige que la hora declare UTC o GMT."""
    linea = linea.strip().lstrip("\ufeff")
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


def _marcas_a_ns(marcas, formato):
    """Horas de texto a nanosegundos UTC (int64), con el formato detectado."""
    serie = pd.Series(marcas, dtype=str).str.replace(_SUFIJO_ZONA, "", regex=True).str.strip()
    formato = formato or _formato_de_fecha(serie.iloc[0])
    instantes = pd.to_datetime(serie, format=formato)
    return formato, instantes.to_numpy(dtype="datetime64[ns]").astype(np.int64)


def marcas_dukascopy(flujo, filas_por_trozo=1_000_000):
    """
    Solo la hora de cada fila de un CSV de Dukascopy, sin interpretar precios.

    Es la primera pasada de la conversion: con ella se revisa, antes de leer un
    solo precio, que ningun minuto sea del sellado y que Bid y Ask traigan los
    mismos minutos. Genera arrays int64 de nanosegundos UTC, por trozos. De
    cada linea se toma solo lo que esta antes del primer separador.
    """
    sep = _encabezado_dukascopy(flujo.readline())
    formato = None
    lote = []
    for linea in flujo:
        if linea.strip():
            lote.append(linea.split(sep, 1)[0])
        if len(lote) == filas_por_trozo:
            formato, ns = _marcas_a_ns(lote, formato)
            lote = []
            yield ns
    if lote:
        yield _marcas_a_ns(lote, formato)[1]


_DIGITOS = r"\d+"


def _coma_decimal(trozo, rango_plausible):
    """Reconstruye los cinco numeros de una fila escrita con coma decimal."""
    salida = pd.DataFrame(index=trozo.index)
    partes = [f"c{k}" for k in range(1, 11)]
    for k, nombre in enumerate(LADOS):
        entero, decimales = trozo[partes[2 * k]], trozo[partes[2 * k + 1]]
        if not (entero.str.fullmatch(_DIGITOS).all() and decimales.str.fullmatch(_DIGITOS).all()):
            raise FormatoError(f"Dukascopy (coma decimal): '{nombre}' con campos que no son digitos")
        salida[nombre] = pd.to_numeric(entero + "." + decimales)
    entero, decimales = trozo["c9"], trozo["c10"]
    if not (entero.str.fullmatch(_DIGITOS).all() and decimales.dropna().str.fullmatch(_DIGITOS).all()):
        raise FormatoError("Dukascopy (coma decimal): volumen con campos que no son digitos")
    salida["volumen"] = pd.to_numeric(entero.where(decimales.isna(), entero + "." + decimales))
    precios = salida[list(LADOS)].to_numpy()
    if not ((precios > rango_plausible[0]) & (precios < rango_plausible[1])).all():
        raise FormatoError("Dukascopy (coma decimal): precios fuera de rango; alguna fila se "
                           "partio mal")
    return salida


def dukascopy_jforex(flujo, rango_plausible, filas_por_trozo=1_000_000):
    """
    Lee un CSV de Dukascopy (un lado: bid o ask) por trozos.

    Genera DataFrames con open, high, low, close y volumen, con indice
    `apertura_utc` en UTC. Los trozos permiten convertir decenas de millones
    de filas sin cargarlas todas a la vez. Reconoce solo el formato con punto
    decimal y el de coma decimal descrito arriba; cualquier otro se rechaza.
    """
    sep = _encabezado_dukascopy(flujo.readline())
    posicion = flujo.tell()
    campos = len(flujo.readline().rstrip("\r\n").split(sep))
    flujo.seek(posicion)
    if campos == 6:
        coma_decimal = False
        nombres = ["marca"] + COLUMNAS
    elif sep == "," and campos in (10, 11):
        coma_decimal = True
        nombres = ["marca"] + [f"c{k}" for k in range(1, 11)]
    else:
        raise FormatoError(f"Dukascopy: la primera fila trae {campos} campos y el encabezado 6")
    lector = pd.read_csv(flujo, sep=sep, header=None, names=nombres,
                         dtype=str if coma_decimal else {"marca": str},
                         float_precision="round_trip", chunksize=filas_por_trozo)
    formato = None
    for trozo in lector:
        if coma_decimal:
            if trozo[nombres[:10]].isna().any().any():
                raise FormatoError("Dukascopy (coma decimal): filas con menos de 10 campos")
            numeros = _coma_decimal(trozo, rango_plausible)
            trozo = pd.concat([trozo[["marca"]], numeros], axis=1)
        _sin_nulos(trozo, "Dukascopy")
        marca = trozo["marca"].str.replace(_SUFIJO_ZONA, "", regex=True).str.strip()
        if formato is None:
            formato = _formato_de_fecha(marca.iloc[0])
        indice = pd.DatetimeIndex(pd.to_datetime(marca, format=formato)).tz_localize("UTC")
        salida = trozo[COLUMNAS].astype(float)
        salida.index = indice.rename("apertura_utc")
        yield salida
