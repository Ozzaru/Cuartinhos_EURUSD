# -*- coding: utf-8 -*-
"""
La ruptura que ve el control de calidad (`motor.rupturas`) es la misma que ve
el analisis (`motor.eventos`). Desde el punto G, `eventos` usa las funciones de
`rupturas`; estos tests lo amarran tambien desde afuera, sobre un mercado
simulado y con la configuracion principal y la de robustez del umbral.
"""
import numpy as np
import pytest

import ayuda
from motor import eventos, franjas, resultados, rupturas
from simulacion import mercado


@pytest.fixture(scope="module")
def mercado_simulado():
    cfg = ayuda.cfg_prueba()
    datos, _ = mercado.generar(1, cfg.SEMILLA + 7, cfg)
    return datos


@pytest.mark.parametrize("cambios", [{}, {"UMBRAL_MODO": "vol"}, {"UMBRAL_PIPS": 3.0}])
def test_las_rupturas_son_las_mismas_que_detecta_eventos(mercado_simulado, cambios):
    cfg = ayuda.cfg_prueba(**cambios)
    barras = franjas.Barras.desde(mercado_simulado, cfg)
    cal = franjas.calendario(barras, cfg)
    sigma = resultados.sigma_por_franja(barras, cal, cfg)
    mascara = eventos.franjas_utilizables(cal, sigma, cfg)

    del_motor = eventos.detectar(barras, cal, cfg, sigma=sigma)
    del_motor = del_motor[del_motor["tipo"] == "ruptura"].sort_values("pos_franja")
    solas = rupturas.detectar(barras, cal, cfg, mascara, sigma=sigma)
    rompen = solas[solas["direccion"] != 0].sort_values("pos_franja")

    assert len(del_motor) > 500
    assert np.array_equal(rompen["pos_franja"].to_numpy(), del_motor["pos_franja"].to_numpy())
    assert np.array_equal(rompen["direccion"].to_numpy(), del_motor["direccion"].to_numpy())
    assert np.array_equal(rompen["t_ruptura_ns"].to_numpy(), del_motor["t_ruptura_ns"].to_numpy())
    # Las franjas sin ruptura no tienen hora.
    assert (solas.loc[solas["direccion"] == 0, "t_ruptura_ns"] == -1).all()
    assert solas.loc[solas["direccion"] == 0, "t_ruptura_utc"].isna().all()


def test_la_mascara_de_eventos_es_la_de_rupturas_con_sigma(mercado_simulado):
    cfg = ayuda.cfg_prueba()
    barras = franjas.Barras.desde(mercado_simulado, cfg)
    cal = franjas.calendario(barras, cfg)
    sigma = resultados.sigma_por_franja(barras, cal, cfg)
    con_ref = rupturas.franjas_con_referencia(cal, cfg)
    assert np.array_equal(eventos.franjas_utilizables(cal, sigma, cfg),
                          con_ref & np.isfinite(sigma))
    # Sin sigma_ref solo se pierden las primeras franjas de la muestra.
    assert con_ref.sum() > eventos.franjas_utilizables(cal, sigma, cfg).sum()


def test_la_barra_ambigua_queda_marcada():
    H, L, u = 1.1010, 1.0990, 0.0001
    alto = np.array([1.1005, 1.1020, 1.1030])
    bajo = np.array([1.0995, 1.0980, 1.0995])
    cfg = ayuda.cfg_prueba(EXCLUIR_BARRA_AMBIGUA=True)
    assert rupturas.primera_ruptura(alto, bajo, H, L, u, u, cfg) == (1, 0, True)
    # Con la exclusion apagada desempata el lado que penetro mas (empate: alcista).
    cfg = ayuda.cfg_prueba(EXCLUIR_BARRA_AMBIGUA=False)
    assert rupturas.primera_ruptura(alto, bajo, H, L, u, u, cfg) == (1, 1, False)


def test_sin_ruptura_y_rupturas_de_un_lado():
    cfg = ayuda.cfg_prueba()
    H, L, u = 1.1010, 1.0990, 0.0001
    quieto = np.array([1.1005, 1.1010])
    assert rupturas.primera_ruptura(quieto, quieto - 0.001, H, L, u, u, cfg) == (-1, 0, False)
    # Tocar H + umbral exacto no es romper: hay que superarlo.
    assert rupturas.primera_ruptura(np.array([H + u]), np.array([1.1]), H, L, u, u, cfg)[1] == 0
    baja = np.array([1.1000, 1.1000]), np.array([1.0995, 1.0980])
    assert rupturas.primera_ruptura(*baja, H, L, u, u, cfg) == (1, -1, False)


def test_el_umbral_vol_exige_sigma(mercado_simulado):
    cfg = ayuda.cfg_prueba(UMBRAL_MODO="vol")
    barras = franjas.Barras.desde(mercado_simulado.iloc[:5000], cfg)
    cal = franjas.calendario(barras, cfg)
    with pytest.raises(ValueError):
        rupturas.detectar(barras, cal, cfg)
