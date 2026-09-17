# -*- coding: utf-8 -*-
"""
Pruebas de la hipotesis nula emparejada.

Lo que se vigila:
  - los minutos sorteados comparten franja, dia de semana y decil con el evento;
  - nunca sale un minuto de la MISMA franja del evento (seria compararlo consigo
    mismo);
  - el p-valor sigue la formula de Phipson y Smyth y nunca da cero;
  - con la misma semilla sale el mismo resultado;
  - sobre ruido puro los p-valores no se amontonan en valores bajos.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import nula


def mercado(semilla=42, dias=200):
    """Un mercado sin ningun patron, con fines de semana de verdad."""
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2016-01-04 00:00", dias * 24 * 60)
    viernes = (idx.dayofweek == 4) & (idx.hour >= 21)
    sabado = idx.dayofweek == 5
    domingo = (idx.dayofweek == 6) & (idx.hour < 21)
    idx = idx[~(viernes | sabado | domingo)]
    velas = ayuda.camino_aleatorio(len(idx), semilla=semilla)
    barras, cal, ev = motor.preparar(ayuda.datos(velas, idx=idx), cfg)
    return cfg, barras, cal, ev


# --- emparejamiento ---------------------------------------------------------

def test_los_deciles_reparten_las_franjas_en_partes_parejas():
    sigma = np.linspace(1e-5, 1e-3, 1000)
    utilizable = np.ones(1000, dtype=bool)
    grupo = nula.deciles_de_volatilidad(sigma, utilizable, 10)
    cuentas = np.bincount(grupo[grupo >= 0], minlength=10)
    assert len(cuentas) == 10
    assert cuentas.min() >= 90 and cuentas.max() <= 110
    # Las franjas no utilizables quedan marcadas con -1.
    grupo2 = nula.deciles_de_volatilidad(sigma, np.zeros(1000, dtype=bool), 10)
    assert np.all(grupo2 == -1)


def test_el_sorteo_respeta_el_grupo_y_evita_la_propia_franja():
    rng = np.random.default_rng(0)
    # Dos grupos de candidatos. El grupo 10 tiene minutos de tres franjas.
    pools = {10: np.array([0, 1, 2, 3, 4, 5]), 20: np.array([6, 7, 8])}
    pos_franja_candidato = np.array([100, 100, 101, 101, 102, 102, 200, 201, 202])
    claves_evento = np.array([10, 10, 20])
    franja_evento = np.array([100, 101, 200])

    indices, usable = nula._sortear(rng, pools, claves_evento, franja_evento,
                                    pos_franja_candidato, repeticiones=200)
    assert usable.all()
    for i in range(3):
        sorteados = indices[:, i]
        esperado = pools[int(claves_evento[i])]
        assert np.all(np.isin(sorteados, esperado)), "salio de otro grupo"
        assert not np.any(pos_franja_candidato[sorteados] == franja_evento[i]), \
            "el evento se comparo consigo mismo"


def test_si_el_grupo_es_solo_la_propia_franja_el_evento_queda_fuera():
    rng = np.random.default_rng(0)
    pools = {10: np.array([0, 1, 2])}
    pos_franja_candidato = np.array([100, 100, 100])
    indices, usable = nula._sortear(rng, pools, np.array([10]), np.array([100]),
                                    pos_franja_candidato, repeticiones=20,
                                    intentos_max=5)
    assert not usable[0], "no hay con quien compararlo: debe quedar fuera"


# --- p-valores --------------------------------------------------------------

def test_la_formula_de_phipson_y_smyth():
    # Cinco nulas, ninguna alcanza al valor observado. Con la formula ingenua el
    # p-valor seria 0, que es imposible: lo observado tambien es un resultado
    # posible. Con la correccion queda 1/6.
    nulas = np.array([0.1, 0.2, 0.0, -0.1, -0.2])
    assert nula._p_una_cola(5.0, nulas, "mayor") == pytest.approx(1 / 6)
    assert nula._p_una_cola(-5.0, nulas, "menor") == pytest.approx(1 / 6)
    # Un valor observado en el medio deja muchas nulas tanto o mas extremas.
    assert nula._p_una_cola(0.0, nulas, "mayor") == pytest.approx(4 / 6)
    assert np.isnan(nula._p_una_cola(0.0, nulas, "dos"))


def test_el_p_de_dos_colas_se_centra_en_la_nula():
    nulas = np.array([1.0, 1.1, 0.9, 1.0, 1.2])     # centrada en 1.04, no en cero
    # Un observado igual al centro es lo menos extremo posible.
    assert nula._p_dos_colas(1.04, nulas) == pytest.approx(1.0)
    # Uno muy lejos del centro da el minimo posible.
    assert nula._p_dos_colas(50.0, nulas) == pytest.approx(1 / 6)


def test_el_p_valor_nunca_es_cero_ni_mayor_que_uno():
    cfg, barras, cal, ev = mercado()
    tabla, _ = nula.correr(barras, cal, ev, cfg, semilla=1, repeticiones=50)
    for columna in ["p_una_cola", "p_dos_colas"]:
        valores = tabla[columna].to_numpy(float)
        hay = np.isfinite(valores)
        assert np.all(valores[hay] >= 1 / 51 - 1e-12)
        assert np.all(valores[hay] <= 1.0)


# --- reproducibilidad y calibracion -----------------------------------------

def test_la_misma_semilla_da_el_mismo_resultado():
    cfg, barras, cal, ev = mercado()
    candidatos = nula.preparar_candidatos(barras, cal, cfg)
    a, _ = nula.correr(barras, cal, ev, cfg, semilla=5, repeticiones=60,
                       candidatos=candidatos)
    b, _ = nula.correr(barras, cal, ev, cfg, semilla=5, repeticiones=60,
                       candidatos=candidatos)
    c, _ = nula.correr(barras, cal, ev, cfg, semilla=6, repeticiones=60,
                       candidatos=candidatos)
    pd.testing.assert_frame_equal(a, b)
    assert not np.allclose(a["p_dos_colas"].to_numpy(float),
                           c["p_dos_colas"].to_numpy(float), equal_nan=True)


def test_sobre_ruido_puro_los_p_valores_no_se_amontonan_abajo():
    # Prueba rapida y aproximada: en mercados sin ningun patron, los p-valores
    # de la nula tienen que quedar repartidos. Si se amontonaran cerca de cero,
    # seria senal de que el emparejamiento no esta comparando peras con peras.
    todos = []
    for semilla in (11, 22, 33):
        cfg, barras, cal, ev = mercado(semilla=semilla, dias=120)
        tabla, _ = nula.correr(barras, cal, ev, cfg, semilla=semilla, repeticiones=200)
        todos.append(tabla["p_dos_colas"].to_numpy(float))
    p = np.concatenate(todos)
    p = p[np.isfinite(p)]

    assert len(p) >= 30
    assert 0.25 < p.mean() < 0.75, f"el promedio de los p-valores quedo en {p.mean():.3f}"
    assert np.mean(p <= 0.05) <= 0.20, "demasiados p-valores muy chicos para ser ruido"
    assert p.max() > 0.5, "ningun p-valor alto: la distribucion no se ve plana"


def test_la_nula_informa_cuantos_eventos_uso():
    cfg, barras, cal, ev = mercado()
    tabla, distribuciones = nula.correr(barras, cal, ev, cfg, semilla=1, repeticiones=40)
    assert set(tabla["tipo"]) == set(cfg.TIPOS_EVENTO)
    assert len(tabla) == len(cfg.TIPOS_EVENTO) * len(cfg.HORIZONTES)
    usadas = tabla[tabla["n_eventos"] > 0]
    assert len(usadas) > 0
    for _, fila in usadas.iterrows():
        assert len(distribuciones[(fila["tipo"], fila["horizonte"])]) == 40
    # "ruptura" es descriptivo: se informa a dos colas y no tiene cola definida.
    ruptura = tabla[tabla["tipo"] == "ruptura"]
    assert (ruptura["cola"] == "dos").all()
    assert ruptura["p_una_cola"].isna().all()
