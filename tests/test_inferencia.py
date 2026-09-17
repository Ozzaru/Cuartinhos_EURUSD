# -*- coding: utf-8 -*-
"""
Pruebas de la inferencia: minimos cuadrados agrupados, Holm y Romano-Wolf.

Holm se compara contra un calculo hecho a mano. Los errores agrupados se
comparan contra statsmodels, que es la implementacion de referencia.
"""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

import ayuda
from motor import inferencia


# --- minimos cuadrados con errores agrupados --------------------------------

@pytest.mark.parametrize("n, k, grupos", [(500, 4, 50), (2000, 8, 300), (150, 3, 12)])
def test_los_errores_agrupados_coinciden_con_statsmodels(n, k, grupos):
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(n), rng.normal(size=(n, k - 1))])
    dia = np.sort(rng.integers(0, grupos, n))
    efecto_del_dia = rng.normal(size=grupos)[dia]
    y = X @ np.arange(1.0, k + 1) + efecto_del_dia + rng.normal(size=n)

    inicio = np.flatnonzero(np.concatenate([[True], np.diff(dia) != 0]))
    beta, error, G = inferencia.ols_agrupado(y, X, inicio)

    referencia = sm.OLS(y, X).fit(cov_type="cluster",
                                  cov_kwds={"groups": dia, "use_correction": True})
    assert G == len(np.unique(dia))
    assert np.allclose(beta, referencia.params, rtol=1e-10, atol=1e-12)
    assert np.allclose(error, referencia.bse, rtol=1e-10, atol=1e-12)


def test_agrupar_por_dia_da_errores_mas_grandes_que_ignorar_la_agrupacion():
    # Si los eventos del mismo dia comparten shocks, tratarlos como
    # independientes infla la significancia. Esta prueba deja ese efecto a la
    # vista con datos donde el shock diario es grande.
    rng = np.random.default_rng(3)
    n, grupos = 1200, 40
    dia = np.sort(rng.integers(0, grupos, n))
    x = rng.normal(size=grupos)[dia]                 # el regresor vive al nivel del dia
    y = rng.normal(size=grupos)[dia] * 3 + rng.normal(size=n) * 0.1

    X = np.column_stack([np.ones(n), x])
    inicio = np.flatnonzero(np.concatenate([[True], np.diff(dia) != 0]))
    _, agrupado, _ = inferencia.ols_agrupado(y, X, inicio)
    ingenuo = sm.OLS(y, X).fit().bse
    assert agrupado[1] > 3 * ingenuo[1]


# --- Holm -------------------------------------------------------------------

def test_holm_contra_un_calculo_a_mano():
    # Cuatro p-valores. A mano, ordenados de menor a mayor:
    #   0.001 * 4 = 0.004
    #   0.010 * 3 = 0.030
    #   0.030 * 2 = 0.060
    #   0.040 * 1 = 0.040 -> pero no puede bajar, asi que queda en 0.060
    p = np.array([0.010, 0.001, 0.040, 0.030])
    esperado = np.array([0.030, 0.004, 0.060, 0.060])
    assert np.allclose(inferencia.holm(p), esperado)


def test_holm_nunca_pasa_de_uno_y_no_baja():
    p = np.array([0.2, 0.3, 0.5, 0.9])
    salida = inferencia.holm(p)
    assert np.all(salida <= 1.0)
    orden = np.argsort(p)
    assert np.all(np.diff(salida[orden]) >= -1e-12), "la lista corregida no puede bajar"
    assert np.all(salida >= p), "corregir nunca puede hacer un p-valor mas chico"


def test_holm_con_una_sola_prueba_no_cambia_nada():
    assert inferencia.holm(np.array([0.03]))[0] == pytest.approx(0.03)


def test_holm_ignora_las_pruebas_que_no_se_pudieron_correr():
    # Una prueba con p NaN (por ejemplo, un moderador que no varia) no ocupa
    # lugar en la familia: las otras tres se corrigen entre ellas.
    p = np.array([0.010, np.nan, 0.040, 0.030])
    salida = inferencia.holm(p)
    assert np.isnan(salida[1])
    assert salida[0] == pytest.approx(0.030)      # 0.010 * 3, no * 4


# --- Romano-Wolf ------------------------------------------------------------

