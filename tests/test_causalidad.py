# -*- coding: utf-8 -*-
"""
Prueba de causalidad: el futuro no puede cambiar el pasado.

Es la prueba mas importante del motor. Se corre el pipeline completo dos veces
sobre la misma serie, cambiando solo lo que ocurre DESPUES de un instante de
corte. Todo evento anterior o igual al corte, con sus moderadores, tiene que
salir exactamente igual en las dos corridas.

Si alguna vez falla, el mensaje no es "hay que ajustar el test": es que alguna
variable esta mirando hacia adelante.

El corte se pone a proposito a mitad de franja, que es donde una fuga intradia
se esconde mejor. Es la leccion que dejo el proyecto anterior
(Cuartinhos_Goty): con un margen de seguridad alrededor del corte, un motor
contaminado pasaba la prueba igual.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import tiempo

CORTE = "2020-06-19 09:13"          # jueves, a mitad de la franja [6,12) de Londres

COLUMNAS_A_COMPARAR = [
    "id_franja", "tipo", "direccion", "t_evento_utc", "t_ruptura_utc",
    "extremo_roto", "precio_evento", "sigma_ref",
    "dist_redondo_pips", "cerca_redondo", "cerca_extremo_previo",
    "ratio_compresion", "comprimida", "noticia",
]


def serie_larga(semilla=11):
    idx = ayuda.indice("2020-06-01 00:00", 25 * 24 * 60)
    velas = ayuda.camino_aleatorio(len(idx), semilla)
    return idx, velas


def hasta_el_corte(eventos, corte):
    t = tiempo.a_ns(pd.Timestamp(corte, tz="UTC"))
    recorte = eventos[eventos["t_evento_ns"] <= t]
    return recorte[COLUMNAS_A_COMPARAR].reset_index(drop=True)


def test_hay_suficientes_eventos_para_que_la_prueba_signifique_algo():
    idx, velas = serie_larga()
    cfg = ayuda.cfg_prueba()
    _, _, eventos = motor.preparar(ayuda.datos(velas, idx=idx), cfg)
    antes = hasta_el_corte(eventos, CORTE)
    assert len(antes) > 30, "sin eventos antes del corte la prueba no prueba nada"
    assert set(antes["tipo"]) == {"ruptura", "sostenida", "reingreso"}


def test_cambiar_el_futuro_no_cambia_ningun_evento_anterior_al_corte():
    idx, velas = serie_larga()
    cfg = ayuda.cfg_prueba()
    original = motor.preparar(ayuda.datos(velas, idx=idx), cfg)[2]

    # Se reemplaza todo lo posterior al corte por otro camino distinto. Se
    # cambian las barras que CIERRAN despues del corte, o sea las que abren en
    # el corte o despues: son exactamente las que en el corte aun no existen.
    t_corte = pd.Timestamp(CORTE, tz="UTC")
    futuro = idx >= t_corte
    otras = velas.copy()
    rng = np.random.default_rng(999)
    factor = np.exp(np.cumsum(rng.normal(0.0, 5e-4, int(futuro.sum()))))
    otras[futuro, :] = otras[futuro, :] * factor[:, None]
    assert not np.allclose(otras[futuro, 3], velas[futuro, 3]), "el futuro tiene que cambiar"

    modificado = motor.preparar(ayuda.datos(otras, idx=idx), cfg)[2]

    a = hasta_el_corte(original, CORTE)
    b = hasta_el_corte(modificado, CORTE)
    assert len(a) == len(b), "cambio la cantidad de eventos anteriores al corte"
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12, atol=1e-12)


def test_truncar_la_muestra_en_el_corte_tampoco_cambia_nada():
    # La otra cara de lo mismo: si los datos posteriores al corte no existen,
    # los eventos anteriores deben ser identicos.
    idx, velas = serie_larga()
    cfg = ayuda.cfg_prueba()
    completo = motor.preparar(ayuda.datos(velas, idx=idx), cfg)[2]

    t_corte = pd.Timestamp(CORTE, tz="UTC")
    hasta = idx < t_corte
    truncado = motor.preparar(ayuda.datos(velas[hasta], idx=idx[hasta]), cfg)[2]

    a = hasta_el_corte(completo, CORTE)
    b = hasta_el_corte(truncado, CORTE)
    assert len(a) == len(b), "truncar la muestra cambio la cantidad de eventos"
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12, atol=1e-12)


def test_los_retornos_si_dependen_del_futuro_como_corresponde():
    # El contraste, para que la prueba anterior no sea trivial: los RESULTADOS
    # SI tienen que cambiar cuando cambia el futuro. Si tambien salieran
    # identicos, la senal seria que no se esta midiendo nada.
    #
    # El corte se ancla a un evento real, cinco minutos despues de que ocurra:
    # su deteccion ya esta cerrada, pero su retorno a 60 minutos todavia no.
    idx, velas = serie_larga()
    cfg = ayuda.cfg_prueba()
    original = motor.preparar(ayuda.datos(velas, idx=idx), cfg)[2]

    con_retorno = original[np.isfinite(original["ret_60"])].reset_index(drop=True)
    elegido = con_retorno.iloc[len(con_retorno) // 2]
    corte = tiempo.de_ns(int(elegido["t_evento_ns"]) + 5 * tiempo.NS_MIN)

    otras = velas.copy()
    futuro = idx >= corte
    otras[futuro, :] = otras[futuro, :] * 1.002
    modificado = motor.preparar(ayuda.datos(otras, idx=idx), cfg)[2]

    misma = modificado[(modificado["t_evento_ns"] == elegido["t_evento_ns"])
                       & (modificado["tipo"] == elegido["tipo"])]
    assert len(misma) == 1, "el evento tiene que seguir existiendo"
    fila = misma.iloc[0]

    # La deteccion no se movio...
    assert fila["precio_evento"] == pytest.approx(elegido["precio_evento"])
    assert fila["extremo_roto"] == pytest.approx(elegido["extremo_roto"])
    assert fila["direccion"] == elegido["direccion"]
    # ...pero el resultado si.
    assert not np.isclose(fila["ret_60"], elegido["ret_60"]), \
        "el retorno a 60 minutos deberia haber cambiado al cambiar el futuro"


@pytest.mark.parametrize("corte", ["2020-06-10 03:07", "2020-06-15 14:41",
                                   "2020-06-22 21:58"])
def test_la_prueba_se_sostiene_en_varios_cortes(corte):
    idx, velas = serie_larga(semilla=7)
    cfg = ayuda.cfg_prueba()
    original = motor.preparar(ayuda.datos(velas, idx=idx), cfg)[2]

    futuro = idx >= pd.Timestamp(corte, tz="UTC")
    otras = velas.copy()
    otras[futuro, :] = otras[futuro, :] * 0.997
    modificado = motor.preparar(ayuda.datos(otras, idx=idx), cfg)[2]

    pd.testing.assert_frame_equal(hasta_el_corte(original, corte),
                                  hasta_el_corte(modificado, corte),
                                  check_exact=False, rtol=1e-12, atol=1e-12)
