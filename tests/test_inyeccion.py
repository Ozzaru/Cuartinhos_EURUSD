# -*- coding: utf-8 -*-
"""
Pruebas de la inyeccion de un efecto conocido (simulacion/inyeccion.py).

Tres cosas tienen que ser ciertas para que la curva de potencia mida lo que
dice medir:

  1. el retorno normalizado de un evento sube EXACTAMENTE delta, en la
     direccion que predice su hipotesis, a cualquier horizonte dentro de su
     franja, y menos por construccion si el horizonte cruza el fin;
  2. el efecto empieza despues del evento: ninguna barra que cierra en t o
     antes se toca;
  3. las barras siguen siendo barras: maximo arriba, minimo abajo, ask sobre
     bid, y cada apertura empalma con el cierre anterior.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import tiempo
from simulacion import inyeccion, mercado

DELTA = 0.2


def evento(t, tipo="sostenida", direccion=1, sigma=1e-4, minutos=100):
    """Una fila de evento con lo minimo que necesita la inyeccion."""
    return pd.DataFrame([{"tipo": tipo, "direccion": direccion, "sigma_ref": sigma,
                          "h_fin_franja": float(minutos),
                          "t_evento_ns": tiempo.a_ns(pd.Timestamp(t, tz="UTC"))}])


def serie_plana(minutos=400, inicio="2020-06-02 08:00"):
    idx = ayuda.indice(inicio, minutos)
    return ayuda.datos(ayuda.plano(minutos, 1.10), idx=idx), idx


def mid_close(datos):
    return ((datos["bid_close"] + datos["ask_close"]) / 2).to_numpy()


# --- el tamano y la forma del efecto ----------------------------------------

@pytest.mark.parametrize("h", [1, 30, 60, 100])
def test_dentro_de_la_franja_el_retorno_normalizado_sube_exactamente_delta(h):
    datos, idx = serie_plana()
    t = "2020-06-02 09:00"
    sigma = 1.3e-4
    nuevo = inyeccion.inyectar(datos, evento(t, sigma=sigma, minutos=100), DELTA,
                               ayuda.cfg_prueba())
    j0 = ayuda.posicion(idx, t) - 1                       # la barra que cierra en t
    jh = j0 + h
    antes = np.log(mid_close(datos)[jh]) - np.log(mid_close(datos)[j0])
    despues = np.log(mid_close(nuevo)[jh]) - np.log(mid_close(nuevo)[j0])
    assert (despues - antes) / (sigma * np.sqrt(h)) == pytest.approx(DELTA, rel=1e-9)


def test_si_el_horizonte_cruza_el_fin_de_franja_el_delta_realizado_es_menor():
    datos, idx = serie_plana()
    t = "2020-06-02 09:00"
    sigma, minutos, h = 1e-4, 40, 160
    nuevo = inyeccion.inyectar(datos, evento(t, sigma=sigma, minutos=minutos), DELTA,
                               ayuda.cfg_prueba())
    j0 = ayuda.posicion(idx, t) - 1
    cambio = np.log(mid_close(nuevo)[j0 + h]) - np.log(mid_close(datos)[j0 + h])
    realizado = cambio / (sigma * np.sqrt(h))
    assert realizado == pytest.approx(DELTA * np.sqrt(minutos / h), rel=1e-9)
    assert realizado < DELTA


def test_el_reingreso_se_devuelve_y_la_sostenida_continua_en_la_direccion_de_la_ruptura():
    datos, idx = serie_plana()
    t = "2020-06-02 09:00"
    j = ayuda.posicion(idx, t) - 1 + 30
    cfg = ayuda.cfg_prueba()
    base = np.log(mid_close(datos)[j])
    for tipo, direccion, signo in [("sostenida", 1, 1), ("sostenida", -1, -1),
                                   ("reingreso", 1, -1), ("reingreso", -1, 1)]:
        nuevo = inyeccion.inyectar(datos, evento(t, tipo=tipo, direccion=direccion), DELTA, cfg)
        assert np.sign(np.log(mid_close(nuevo)[j]) - base) == signo, (tipo, direccion)


def test_la_ruptura_no_recibe_efecto_y_delta_cero_no_cambia_nada():
    datos, _ = serie_plana()
    cfg = ayuda.cfg_prueba()
    ruptura = inyeccion.inyectar(datos, evento("2020-06-02 09:00", tipo="ruptura"), DELTA, cfg)
    pd.testing.assert_frame_equal(ruptura, datos)
    cero = inyeccion.inyectar(datos, evento("2020-06-02 09:00"), 0.0, cfg)
    pd.testing.assert_frame_equal(cero, datos)


def test_dos_eventos_suman_sus_derivas():
    x = np.arange(0, 300) * tiempo.NS_MIN
    uno = {"t_ns": np.array([10 * tiempo.NS_MIN]), "amplitud": np.array([2.0]),
           "minutos": np.array([50])}
    otro = {"t_ns": np.array([30 * tiempo.NS_MIN]), "amplitud": np.array([-1.0]),
            "minutos": np.array([100])}
    juntos = {k: np.concatenate([uno[k], otro[k]]) for k in uno}
    np.testing.assert_allclose(inyeccion.deriva(x, juntos, DELTA),
                               inyeccion.deriva(x, uno, DELTA) + inyeccion.deriva(x, otro, DELTA))


# --- causalidad --------------------------------------------------------------

def test_ninguna_barra_que_cierra_en_el_evento_o_antes_cambia():
    datos, idx = serie_plana()
    t = "2020-06-02 09:00"
    nuevo = inyeccion.inyectar(datos, evento(t), DELTA, ayuda.cfg_prueba())
    j0 = ayuda.posicion(idx, t) - 1                       # cierra justo en t
    pd.testing.assert_frame_equal(nuevo.iloc[:j0 + 1], datos.iloc[:j0 + 1])
    assert not np.allclose(nuevo["bid_close"].iloc[j0 + 1], datos["bid_close"].iloc[j0 + 1])


# --- las barras siguen siendo barras -----------------------------------------

@pytest.fixture(scope="module")
def mercado_inyectado():
    """Un mes de mercado simulado, con el efecto inyectado sobre sus eventos reales."""
    cfg = ayuda.cfg_prueba()
    datos, noticias = mercado.generar(1, 5, cfg)
    datos = datos[datos.index < datos.index[0] + pd.Timedelta(days=45)]
    _, _, eventos = motor.preparar(datos, cfg, noticias=noticias)
    return datos, inyeccion.inyectar(datos, eventos, DELTA, cfg), eventos, cfg


def test_las_barras_inyectadas_siguen_siendo_coherentes(mercado_inyectado):
    datos, nuevo, eventos, cfg = mercado_inyectado
    assert nuevo.index.equals(datos.index)
    assert list(nuevo.columns) == list(datos.columns)
    assert np.isfinite(nuevo.to_numpy()).all() and (nuevo.to_numpy() > 0).all()
    for lado in ("bid", "ask"):
        o, h = nuevo[f"{lado}_open"], nuevo[f"{lado}_high"]
        l, c = nuevo[f"{lado}_low"], nuevo[f"{lado}_close"]
        assert (h >= np.maximum(o, c)).all(), f"{lado}: un maximo quedo por debajo"
        assert (l <= np.minimum(o, c)).all(), f"{lado}: un minimo quedo por encima"
    for campo in inyeccion.LADOS:
        assert (nuevo[f"ask_{campo}"] >= nuevo[f"bid_{campo}"]).all()


def test_cada_apertura_sigue_empalmando_con_el_cierre_anterior(mercado_inyectado):
    datos, nuevo, _, _ = mercado_inyectado
    abre = ((datos["bid_open"] + datos["ask_open"]) / 2).to_numpy()
    cierra = mid_close(datos)
    contiguo = np.diff(tiempo.a_ns(datos.index)) == tiempo.NS_MIN
    empalmaba = contiguo & np.isclose(abre[1:], cierra[:-1], rtol=0, atol=1e-12)
    assert empalmaba.mean() > 0.9, "el simulador tendria que empalmar casi siempre"

    abre_n = ((nuevo["bid_open"] + nuevo["ask_open"]) / 2).to_numpy()
    cierra_n = mid_close(nuevo)
    np.testing.assert_allclose(abre_n[1:][empalmaba], cierra_n[:-1][empalmaba],
                               rtol=1e-12)


def test_el_efecto_se_inyecto_de_verdad_sobre_los_eventos_del_mercado(mercado_inyectado):
    datos, nuevo, eventos, cfg = mercado_inyectado
    efectos = inyeccion.inyectables(eventos, cfg)
    assert len(efectos["t_ns"]) > 20
    assert set(eventos.loc[eventos["t_evento_ns"].isin(efectos["t_ns"]), "tipo"]) \
        <= {"sostenida", "reingreso"}
    assert not np.allclose(mid_close(nuevo), mid_close(datos))
