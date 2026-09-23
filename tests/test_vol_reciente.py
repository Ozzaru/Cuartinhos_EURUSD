# -*- coding: utf-8 -*-
"""
Pruebas de la volatilidad reciente y del estadistico estudentizado de H1 y H2.

Las dos piezas atacan la misma sospecha: un evento no es un minuto cualquiera.
Un reingreso ocurre justo despues de una expansion, asi que llega con la
volatilidad reciente alta por construccion, y si su comparacion no comparte esa
caracteristica, no estan midiendo lo mismo.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import franjas, inferencia, nula, resultados, tiempo


# --- volatilidad reciente ---------------------------------------------------

def test_la_volatilidad_reciente_mide_lo_que_dice():
    # Serie con retornos de 1 minuto de tamano exacto r, alternando: la
    # desviacion tipica de esa ventana tiene que dar exactamente r.
    cfg = ayuda.cfg_prueba(VENTANA_VOL_RECIENTE_MIN=60, MIN_BARRAS_VOL_RECIENTE=30)
    r = 1e-4
    n = 300
    idx = ayuda.indice("2020-06-15 00:00", n)
    cierres = 1.10 * np.exp(np.where(np.arange(n) % 2 == 1, r, 0.0))
    velas = ayuda.velas_de_cierres(cierres)
    barras = franjas.Barras.desde(ayuda.datos(velas, idx=idx), cfg)

    vol = resultados.volatilidad_reciente(barras, cfg)
    assert np.isnan(vol[:30]).all(), "sin historia suficiente tiene que ser NaN"
    assert vol[100] == pytest.approx(r, rel=1e-9)
    assert vol[-1] == pytest.approx(r, rel=1e-9)


def test_la_volatilidad_reciente_solo_usa_el_pasado():
    # Se cambia el futuro a partir de un minuto y la volatilidad reciente de
    # los minutos anteriores no se mueve ni un decimal.
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2020-06-15 00:00", 600)
    velas = ayuda.camino_aleatorio(len(idx), semilla=4)
    barras = franjas.Barras.desde(ayuda.datos(velas, idx=idx), cfg)
    original = resultados.volatilidad_reciente(barras, cfg)

    otras = velas.copy()
    otras[400:, :] *= 1.01
    barras2 = franjas.Barras.desde(ayuda.datos(otras, idx=idx), cfg)
    modificada = resultados.volatilidad_reciente(barras2, cfg)

    assert np.allclose(original[:400], modificada[:400], equal_nan=True)
    assert not np.allclose(original[400:], modificada[400:], equal_nan=True)


def test_los_retornos_que_cruzan_un_hueco_no_cuentan():
    cfg = ayuda.cfg_prueba(VENTANA_VOL_RECIENTE_MIN=60, MIN_BARRAS_VOL_RECIENTE=10)
    idx = ayuda.indice("2020-06-15 00:00", 400)
    fuera = (idx >= pd.Timestamp("2020-06-15 03:00", tz="UTC")) & \
            (idx < pd.Timestamp("2020-06-15 05:00", tz="UTC"))
    idx = idx[~fuera]
    velas = ayuda.camino_aleatorio(len(idx), semilla=5)
    barras = franjas.Barras.desde(ayuda.datos(velas, idx=idx), cfg)

    vol = resultados.volatilidad_reciente(barras, cfg)
    # El salto de precio a traves del hueco de dos horas seria enorme si
    # contara como un retorno de un minuto.
    justo_despues = np.searchsorted(barras.apertura_ns,
                                    tiempo.a_ns(pd.Timestamp("2020-06-15 05:00", tz="UTC")))
    finitos = vol[np.isfinite(vol)]
    assert vol[justo_despues] <= np.percentile(finitos, 99.9)


def test_los_grupos_de_volatilidad_reciente_quedan_parejos():
    vol = np.linspace(1e-5, 1e-3, 900)
    disponible = np.ones(900, dtype=bool)
    grupo = nula.grupos_de_volatilidad_reciente(vol, disponible, 3)
    cuentas = np.bincount(grupo, minlength=4)
    assert cuentas[3] == 0, "sin NaN no deberia usarse el grupo 'sin dato'"
    assert cuentas[:3].min() >= 290 and cuentas[:3].max() <= 310


def test_los_minutos_sin_historia_van_a_su_propio_grupo():
    vol = np.concatenate([np.full(100, np.nan), np.linspace(1e-5, 1e-3, 300)])
    grupo = nula.grupos_de_volatilidad_reciente(vol, np.ones(400, dtype=bool), 3)
    assert (grupo[:100] == 3).all(), "sin dato es un grupo aparte, no el grupo 0"
    assert set(np.unique(grupo[100:])) == {0, 1, 2}


# --- media con error agrupado ----------------------------------------------

@pytest.mark.parametrize("n, grupos", [(400, 40), (1500, 200), (90, 9)])
def test_la_media_agrupada_coincide_con_la_regresion(n, grupos):
    rng = np.random.default_rng(1)
    dia = np.sort(rng.integers(0, grupos, n))
    y = rng.normal(size=grupos)[dia] + rng.normal(size=n) * 0.3

    media, error, t = inferencia.media_agrupada(y, dia)

    inicio = np.flatnonzero(np.concatenate([[True], np.diff(dia) != 0]))
    beta, error_ref, _ = inferencia.ols_agrupado(y, np.ones((n, 1)), inicio)
    assert media == pytest.approx(float(beta[0]), rel=1e-12)
    assert error == pytest.approx(float(error_ref[0]), rel=1e-10)
    assert t == pytest.approx(media / error, rel=1e-12)


def test_la_media_agrupada_no_depende_del_orden_de_las_filas():
    rng = np.random.default_rng(2)
    dia = rng.integers(0, 30, 300)
    y = rng.normal(size=300)
    orden = rng.permutation(300)
    a = inferencia.media_agrupada(y, dia)
    b = inferencia.media_agrupada(y[orden], dia[orden])
    assert np.allclose(a, b, equal_nan=True)


def test_agrupar_por_dia_ensancha_el_error_de_la_media():
    # Si todos los eventos de un dia comparten el mismo shock, el error de la
    # media tiene que ser mucho mayor que el ingenuo.
    rng = np.random.default_rng(3)
    dia = np.repeat(np.arange(30), 40)
    y = np.repeat(rng.normal(size=30), 40) + rng.normal(size=1200) * 0.01
    _, error, _ = inferencia.media_agrupada(y, dia)
    ingenuo = y.std(ddof=1) / np.sqrt(len(y))
    assert error > 4 * ingenuo


# --- la nula usa las dos piezas --------------------------------------------

def mercado_de_prueba(semilla=3, dias=200):
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2016-01-04 00:00", dias * 24 * 60)
    velas = ayuda.camino_aleatorio(len(idx), semilla=semilla)
    barras, cal, ev = motor.preparar(ayuda.datos(velas, idx=idx), cfg)
    return cfg, barras, cal, ev


def test_la_nula_informa_las_dos_versiones_del_estadistico():
    cfg, barras, cal, ev = mercado_de_prueba()
    tabla, _ = nula.correr(barras, cal, ev, cfg, semilla=1, repeticiones=60)
    for columna in ["media_observada", "t_observado", "p_una_cola_media",
                    "p_una_cola_t", "p_dos_colas_media", "p_dos_colas_t"]:
        assert columna in tabla.columns

    usadas = tabla[tabla["n_eventos"] > 0]
    assert len(usadas) > 0
    # Con PRINCIPAL_ESTUDENTIZADO, la columna que usa el resto del programa
    # apunta a la version del estadistico t.
    assert cfg.PRINCIPAL_ESTUDENTIZADO
    assert np.allclose(usadas["p_una_cola"].to_numpy(float),
                       usadas["p_una_cola_t"].to_numpy(float), equal_nan=True)
    # Y el signo del t sigue al de la media.
    con_datos = usadas[np.isfinite(usadas["t_observado"])]
    assert np.all(np.sign(con_datos["t_observado"].to_numpy(float))
                  == np.sign(con_datos["media_observada"].to_numpy(float)))


def test_apagar_el_estudentizado_devuelve_la_version_de_la_media():
    cfg = ayuda.cfg_prueba(PRINCIPAL_ESTUDENTIZADO=False)
    _, barras, cal, ev = mercado_de_prueba()
    tabla, _ = nula.correr(barras, cal, ev, cfg, semilla=1, repeticiones=60)
    usadas = tabla[tabla["n_eventos"] > 0]
    assert np.allclose(usadas["p_una_cola"].to_numpy(float),
                       usadas["p_una_cola_media"].to_numpy(float), equal_nan=True)


def test_la_nula_solo_sortea_minutos_del_mismo_grupo_de_volatilidad_reciente(monkeypatch):
    cfg, barras, cal, ev = mercado_de_prueba()
    candidatos = nula.preparar_candidatos(barras, cal, cfg)
    grupo_cand = candidatos["grupo_reciente"]

    registro = []
    original = nula._sortear

    def espia(rng, pools, claves, franja_evento, pos_cand, repeticiones, **kw):
        indices, usable = original(rng, pools, claves, franja_evento, pos_cand,
                                   repeticiones, **kw)
        registro.append((claves.copy(), indices.copy(), usable.copy()))
        return indices, usable

    monkeypatch.setattr(nula, "_sortear", espia)
    nula.correr(barras, cal, ev, cfg, semilla=1, repeticiones=10,
                candidatos=candidatos)

    revisados = 0
    for claves, indices, usable in registro:
        if not usable.any():
            continue
        grupo_evento = claves % 10          # la ultima cifra de la clave
        for i in np.flatnonzero(usable):
            assert np.all(grupo_cand[indices[:, i]] == grupo_evento[i]), \
                "se sorteo un minuto con otra volatilidad reciente"
            revisados += 1
    assert revisados > 50