def mercado_con_eventos(semilla=42, dias=200):
    cfg = ayuda.cfg_prueba()
    import motor
    from motor import moderadores
    idx = ayuda.indice("2016-01-04 00:00", dias * 24 * 60)
    velas = ayuda.camino_aleatorio(len(idx), semilla=semilla)
    barras, cal, ev = motor.preparar(ayuda.datos(velas, idx=idx), cfg)
    noticias = pd.DataFrame({
        "t_utc": pd.date_range("2016-01-05 13:30", periods=dias // 3, freq="3D", tz="UTC"),
        "tipo": ["ipc"] * (dias // 3)})
    ev = moderadores.agregar(barras, cal, ev, cfg, noticias=noticias)
    return cfg, barras, cal, ev


def test_romano_wolf_da_p_valores_ordenados_y_dentro_de_rango():
    cfg, _, _, ev = mercado_con_eventos()
    celdas, dias = inferencia.construir_celdas(ev, cfg)
    familia = cfg.FAMILIA_MODERADORES
    p = inferencia.romano_wolf(celdas, familia, dias, repeticiones=80, semilla=1)

    hay = np.isfinite(p)
    assert hay.any()
    assert np.all(p[hay] >= 0) and np.all(p[hay] <= 1)
    # El p-valor minimo posible con B remuestreos es 1 / (B + 1).
    assert np.all(p[hay] >= 1 / 81 - 1e-12)

    # Orden: una prueba con |t| mas grande no puede tener un p mas grande.
    tabla = inferencia.estadisticos(celdas, familia)
    t = np.abs(tabla["t"].to_numpy(float))
    juntos = np.isfinite(t) & hay
    orden = np.argsort(-t[juntos])
    assert np.all(np.diff(p[juntos][orden]) >= -1e-12)


def test_la_misma_semilla_da_el_mismo_resultado():
    cfg, _, _, ev = mercado_con_eventos()
    celdas, dias = inferencia.construir_celdas(ev, cfg)
    familia = cfg.FAMILIA_MODERADORES
    a = inferencia.romano_wolf(celdas, familia, dias, repeticiones=50, semilla=7)
    b = inferencia.romano_wolf(celdas, familia, dias, repeticiones=50, semilla=7)
    c = inferencia.romano_wolf(celdas, familia, dias, repeticiones=50, semilla=8)
    assert np.allclose(a, b, equal_nan=True), "misma semilla, mismo resultado"
    assert not np.allclose(a, c, equal_nan=True), "semillas distintas deberian diferir"


# --- tabla final ------------------------------------------------------------

def test_la_tabla_final_trae_todo_lo_que_pide_el_pre_registro():
    cfg, _, _, ev = mercado_con_eventos()
    tabla = inferencia.analizar(ev, cfg, cfg.FAMILIA_MODERADORES, semilla=1)
    for columna in ["tipo", "horizonte", "coeficiente", "estimacion", "error", "t",
                    "p_bruto", "p_holm", "p_romano_wolf", "p_corregido", "rechaza"]:
        assert columna in tabla.columns
    assert len(tabla) == len(cfg.FAMILIA_MODERADORES)
    # Sin pedir Romano-Wolf, esa columna queda vacia y no se usa.
    assert tabla["p_romano_wolf"].isna().all()
    assert cfg.CORRECCION_PRINCIPAL == "holm"
    assert np.allclose(tabla["p_corregido"].to_numpy(float),
                       tabla["p_holm"].to_numpy(float), equal_nan=True)


def test_los_p_brutos_se_pueden_reemplazar_por_los_de_la_nula():
    # La familia principal se corrige sobre los p-valores de la nula emparejada,
    # no sobre el t de una regresion.
    cfg, _, _, ev = mercado_con_eventos()
    inventados = {(tipo, h, "media"): 0.001
                  for tipo, h, _, _ in cfg.FAMILIA_PRINCIPAL}
    tabla = inferencia.analizar(ev, cfg, cfg.FAMILIA_PRINCIPAL, semilla=1,
                                p_brutos=inventados)
    assert np.allclose(tabla["p_bruto"].to_numpy(float), 0.001)
    # Ocho pruebas, todas con el mismo p: Holm las lleva a 0.008.
    assert np.allclose(tabla["p_holm"].to_numpy(float), 0.008)
    assert tabla["rechaza"].all()
