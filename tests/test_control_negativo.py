# -*- coding: utf-8 -*-
"""
Pruebas de las piezas del control negativo.

La corrida completa tarda minutos y no cabe en la bateria de tests; lo que si
se prueba aqui son las cuentas que despues se leen en el reporte, porque un
intervalo mal calculado o una tabla mal armada cambiarian la conclusion sin
que nada falle a la vista.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
from experimentos import control_negativo as cn
from experimentos import recursos


# --- intervalo binomial -----------------------------------------------------

def test_el_intervalo_de_wilson_contiene_la_proporcion():
    bajo, alto = cn.intervalo_binomial(5, 100)
    assert bajo < 0.05 < alto
    assert 0.0 <= bajo and alto <= 1.0


def test_el_intervalo_se_angosta_con_mas_datos():
    ancho_chico = np.diff(cn.intervalo_binomial(5, 100))[0]
    ancho_grande = np.diff(cn.intervalo_binomial(50, 1000))[0]
    assert ancho_grande < ancho_chico


def test_el_intervalo_no_se_sale_del_rango_en_los_extremos():
    # Con cero rechazos la formula clasica daria [0, 0], que promete una
    # certeza que no existe. Wilson deja un margen por arriba.
    bajo, alto = cn.intervalo_binomial(0, 20)
    assert bajo == 0.0
    assert 0.0 < alto < 1.0
    bajo, alto = cn.intervalo_binomial(20, 20)
    assert 0.0 < bajo < 1.0
    assert alto == 1.0


def test_sin_datos_el_intervalo_no_inventa():
    bajo, alto = cn.intervalo_binomial(0, 0)
    assert np.isnan(bajo) and np.isnan(alto)


def test_el_error_de_monte_carlo_baja_con_la_raiz_del_numero_de_corridas():
    assert cn.error_monte_carlo(0.05, 100) == pytest.approx(
        np.sqrt(0.05 * 0.95 / 100))
    assert cn.error_monte_carlo(0.05, 400) == pytest.approx(
        cn.error_monte_carlo(0.05, 100) / 2)


# --- resumenes --------------------------------------------------------------

def tabla_de_pruebas(rechazos_por_mercado):
    """Una tabla de pruebas falsa, con los rechazos que pida el test."""
    filas = []
    for mercado, rechazos in enumerate(rechazos_por_mercado):
        for k in range(4):
            p = 0.001 if k < rechazos else 0.5
            filas.append({"familia": "principal", "mercado": mercado,
                          "tipo": "sostenida", "horizonte": 30 + k,
                          "p_bruto": p, "p_corregido": p, "efecto": 0.0})
    return pd.DataFrame(filas)


def test_la_tasa_por_familia_cuenta_mercados_y_no_pruebas():
    # Tres mercados: dos sin ningun rechazo y uno con dos.
    tabla = tabla_de_pruebas([0, 0, 2])
    cfg = ayuda.cfg_prueba()
    resumen = cn.resumen_por_familia(tabla, cfg).iloc[0]
    assert resumen["pruebas"] == 12
    assert resumen["tasa_bruta"] == pytest.approx(2 / 12)
    assert resumen["mercados"] == 3
    assert resumen["tasa_familia"] == pytest.approx(1 / 3)


def test_el_resumen_de_h4_separa_por_tramo_modo_y_estadistico():
    filas = []
    for dias, p in [(5, 0.01), (5, 0.02), (15, 0.5), (50, 0.5), (200, 0.5)]:
        for modo in ("ventana", "franja"):
            filas.append({"modo": modo, "dias_tratados": dias,
                          "p_estudentizado": p, "p_sin_estudentizar": p})
    tabla = cn.resumen_h4(pd.DataFrame(filas), ayuda.cfg_prueba())

    assert set(tabla["modo"]) == {"ventana", "franja"}
    assert set(tabla["estadistico"]) == {"estudentizado", "sin estudentizar"}
    chico = tabla[(tabla["modo"] == "ventana") & (tabla["tramo"] == "<10")
                  & (tabla["estadistico"] == "estudentizado")].iloc[0]
    assert chico["pruebas"] == 2 and chico["rechazos"] == 2
    grande = tabla[(tabla["modo"] == "ventana") & (tabla["tramo"] == ">=100")].iloc[0]
    assert grande["rechazos"] == 0


def test_los_tramos_de_dias_tratados_no_se_pisan_ni_dejan_huecos():
    bordes = [(bajo, alto) for bajo, alto, _ in cn.TRAMOS]
    assert bordes[0][0] == 0
    for (_, alto), (siguiente, _) in zip(bordes, bordes[1:]):
        assert alto == siguiente, "los tramos tienen que encadenarse"


# --- tabla de markdown ------------------------------------------------------

def test_la_tabla_de_markdown_tiene_encabezado_y_separador():
    marco = pd.DataFrame({"a": [1, 2], "b": [0.5, np.nan]})
    texto = cn._tabla(marco).splitlines()
    assert texto[0] == "| a | b |"
    assert texto[1] == "|---|---|"
    assert texto[2] == "| 1 | 0.5 |"
    assert texto[3] == "| 2 | - |", "un valor que falta se muestra como raya"


def test_la_tabla_vacia_lo_dice_en_vez_de_romperse():
    assert "sin datos" in cn._tabla(pd.DataFrame())


# --- recursos ---------------------------------------------------------------

def test_el_numero_de_procesos_nunca_es_cero():
    assert recursos.procesos_que_caben(1000.0) >= 1
    assert recursos.procesos_que_caben(0.0) >= 1
    assert recursos.procesos_que_caben(float("nan")) >= 1


def test_mas_memoria_por_proceso_significa_menos_procesos():
    pocos = recursos.procesos_que_caben(8.0, tope=16)
    muchos = recursos.procesos_que_caben(0.05, tope=16)
    assert muchos >= pocos


def test_el_tope_se_respeta():
    assert recursos.procesos_que_caben(0.001, tope=3) <= 3


def test_medir_pico_devuelve_resultado_tiempo_y_memoria():
    resultado, pico, segundos = recursos.medir_pico(lambda: sum(range(100000)))
    assert resultado == sum(range(100000))
    assert segundos >= 0
    assert pico >= 0
