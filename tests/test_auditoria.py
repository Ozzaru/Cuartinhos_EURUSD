# -*- coding: utf-8 -*-
"""
Pruebas de la auditoria de causalidad.

La auditoria sirve solo si hace dos cosas: dejar pasar al motor real y atrapar
a uno contaminado. Lo segundo se prueba con una fuga inyectada A PROPOSITO que
vive SOLO en este archivo: `precio_en` lee la barra que cierra un minuto
DESPUES de t. Es la fuga mas chica posible, y como el motor usa `precio_en`
solo para fechar la sostenida, altera algo unicamente cuando un corte cae justo
en el instante de una sostenida. Si la auditoria no la ve, no sirve.

Los cortes salen del MISMO generador que usa la auditoria real, con semilla
fija. Ningun corte se pone a mano.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import auditoria, resultados, tiempo
from simulacion import mercado

DIAS = 60                 # largo de la muestra de prueba: suficiente para sigma_ref y moderadores
SEMILLA_CORTES = 3


@pytest.fixture(scope="module")
def mercados():
    """Dos mercados simulados con el mismo indice: el real y el del futuro reemplazado."""
    cfg = ayuda.cfg_prueba()
    datos, noticias = mercado.generar(1, 11, cfg)
    otro, _ = mercado.generar(1, 12, cfg)
    hasta = datos.index[0] + pd.Timedelta(days=DIAS)
    dentro = datos.index < hasta
    return datos[dentro], otro[dentro], noticias[noticias["t_utc"] < hasta], cfg


@pytest.fixture(scope="module")
def preparado(mercados):
    datos, _, noticias, cfg = mercados
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
    return barras, cal, eventos


@pytest.fixture(scope="module")
def auditoria_real(mercados):
    datos, otro, noticias, cfg = mercados
    return auditoria.auditar(datos, cfg, otro, SEMILLA_CORTES, noticias=noticias)


# --- el generador de cortes -------------------------------------------------

def test_los_cortes_salen_en_las_cantidades_acordadas(mercados, preparado):
    cfg = mercados[3]
    cortes = auditoria.generar_cortes(*preparado, cfg, SEMILLA_CORTES)
    cuenta = cortes["clase"].value_counts()
    assert cuenta["evento"] == cfg.CORTES_AUDITORIA_EVENTO
    assert cuenta["mitad_franja"] == cfg.CORTES_AUDITORIA_MITAD_FRANJA
    assert cuenta["azar"] == cfg.CORTES_AUDITORIA_AZAR
    assert cortes["t_corte_ns"].is_monotonic_increasing


def test_los_cortes_anclados_caen_exactamente_en_eventos_de_los_tres_tipos(mercados, preparado):
    cfg = mercados[3]
    _, _, eventos = preparado
    cortes = auditoria.generar_cortes(*preparado, cfg, SEMILLA_CORTES)
    anclados = cortes[cortes["clase"] == "evento"]
    for _, fila in anclados.iterrows():
        mismo = ((eventos["t_evento_ns"] == fila["t_corte_ns"])
                 & (eventos["tipo"] == fila["tipo_evento"]))
        assert mismo.any(), "un corte anclado tiene que coincidir con un evento real"
    assert set(anclados["tipo_evento"]) == set(cfg.TIPOS_EVENTO)


def test_los_cortes_de_mitad_de_franja_caen_en_el_medio_de_una_franja_con_eventos(
        mercados, preparado):
    cfg = mercados[3]
    _, cal, eventos = preparado
    cortes = auditoria.generar_cortes(*preparado, cfg, SEMILLA_CORTES)
    inicio = cal["inicio_ns"].to_numpy(np.int64)
    fin = cal["fin_ns"].to_numpy(np.int64)
    con_eventos = set(eventos["pos_franja"])
    for t in cortes.loc[cortes["clase"] == "mitad_franja", "t_corte_ns"]:
        k = int(np.searchsorted(inicio, t, side="right") - 1)
        assert k in con_eventos
        assert abs((t - inicio[k]) - (fin[k] - t)) <= tiempo.NS_MIN, "no esta en la mitad"


def test_misma_semilla_mismos_cortes_otra_semilla_otros(mercados, preparado):
    cfg = mercados[3]
    a = auditoria.generar_cortes(*preparado, cfg, SEMILLA_CORTES)
    b = auditoria.generar_cortes(*preparado, cfg, SEMILLA_CORTES)
    c = auditoria.generar_cortes(*preparado, cfg, SEMILLA_CORTES + 1)
    pd.testing.assert_frame_equal(a, b)
    assert not a["t_corte_ns"].equals(c["t_corte_ns"])


# --- la auditoria -----------------------------------------------------------

def test_el_motor_real_pasa_todos_los_cortes(auditoria_real):
    cortes, detalle = auditoria_real
    fallas = detalle[~detalle["pasa"]]
    assert cortes["pasa"].all(), f"el motor real no paso la auditoria:\n{fallas}"
    assert set(detalle["variante"]) == {"truncada", "reemplazada"}
    assert (detalle["eventos_completa"] > 0).all(), "cada corte tiene que comparar algo"


def test_la_auditoria_compara_de_verdad_lo_que_el_motor_declara(auditoria_real, preparado):
    # Contraste: con el corte en el ultimo instante, la comparacion abarca la
    # muestra entera, y la cantidad de eventos comparados tiene que crecer con
    # el corte.
    cortes, detalle = auditoria_real
    truncada = detalle[detalle["variante"] == "truncada"].sort_values("t_corte_ns")
    assert truncada["eventos_completa"].is_monotonic_increasing
    assert truncada["eventos_completa"].iloc[-1] > 30


def test_la_auditoria_detecta_una_fuga_de_un_minuto(mercados, monkeypatch):
    datos, otro, noticias, cfg = mercados
    precio_real = resultados.precio_en

    def precio_con_fuga(barras, t_ns, cfg, tolerancia_min=None):
        # FUGA A PROPOSITO: lee la barra que cierra un minuto DESPUES de t.
        return precio_real(barras, np.asarray(t_ns) + tiempo.NS_MIN, cfg, tolerancia_min)

    monkeypatch.setattr(resultados, "precio_en", precio_con_fuga)
    cortes, _ = auditoria.auditar(datos, cfg, otro, SEMILLA_CORTES, noticias=noticias)

    assert not cortes["pasa"].all(), "la auditoria no vio la fuga: asi no sirve"
    atrapada = cortes[~cortes["pasa"]]
    assert (atrapada["tipo_evento"] == "sostenida").any(), \
        "la fuga tiene que aparecer en un corte anclado a una sostenida"


def test_sin_la_fuga_el_mismo_calculo_vuelve_a_pasar(mercados, auditoria_real):
    # El monkeypatch del test anterior no se filtra: el motor quedo intacto.
    assert resultados.precio_en.__name__ == "precio_en"
    assert auditoria_real[0]["pasa"].all()
