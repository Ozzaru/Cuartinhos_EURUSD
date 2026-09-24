# -*- coding: utf-8 -*-
"""
Pruebas de las piezas del control positivo.

La corrida completa tarda y no cabe en la bateria de tests. Lo que si se prueba
son las cuentas que despues se leen en el reporte (potencia, efecto minimo
detectable, delta realizado, traduccion a pips), mas una corrida minima de
punta a punta para ver que la cadena inyeccion -> motor -> nula -> inferencia
entrega lo que se espera.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
from experimentos import control_positivo as cp


# --- efecto minimo detectable -----------------------------------------------

def test_el_efecto_minimo_se_interpola_entre_los_dos_puntos_que_rodean_el_objetivo():
    deltas = [0, 0.05, 0.10, 0.20]
    potencias = [0.05, 0.40, 0.90, 1.0]
    # Entre 0,05 (0,40) y 0,10 (0,90): 0,80 queda a 4/5 del tramo.
    assert cp.efecto_minimo_detectable(deltas, potencias, 0.80) == pytest.approx(0.09)


def test_si_la_curva_no_llega_el_efecto_minimo_no_se_inventa():
    assert np.isnan(cp.efecto_minimo_detectable([0, 0.1, 0.2], [0.05, 0.3, 0.6], 0.80))


def test_el_orden_de_entrada_no_importa():
    assert cp.efecto_minimo_detectable([0.2, 0, 0.1], [1.0, 0.0, 0.5], 0.75) == \
        pytest.approx(cp.efecto_minimo_detectable([0, 0.1, 0.2], [0.0, 0.5, 1.0], 0.75))


# --- rechazos y potencia ----------------------------------------------------

def curva_falsa():
    """Dos mercados, un delta, las dos celdas confirmatorias de 30 minutos."""
    filas = []
    for mercado, (p_s, p_r) in enumerate([(0.001, 0.5), (0.5, 0.5)]):
        filas += [
            {"mercado": mercado, "anios": 4, "delta": 0.1, "tipo": "sostenida",
             "horizonte": "30", "confirmatoria": True, "media_observada": 0.12,
             "media_nula": 0.01, "estimacion": 0.12, "p_holm": p_s, "p_romano_wolf": p_s},
            {"mercado": mercado, "anios": 4, "delta": 0.1, "tipo": "reingreso",
             "horizonte": "30", "confirmatoria": True, "media_observada": -0.1,
             "media_nula": 0.0, "estimacion": -0.1, "p_holm": p_r, "p_romano_wolf": p_r},
        ]
    return pd.DataFrame(filas)


def test_la_potencia_por_familia_cuenta_mercados_con_algun_rechazo_correcto():
    cfg = ayuda.cfg_prueba()
    familia = cp.potencia_por_familia(cp.marcar_rechazos(curva_falsa(), cfg), cfg)
    fila = familia.iloc[0]
    assert fila["mercados"] == 2
    assert fila[f"rechaza_holm_{cfg.ALFA}"] == pytest.approx(0.5)


def test_un_rechazo_con_el_signo_equivocado_no_cuenta_como_potencia():
    cfg = ayuda.cfg_prueba()
    curva = curva_falsa()
    # La sostenida del mercado 0 "rechaza", pero su estimacion va al reves.
    curva.loc[0, ["media_observada", "estimacion"]] = -0.2
    marcada = cp.marcar_rechazos(curva, cfg)
    assert not marcada.loc[0, f"rechaza_holm_{cfg.ALFA}"]
    assert not marcada.loc[0, f"rechaza_romano_wolf_{cfg.ALFA}"]


def test_el_alfa_estricto_rechaza_menos_o_igual():
    cfg = ayuda.cfg_prueba()
    curva = curva_falsa()
    curva.loc[0, "p_holm"] = 0.04                    # pasa con 0,05, no con 0,025
    marcada = cp.marcar_rechazos(curva, cfg)
    assert marcada.loc[0, f"rechaza_holm_{cfg.ALFA}"]
    assert not marcada.loc[0, f"rechaza_holm_{cfg.ALFA_ESTRICTO}"]


def test_las_pruebas_no_confirmatorias_no_suman_potencia():
    cfg = ayuda.cfg_prueba()
    curva = curva_falsa()
    curva["confirmatoria"] = False
    familia = cp.potencia_por_familia(cp.marcar_rechazos(curva, cfg), cfg)
    assert len(familia) == 0


# --- delta realizado --------------------------------------------------------

def test_el_delta_realizado_se_mide_en_la_direccion_de_cada_hipotesis():
    cfg = ayuda.cfg_prueba()
    filas = []
    for delta in (0, 0.1):
        for tipo, signo in (("sostenida", 1), ("reingreso", -1)):
            filas.append({"mercado": 1, "anios": 4, "delta": delta, "tipo": tipo,
                          "horizonte": "60", "media_observada": 0.01 + signo * delta,
                          "media_nula": 0.01})
    tabla = cp.delta_realizado(pd.DataFrame(filas), cfg)
    con_efecto = tabla[tabla["delta"] == 0.1].set_index("tipo")
    assert con_efecto.loc["sostenida", "realizado"] == pytest.approx(0.1)
    assert con_efecto.loc["reingreso", "realizado"] == pytest.approx(0.1)
    assert con_efecto.loc["reingreso", "sesgo"] == pytest.approx(0.0)


# --- unidades ---------------------------------------------------------------

def test_el_factor_de_pips_es_sigma_por_raiz_de_h_por_precio_sobre_el_pip():
    cfg = ayuda.cfg_prueba()
    eventos = pd.DataFrame([{
        "tipo": "sostenida", "idx_franja": 2, "sigma_ref": 1e-4, "precio_evento": 1.2,
        "h_fin_franja": 100.0, **{f"ret_{h}": 0.1 for h in cfg.HORIZONTES}}])
    factores = cp.factores_pips(eventos, cfg).set_index("horizonte")["factor"]
    assert factores["60"] == pytest.approx(1e-4 * np.sqrt(60) * 1.2 / cfg.PIP)
    assert factores["fin_franja"] == pytest.approx(1e-4 * 10 * 1.2 / cfg.PIP)


def test_un_evento_sin_retorno_a_ese_horizonte_no_entra_en_la_traduccion():
    cfg = ayuda.cfg_prueba()
    eventos = pd.DataFrame([{
        "tipo": "reingreso", "idx_franja": 1, "sigma_ref": 1e-4, "precio_evento": 1.1,
        "h_fin_franja": 50.0, **{f"ret_{h}": 0.1 for h in cfg.HORIZONTES}}])
    eventos["ret_120"] = np.nan
    assert "120" not in set(cp.factores_pips(eventos, cfg)["horizonte"])


def test_el_costo_en_unidades_es_costo_sobre_factor_y_su_rango_esta_ordenado():
    resumidos = pd.DataFrame([{"vol": 0.07, "horizonte": "60", "idx_franja": "todas",
                               "eventos": 10, "q25": 5.0, "mediana": 8.0, "q75": 10.0}])
    costos = cp.costos_en_unidades(resumidos, [1.0, 2.0]).set_index("costo_pips")
    assert costos.loc[2.0, "unidades_mediana"] == pytest.approx(0.25)
    assert costos.loc[2.0, "unidades_rango"] == "[0.200, 0.400]"


# --- estimacion del tiempo --------------------------------------------------

def test_la_estimacion_reparte_los_mercados_entre_los_procesos():
    medidas = pd.DataFrame([{"anios": 4, "segundos": 60.0, "pico_gb": 0.0001}])
    estimacion = cp.estimar_corrida(medidas, repeticiones_potencia=30).iloc[0]
    assert estimacion["minutos_estimados"] == pytest.approx(
        30 * 60.0 / estimacion["procesos"] / 60)


# --- de punta a punta -------------------------------------------------------

def test_una_corrida_minima_entrega_filas_completas_y_un_efecto_que_se_ve():
    cambios = {"TAMANOS_EFECTO": [0, 0.2]}
    curva = cp.corrida_curva(semilla=5, anios=1, cambios=cambios, repeticiones=20)
    cfg = ayuda.cfg_prueba(**cambios)
    assert len(curva) == 2 * 2 * len(cfg.HORIZONTES)
    assert (curva.loc[curva["delta"] == 0, "frac_inyectados"] == 1.0).all()
    assert curva["confirmatoria"].sum() == 2 * len(cfg.FAMILIA_PRINCIPAL)

    realizado = cp.delta_realizado(curva, cfg)
    con_efecto = realizado[(realizado["delta"] == 0.2) & (realizado["horizonte"] == "30")]
    # En la direccion de cada hipotesis, el retorno se movio claramente hacia
    # donde se inyecto (no exactamente 0,2: la retroalimentacion diluye).
    assert (con_efecto["realizado"] > 0.1).all()
    assert (con_efecto["realizado"] < 0.3).all()
