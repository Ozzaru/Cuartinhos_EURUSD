# -*- coding: utf-8 -*-
"""
Pruebas del manejo de tiempo.

Un error de unidades (segundos vs nanosegundos) o de zona horaria no avisa:
simplemente devuelve numeros creibles y equivocados. Estas pruebas fijan el
comportamiento esperado para que ningun cambio de version de pandas lo mueva
sin que nos enteremos.
"""
import numpy as np
import pandas as pd
import pytest

from motor import tiempo


def indice_del_motor(inicio, minutos):
    """Un indice de minutos en UTC, construido como lo hara el motor."""
    return pd.date_range(inicio, periods=minutos, freq="min", tz="UTC")


# --- (a) enteros de nanosegundos -------------------------------------------

def test_indice_utc_pasa_a_nanosegundos_enteros():
    idx = indice_del_motor("2020-06-15 00:00", 10)
    ns = tiempo.a_ns(idx)
    assert ns.dtype == np.int64
    # 2020-06-15 00:00 UTC en nanosegundos desde el 1-1-1970, calculado aparte.
    assert ns[0] == 1592179200 * 1_000_000_000
    # El paso entre minutos consecutivos es exactamente un minuto en ns.
    assert np.all(np.diff(ns) == tiempo.NS_MIN)
    assert tiempo.NS_MIN == 60_000_000_000


def test_el_cierre_es_la_apertura_mas_un_minuto():
    idx = indice_del_motor("2020-06-15 00:00", 5)
    aperturas = tiempo.a_ns(idx)
    cierres = tiempo.cierre_ns(aperturas)
    # Escrito de las dos formas: aritmetica en ns y aritmetica de fechas.
    # (Se usa to_timedelta y no Timedelta: ver la nota de version en tiempo.py.)
    assert np.all(cierres - aperturas == 60_000_000_000)
    assert np.array_equal(cierres, tiempo.a_ns(idx + pd.to_timedelta(1, unit="m")))
    # La version escalar tiene que coincidir con la vectorizada.
    assert tiempo.cierre_ns(int(aperturas[0])) == int(cierres[0])
    # El cierre de una barra es la apertura de la siguiente.
    assert int(cierres[0]) == int(aperturas[1])


def test_ida_y_vuelta_entre_fechas_y_nanosegundos():
    idx = indice_del_motor("2020-10-25 00:00", 300)
    assert (tiempo.de_ns(tiempo.a_ns(idx)) == idx).all()
    t = pd.Timestamp("2016-02-29 13:30", tz="UTC")
    assert tiempo.de_ns(tiempo.a_ns(t)) == t


def test_una_fecha_sin_zona_es_un_error():
    idx = pd.date_range("2020-06-15", periods=3, freq="min")     # sin tz a proposito
    with pytest.raises(ValueError):
        tiempo.a_ns(idx)
    with pytest.raises(ValueError):
        tiempo.a_ns(pd.Timestamp("2020-06-15 12:00"))


# --- (b) ida y vuelta por la zona de Londres -------------------------------

@pytest.mark.parametrize("inicio, etiqueta", [
    ("2020-06-15 00:00", "verano (BST, UTC+1)"),
    ("2020-01-15 00:00", "invierno (GMT, UTC+0)"),
    ("2020-03-29 00:00", "dia en que Londres adelanta el reloj"),
    ("2020-10-25 00:00", "dia en que Londres atrasa el reloj"),
])
def test_utc_a_londres_y_de_vuelta_es_identico(inicio, etiqueta):
    idx = indice_del_motor(inicio, 24 * 60)
    ida = tiempo.a_zona(idx, "Europe/London")
    vuelta = tiempo.a_utc(ida)
    assert (vuelta == idx).all(), f"la ida y vuelta cambio el instante en {etiqueta}"
    # El instante fisico nunca cambia, solo la etiqueta del reloj.
    assert np.array_equal(tiempo.a_ns(ida), tiempo.a_ns(idx))


def test_londres_adelanta_y_atrasa_en_las_fechas_esperadas():
    # En verano Londres va una hora adelante de UTC; en invierno, igual que UTC.
    verano = tiempo.a_zona(pd.Timestamp("2020-06-15 05:00", tz="UTC"), "Europe/London")
    invierno = tiempo.a_zona(pd.Timestamp("2020-12-15 06:00", tz="UTC"), "Europe/London")
    assert (verano.hour, verano.utcoffset().total_seconds()) == (6, 3600)
    assert (invierno.hour, invierno.utcoffset().total_seconds()) == (6, 0)
