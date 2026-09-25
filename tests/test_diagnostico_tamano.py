# -*- coding: utf-8 -*-
"""
Pruebas del diagnostico del tamano: dar vuelta la cola de un p de Phipson y
Smyth y los intervalos que remuestrean mercados.
"""
import numpy as np
import pandas as pd
import pytest

from experimentos import diagnostico_tamano as dt
from motor.nula import _p_una_cola


def test_el_p_de_la_cola_opuesta_coincide_con_calcularlo_directo():
    rng = np.random.default_rng(3)
    nulas = rng.normal(size=499)
    for observado in (-2.0, -0.3, 0.0, 0.7, 2.5):
        p = _p_una_cola(observado, nulas, "mayor")
        opuesto = dt.p_cola_opuesta([p], 499)[0]
        assert opuesto == pytest.approx(_p_una_cola(observado, nulas, "menor"))


def test_un_p_fuera_de_la_grilla_no_se_da_vuelta():
    with pytest.raises(ValueError):
        dt.p_cola_opuesta([0.0123], 499)


def pruebas_falsas(rechazos_hip, rechazos_opu, mercados=10, por_mercado=6):
    """`mercados` mercados; los primeros rechazan en la cola de la hipotesis o la opuesta."""
    filas = []
    for m in range(mercados):
        for j in range(por_mercado):
            hip = m < rechazos_hip and j == 0
            opu = m < rechazos_opu and j == 1
            filas.append({"mercado": m, "p_bruto": 0.01 if hip else 0.5,
                          "p_opuesto": 0.01 if opu else 0.5})
    return pd.DataFrame(filas)


def test_la_asimetria_resta_las_dos_colas_con_las_mismas_pruebas():
    hip, opu, dif, bajo, alto = dt.asimetria(pruebas_falsas(6, 3), 0.05, 500, semilla=1)
    assert hip == pytest.approx(6 / 60) and opu == pytest.approx(3 / 60)
    assert dif == pytest.approx(3 / 60)
    assert bajo <= dif <= alto


def test_la_diferencia_entre_bloques_es_cero_si_los_bloques_son_iguales():
    a = pruebas_falsas(4, 0)
    ta, tb, dif, bajo, alto = dt.diferencia_entre_bloques(a, a.copy(), "p_bruto", 0.05, 500, 1)
    assert ta == tb and dif == 0
    assert bajo <= 0 <= alto
