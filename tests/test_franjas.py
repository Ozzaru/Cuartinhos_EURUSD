# -*- coding: utf-8 -*-
"""
Pruebas del calendario: franjas de Londres, cobertura y cierres de mercado.

El punto delicado es el horario de verano. Las franjas se definen en hora de
Londres, asi que en UTC se corren una hora segun la epoca del ano, y los dos
dias del cambio de hora tienen una franja de 5 o de 7 horas.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
from motor import franjas, tiempo


def calendario_de(inicio, dias, cfg, precio=1.10):
    idx = ayuda.indice(inicio, dias * 24 * 60)
    datos = ayuda.datos(ayuda.plano(len(idx), precio), idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    return barras, franjas.calendario(barras, cfg)


def fila(cal, fecha, idx_franja):
    sel = cal[(cal["fecha_londres"] == pd.Timestamp(fecha)) & (cal["idx_franja"] == idx_franja)]
    assert len(sel) == 1, f"no hay una unica franja {fecha} / {idx_franja}"
    return sel.iloc[0]


@pytest.mark.parametrize("fecha, hora_utc_esperada, etiqueta", [
    ("2020-06-16", "05:00", "verano: Londres va una hora adelante"),
    ("2020-12-15", "06:00", "invierno: Londres coincide con UTC"),
    ("2020-03-29", "05:00", "dia en que Londres adelanta el reloj"),
    ("2020-10-25", "06:00", "dia en que Londres atrasa el reloj"),
])
def test_la_franja_de_6_a_12_empieza_donde_corresponde(fecha, hora_utc_esperada, etiqueta):
    cfg = ayuda.cfg_prueba()
    inicio = (pd.Timestamp(fecha) - pd.Timedelta(days=1)).strftime("%Y-%m-%d 00:00")
    _, cal = calendario_de(inicio, 3, cfg)
    f = fila(cal, fecha, 1)
    esperado = pd.Timestamp(f"{fecha} {hora_utc_esperada}", tz="UTC")
    assert tiempo.de_ns(f["inicio_ns"]) == esperado, etiqueta


def test_el_dia_que_se_adelanta_el_reloj_la_franja_cero_dura_cinco_horas():
    # El 29-03-2020 Londres salta de las 01:00 a las 02:00: la franja [0,6)
    # local empieza a las 00:00 UTC y termina a las 05:00 UTC.
    cfg = ayuda.cfg_prueba()
    _, cal = calendario_de("2020-03-28 00:00", 3, cfg)
    f = fila(cal, "2020-03-29", 0)
    assert f["minutos_esperados"] == 300
    assert f["minutos_presentes"] == 300
    assert f["cobertura"] == 1.0


def test_el_dia_que_se_atrasa_el_reloj_la_franja_cero_dura_siete_horas():
    # El 25-10-2020 Londres repite la hora de 01:00 a 02:00.
    cfg = ayuda.cfg_prueba()
    _, cal = calendario_de("2020-10-24 00:00", 3, cfg)
    f = fila(cal, "2020-10-25", 0)
    assert f["minutos_esperados"] == 420
    assert f["minutos_presentes"] == 420
    assert tiempo.de_ns(f["inicio_ns"]) == pd.Timestamp("2020-10-24 23:00", tz="UTC")


def test_una_franja_sin_datos_aparece_con_cobertura_cero():
    # El calendario lista TODAS las franjas del periodo, tengan datos o no: asi
    # una franja que falta invalida a la siguiente en vez de pasar inadvertida.
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2020-06-15 00:00", 2 * 24 * 60)
    fuera = (idx >= pd.Timestamp("2020-06-16 05:00", tz="UTC")) & \
            (idx < pd.Timestamp("2020-06-16 11:00", tz="UTC"))
    idx = idx[~fuera]
    datos = ayuda.datos(ayuda.plano(len(idx), 1.10), idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    f = fila(cal, "2020-06-16", 1)
    assert f["minutos_presentes"] == 0
    assert f["cobertura"] == 0.0
    assert f["i0"] == f["i1"]


def test_un_hueco_largo_abre_una_sesion_nueva_y_uno_corto_no():
    cfg = ayuda.cfg_prueba(HUECO_CIERRE_MIN=60)
    idx = ayuda.indice("2020-06-15 00:00", 600)
    # Hueco de 30 minutos: sigue siendo la misma sesion.
    corto = (idx >= pd.Timestamp("2020-06-15 02:00", tz="UTC")) & \
            (idx < pd.Timestamp("2020-06-15 02:30", tz="UTC"))
    # Hueco de 120 minutos: es un cierre de mercado.
    largo = (idx >= pd.Timestamp("2020-06-15 05:00", tz="UTC")) & \
            (idx < pd.Timestamp("2020-06-15 07:00", tz="UTC"))
    idx = idx[~(corto | largo)]
    datos = ayuda.datos(ayuda.plano(len(idx), 1.10), idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    assert barras.sesion[0] == 0
    antes = np.searchsorted(barras.apertura_ns,
                            tiempo.a_ns(pd.Timestamp("2020-06-15 04:00", tz="UTC")))
    despues = np.searchsorted(barras.apertura_ns,
                              tiempo.a_ns(pd.Timestamp("2020-06-15 08:00", tz="UTC")))
    assert barras.sesion[antes] == 0, "un hueco de 30 minutos no es un cierre"
    assert barras.sesion[despues] == 1, "un hueco de 120 minutos si es un cierre"
    assert barras.sesion.max() == 1


def test_el_precio_medio_es_el_promedio_de_bid_y_ask():
    cfg = ayuda.cfg_prueba()
    velas = np.array([[1.1000, 1.1010, 1.0990, 1.1005]])
    datos = ayuda.datos(velas, inicio="2020-06-15 00:00", spread_pips=2.0)
    barras = franjas.Barras.desde(datos, cfg)
    assert barras.mid_o[0] == pytest.approx(1.1000)
    assert barras.mid_h[0] == pytest.approx(1.1010)
    assert barras.mid_l[0] == pytest.approx(1.0990)
    assert barras.mid_c[0] == pytest.approx(1.1005)
    con_medios = franjas.agregar_medios(datos)
    assert con_medios["ask_close"].iloc[0] - con_medios["bid_close"].iloc[0] == pytest.approx(2 * ayuda.PIP)


def test_los_datos_mal_formados_revientan_en_vez_de_seguir():
    cfg = ayuda.cfg_prueba()
    velas = ayuda.plano(10, 1.10)
    datos = ayuda.datos(velas, inicio="2020-06-15 00:00")

    sin_zona = datos.copy()
    sin_zona.index = datos.index.tz_localize(None)
    with pytest.raises(ValueError):
        franjas.Barras.desde(sin_zona, cfg)

    desordenado = datos.iloc[::-1]
    with pytest.raises(ValueError):
        franjas.Barras.desde(desordenado, cfg)

    faltan_columnas = datos[["bid_open", "ask_open"]]
    with pytest.raises(ValueError):
        franjas.Barras.desde(faltan_columnas, cfg)
