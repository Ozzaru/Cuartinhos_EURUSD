# -*- coding: utf-8 -*-
"""
Pruebas de la potencia de H3 y H4 (punto F).

Lo que hace valido el atajo, comprobado contra el calculo directo:
  - H3: sumar delta al retorno de los eventos con el moderador encendido mueve
    el coeficiente exactamente delta y deja igual el error agrupado;
  - H4: sumar delta a los eventos con anuncio y volver a correr la nula (misma
    semilla) da el mismo p que el calculo en la grilla.
Y las cuentas: Holm por filas es Holm, el p de dos colas es el de la
regresion, el conteo de dias tratados y el intervalo del efecto minimo.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from experimentos import potencia_moderadores as pm
from motor import inferencia, nula
from simulacion import mercado

SEMILLA = 8
REPETICIONES = 40


@pytest.fixture(scope="module")
def mercado_f():
    """Un ano de mercado sin patron, con el calendario de la lista cerrada."""
    cfg = ayuda.cfg_prueba(ANUNCIOS_SIMULADOS=ayuda.cfg_prueba().ANUNCIOS_SIMULADOS_LISTA_CERRADA)
    datos, noticias = mercado.generar(1, SEMILLA, cfg)
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    return cfg, barras, cal, eventos, noticias, candidatos


# --- Holm por filas y p de dos colas ------------------------------------------

def test_holm_por_filas_es_holm_fila_por_fila():
    rng = np.random.default_rng(3)
    p = rng.uniform(0, 0.2, size=(30, 7))
    p[rng.uniform(size=p.shape) < 0.2] = np.nan
    p[0, :] = np.nan                          # una fila sin ninguna prueba
    p[1, :3] = 0.01                           # empates
    esperado = np.vstack([inferencia.holm(fila) for fila in p])
    assert np.allclose(pm.holm_por_filas(p), esperado, equal_nan=True, rtol=0, atol=1e-15)


def test_el_p_de_dos_colas_es_el_de_la_regresion(mercado_f):
    cfg, _, _, eventos, _, _ = mercado_f
    h3 = pm.estadisticos_h3(eventos, cfg)
    celdas, _ = inferencia.construir_celdas(eventos, cfg)
    directo = inferencia.estadisticos(celdas, cfg.FAMILIA_MODERADORES)
    p = pm.p_dos_colas_t(h3["beta"] / h3["error"], h3["grupos"])
    assert np.allclose(p, directo["p_bruto"], equal_nan=True, rtol=0, atol=1e-12)
    assert np.allclose(h3["beta"], directo["estimacion"], equal_nan=True, rtol=0, atol=0)


# --- el atajo de H3 -----------------------------------------------------------

def test_sumar_delta_al_subgrupo_mueve_el_coeficiente_delta_y_no_toca_el_error(mercado_f):
    cfg, _, _, eventos, _, _ = mercado_f
    base = pm.estadisticos_h3(eventos, cfg)
    delta, tipo, mod = 0.3, "reingreso", "cerca_redondo"
    movidos = eventos.copy()
    elegir = (movidos["tipo"] == tipo) & (movidos[mod] == 1.0)
    for h in cfg.HORIZONTES:
        movidos.loc[elegir, f"ret_{h}"] += -delta     # reingreso: signo -1
    nuevo = pm.estadisticos_h3(movidos, cfg)
    en = (base["tipo"] == tipo) & (base["coeficiente"] == mod)
    assert en.sum() == len(cfg.HORIZONTES)
    assert np.allclose(nuevo.loc[en, "beta"] - base.loc[en, "beta"], -delta, rtol=0, atol=1e-10)
    assert np.allclose(nuevo["error"], base["error"], rtol=1e-9, atol=0)
    # Las demas pruebas del mismo tipo (otros moderadores) no se mueven.
    otras = (base["tipo"] == tipo) & ~en
    assert np.allclose(nuevo.loc[otras, "beta"], base.loc[otras, "beta"], rtol=0, atol=1e-10)


def test_la_potencia_de_h3_en_delta_cero_es_el_tamano_y_sube_con_delta():
    cfg = ayuda.cfg_prueba(GRILLA_POTENCIA_H3=[0.0, 0.5, 5.0])
    filas = []
    for mercado_id in range(3):
        for t, h, c, _ in cfg.FAMILIA_MODERADORES:
            filas.append({"mercado": mercado_id, "tipo": t, "horizonte": str(h),
                          "coeficiente": c, "beta": 0.0, "error": 0.1, "grupos": 500})
    rechazos, tamano = pm.rechazos_h3(pd.DataFrame(filas), cfg)
    assert tamano["familia"] == 0.0 and tamano["por_prueba"] == 0.0
    matriz = rechazos[("comprimida", "sostenida", "30")]
    assert list(matriz.columns) == [0.0, 0.5, 5.0]
    assert (matriz[0.0] == 0).all() and (matriz[5.0] == 1).all()


# --- el atajo de H4 -----------------------------------------------------------

def test_h4_en_la_grilla_reproduce_la_nula_con_los_tratados_movidos(mercado_f):
    cfg, barras, cal, eventos, _, candidatos = mercado_f
    tabla, dist = nula.correr_h4(barras, cal, eventos, cfg, SEMILLA, repeticiones=REPETICIONES,
                                 candidatos=candidatos, con_distribuciones=True)
    grilla = pm.h4_en_grilla(tabla, dist, [0.0, 0.4])
    cero = grilla[grilla["delta"] == 0.0].reset_index(drop=True)
    assert np.allclose(cero["p"], tabla["p_estudentizado"], equal_nan=True, rtol=0, atol=0)

    movidos = eventos.copy()
    tratado = movidos["noticia"] == 1.0
    assert tratado.any()
    for h in cfg.HORIZONTES:
        movidos.loc[tratado, f"ret_{h}"] += 0.4
    directo = nula.correr_h4(barras, cal, movidos, cfg, SEMILLA, repeticiones=REPETICIONES,
                             candidatos=candidatos)
    movida = grilla[grilla["delta"] == 0.4].reset_index(drop=True)
    assert np.allclose(movida["p"], directo["p_estudentizado"], equal_nan=True, rtol=0, atol=0)
    assert np.allclose(movida["estimacion"], directo["diferencia"], equal_nan=True,
                       rtol=0, atol=1e-10)


def test_la_prueba_de_h4_sin_dias_suficientes_no_rechaza_nunca():
    cfg = ayuda.cfg_prueba(MIN_DIAS_TRATADOS=15)
    filas = []
    for mercado_id in range(2):
        for t, h, _, _ in cfg.FAMILIA_H4:
            for delta in (0.0, 1.0):
                dias = 10 if t == "sostenida" else 40
                filas.append({"mercado": mercado_id, "tipo": t, "horizonte": str(h),
                              "delta": delta, "p": 0.5 if delta == 0 else 0.001,
                              "estimacion": delta + 0.01, "dias_tratados": dias})
    rechazos, entra, tamano = pm.rechazos_h4(pd.DataFrame(filas), cfg)
    assert entra[("sostenida", "30")] == 0.0 and entra[("reingreso", "30")] == 1.0
    assert (rechazos[("sostenida", "30")].to_numpy() == 0).all()
    assert (rechazos[("reingreso", "30")][1.0] == 1).all()
    assert tamano["pruebas"] == 2 * len(cfg.HORIZONTES)


# --- conteos --------------------------------------------------------------------

def test_los_dias_tratados_cuentan_dias_distintos_y_el_bce_suma(mercado_f):
    cfg, _, cal, eventos, noticias, _ = mercado_f
    conteos = pm.conteos_del_mercado(eventos, cal, noticias, cfg, anios=1)
    for fila in conteos.itertuples(index=False):
        sub = eventos[(eventos["tipo"] == fila.tipo) & (eventos["noticia"] == 1.0)]
        assert fila.dias_tratados == sub["fecha_londres"].nunique()
        assert fila.dias_sin_bce_por_anio <= fila.dias_tratados_por_anio
        assert fila.dias_tratados_por_anio <= fila.dias_franja_por_anio
        assert 0.0 <= fila.prev_cerca_redondo <= 1.0
    assert conteos["anuncios_por_anio"].iloc[0] == len(noticias)


# --- efecto minimo detectable y aproximacion ------------------------------------

def test_si_todos_los_mercados_son_iguales_el_intervalo_se_cierra_en_el_punto():
    # Entre 0,1 (potencia 0) y 0,2 (potencia 1), el 80% queda en 0,18.
    rechazos = pd.DataFrame([[0, 0, 1, 1]] * 20, columns=[0.0, 0.1, 0.2, 0.3])
    efecto, bajo, alto = pm.efecto_minimo_con_ic(rechazos, 0.8, 200, 1)
    assert (efecto, bajo, alto) == pytest.approx((0.18, 0.18, 0.18))


def test_si_la_curva_no_llega_el_borde_alto_es_infinito():
    rechazos = pd.DataFrame([[0, 1]] * 5 + [[0, 0]] * 15, columns=[0.0, 0.1])
    efecto, _, alto = pm.efecto_minimo_con_ic(rechazos, 0.8, 200, 1)
    assert np.isnan(efecto) and np.isinf(alto)


def test_la_aproximacion_escala_con_la_raiz_del_tamano_de_los_grupos():
    a = pm.mde_aproximado(1.0, 100, 900, 0.05, 1, 2, 0.8)
    b = pm.mde_aproximado(1.0, 400, 3600, 0.05, 1, 2, 0.8)
    assert a == pytest.approx(2 * b)
    assert a == pytest.approx((1.959964 + 0.841621) * np.sqrt(1 / 100 + 1 / 900), rel=1e-5)
    assert np.isnan(pm.mde_aproximado(1.0, 0, 900, 0.05, 1, 2, 0.8))
