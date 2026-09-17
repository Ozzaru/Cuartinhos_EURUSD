# -*- coding: utf-8 -*-
"""
TIEMPO — la unica puerta de entrada y salida de las conversiones de fecha.

REGLA DEL PROYECTO: ningun otro modulo convierte tiempos "a mano". Todo pasa
por estas funciones. Si alguien escribe su propia conversion en otro archivo,
un error de unidades (segundos vs nanosegundos) o de zona horaria puede pasar
en silencio y contaminar la deteccion de eventos.

Convencion heredada del proyecto anterior (Cuartinhos_Goty, motor.py::TF):
el indice de una barra es su hora de APERTURA y el trabajo interno se hace en
enteros de nanosegundos UTC, porque comparar enteros es exacto y rapido.
La barra de 1 minuto que abre en `apertura` CIERRA en `apertura + NS_MIN`, y
recien ahi su informacion existe.

Todas las marcas de tiempo deben traer zona horaria. Una fecha sin zona se
rechaza con un error: preferimos que reviente a que se asuma una zona.
"""
import numpy as np
import pandas as pd

NS_MIN = 60_000_000_000          # nanosegundos que dura un minuto


def _exigir_zona(x, nombre):
    """Rechaza fechas sin zona horaria: una zona implicita es un error futuro."""
    if x is None:
        raise ValueError(f"{nombre}: se esperaba una fecha, llego None")
    if x.tz is None:
        raise ValueError(
            f"{nombre}: la fecha no trae zona horaria. El motor solo trabaja "
            f"con fechas con zona (normalmente UTC)."
        )


def a_ns(tiempos):
    """
    Pasa fechas con zona a enteros de nanosegundos UTC.

    Acepta una marca suelta (devuelve int) o un indice / serie de fechas
    (devuelve un array int64). La zona de origen da igual: el resultado
    siempre esta en el mismo reloj, el de UTC.
    """
    if isinstance(tiempos, pd.Timestamp):
        _exigir_zona(tiempos, "a_ns")
        return int(tiempos.value)          # .value ya esta en nanosegundos UTC
    idx = tiempos if isinstance(tiempos, pd.DatetimeIndex) else pd.DatetimeIndex(tiempos)
    _exigir_zona(idx, "a_ns")
    return idx.tz_convert("UTC").values.astype("datetime64[ns]").astype(np.int64)


def de_ns(ns):
    """Vuelta atras: de nanosegundos UTC a fechas con zona UTC."""
    if np.isscalar(ns):
        return pd.Timestamp(int(ns), tz="UTC")
    return pd.DatetimeIndex(np.asarray(ns, dtype=np.int64).astype("datetime64[ns]"), tz="UTC")


def cierre_ns(apertura_ns, minutos=1):
    """
    Instante de CIERRE de una barra que abre en `apertura_ns`.

    Esta es la regla de causalidad escrita como codigo: la informacion de la
    barra existe en este instante, no en el de su apertura.
    """
    if np.isscalar(apertura_ns):
        return int(apertura_ns) + int(minutos) * NS_MIN
    return np.asarray(apertura_ns, dtype=np.int64) + int(minutos) * NS_MIN


def a_zona(tiempos, zona):
    """Mismo instante, visto en otro reloj (por ejemplo 'Europe/London')."""
    idx = tiempos if isinstance(tiempos, (pd.DatetimeIndex, pd.Timestamp)) else pd.DatetimeIndex(tiempos)
    _exigir_zona(idx, "a_zona")
    return idx.tz_convert(zona)


def a_utc(tiempos):
    """Mismo instante, de vuelta en UTC."""
    return a_zona(tiempos, "UTC")
