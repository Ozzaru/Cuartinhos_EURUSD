# -*- coding: utf-8 -*-
"""
Pruebas del anexo de sensibilidad: solo cuenta eventos, y las cuentas tienen
que ser coherentes entre si.
"""
import numpy as np
import pandas as pd
import pytest

from experimentos import anexo_sensibilidad as anexo


@pytest.fixture(scope="module")
def tabla():
    cambios = {"SENSIBILIDAD_UMBRAL_PIPS": [1.0, 5.0], "SENSIBILIDAD_UMBRAL_VOL": [1.0],
               "SENSIBILIDAD_M": [5, 30]}
    return anexo.corrida(semilla=12, anios=1, cambios=cambios)


def test_una_fila_por_variante_y_porcentajes_entre_cero_y_uno(tabla):
    assert len(tabla) == 3 * 2
    for c in [c for c in tabla.columns if c.startswith("pct_")]:
        assert tabla[c].between(0, 1).all(), c


def test_un_umbral_mas_alto_rompe_menos_franjas(tabla):
    pips = tabla[tabla["modo"] == "pips"].set_index(["valor", "M"])
    assert pips.loc[(5.0, 5), "pct_ruptura"] < pips.loc[(1.0, 5), "pct_ruptura"]


def test_m_solo_cambia_las_sostenidas(tabla):
    pips = tabla[(tabla["modo"] == "pips") & (tabla["valor"] == 1.0)].set_index("M")
    assert pips.loc[5, "pct_ruptura"] == pips.loc[30, "pct_ruptura"]
    assert pips.loc[5, "pct_reingreso"] == pips.loc[30, "pct_reingreso"]
    assert pips.loc[30, "pct_sostenida"] < pips.loc[5, "pct_sostenida"]


def test_en_modo_pips_el_umbral_medio_es_el_valor(tabla):
    pips = tabla[tabla["modo"] == "pips"]
    assert (pips["umbral_medio_pips"] == pips["valor"]).all()
    vol = tabla[tabla["modo"] == "vol"]
    assert (vol["umbral_medio_pips"] > 0).all()


def test_una_sostenida_con_reingreso_en_su_franja_cuenta_como_que_reingresa():
    eventos = pd.DataFrame({
        "tipo": ["ruptura", "sostenida", "reingreso", "ruptura", "sostenida"],
        "id_franja": ["a", "a", "a", "b", "b"],
    })
    resumen = anexo.resumen_de_variante(eventos, n_utilizables=4, anios=1)
    assert resumen["pct_ruptura"] == 0.5
    assert resumen["pct_sostenidas_que_reingresan"] == 0.5
    assert resumen["pct_rupturas_que_aguantan"] == 1.0
    assert np.isclose(resumen["pct_reingreso"], 0.25)
