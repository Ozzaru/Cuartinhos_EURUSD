# -*- coding: utf-8 -*-
"""
Pruebas de las piezas del control positivo.

La corrida completa tarda y no cabe en la bateria de tests. Lo que si se prueba
son las cuentas que despues se leen en el reporte (potencia, efecto minimo
detectable, delta realizado, sesgo, tamano, costos, traduccion a pips) y lo que
hace valido al diseno D: sumar delta mueve lo observado exactamente delta, no
toca la nula ni los remuestreos de Romano-Wolf, y en delta = 0 reproduce el
pipeline normal. Del control B se prueba que el punto fijo es de verdad un
punto fijo.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from experimentos import control_positivo as cp
from motor import inferencia, nula
from simulacion import inyeccion, mercado


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


# --- efecto minimo con intervalo ------------------------------------------

def test_si_todos_los_mercados_son_iguales_el_intervalo_se_cierra_en_el_punto():
    deltas = [0, 0.05, 0.10, 0.20]
    # 10 mercados: rechazan desde 0,10 los 8 primeros y desde 0,05 los 2
    # ultimos. La curva promedio: 0, 0,2, 1, 1.
    filas = [[0, 0, 1, 1]] * 8 + [[0, 1, 1, 1]] * 2
    rechazos = pd.DataFrame(filas, columns=deltas)
    efecto, bajo, alto = cp.efecto_minimo_con_ic(rechazos, 0.80, 200, semilla=1)
    # Entre 0,05 (0,2) y 0,10 (1): 0,80 queda a 3/4 del tramo.
    assert efecto == pytest.approx(0.0875)
    assert bajo <= efecto <= alto

    # Todos iguales (0, 0, 1, 1): cruza en 0,05 + 0,8 * 0,05 = 0,09, en cada
    # remuestreo.
    iguales = pd.DataFrame([[0, 0, 1, 1]] * 10, columns=deltas)
    efecto, bajo, alto = cp.efecto_minimo_con_ic(iguales, 0.80, 200, semilla=1)
    assert efecto == pytest.approx(0.09)
    assert bajo == pytest.approx(0.09) and alto == pytest.approx(0.09)


def test_si_la_curva_no_llega_el_borde_alto_del_intervalo_es_infinito():
    rechazos = pd.DataFrame([[0, 0, 1]] * 3 + [[0, 0, 0]] * 7, columns=[0, 0.1, 0.2])
    efecto, _, alto = cp.efecto_minimo_con_ic(rechazos, 0.80, 200, semilla=1)
    assert np.isnan(efecto)
    assert np.isinf(alto)


# --- sesgo, tamano y costos -------------------------------------------------

def curva_d_falsa():
    """Dos mercados; la media se mueve exactamente delta y la nula no se mueve."""
    filas = []
    for mercado_k, piso in ((1, 0.004), (2, 0.008)):
        for delta in (0, 0.05, 0.1):
            for tipo, signo in (("sostenida", 1), ("reingreso", -1)):
                filas.append({
                    "mercado": mercado_k, "anios": 4, "delta": delta, "tipo": tipo,
                    "horizonte": "30", "confirmatoria": True,
                    "media_observada": signo * (piso + delta) + 0.001,
                    "media_nula": 0.001,
                    "p_bruto": 0.01 if mercado_k == 1 else 0.5,
                    "p_holm": 0.02 if mercado_k == 1 else 0.9})
    return pd.DataFrame(filas)


def test_el_sesgo_es_observado_menos_nulo_menos_delta_y_no_depende_de_delta():
    cfg = ayuda.cfg_prueba()
    sesgo = cp.sesgo_del_estimador(curva_d_falsa(), cfg).set_index("tipo")
    for tipo in ("sostenida", "reingreso"):
        assert sesgo.loc[tipo, "sesgo"] == pytest.approx(0.006)
        assert sesgo.loc[tipo, "variacion_max"] == pytest.approx(0.0, abs=1e-12)
        assert sesgo.loc[tipo, "mercados"] == 2
    # La media cruda no descuenta la nula (+0,001, que en el reingreso va en
    # contra de su direccion).
    assert sesgo.loc["sostenida", "sesgo_media_cruda"] == pytest.approx(0.007)
    assert sesgo.loc["reingreso", "sesgo_media_cruda"] == pytest.approx(0.005)


def test_la_tasa_en_delta_cero_cuenta_solo_delta_cero_y_por_duracion():
    cfg = ayuda.cfg_prueba(ALFA_PRINCIPAL=0.05)
    tabla = cp.tamano_en_cero(curva_d_falsa(), cfg, remuestreos=200, semilla=1).iloc[0]
    assert tabla["mercados"] == 2
    assert tabla["familia"] == pytest.approx(0.5)          # solo el mercado 1 rechaza
    assert tabla["por_prueba_bruto"] == pytest.approx(0.5)
    assert tabla["por_prueba_holm"] == pytest.approx(0.5)


def test_la_potencia_contra_un_costo_se_lee_en_delta_menos_c():
    celda = pd.DataFrame({"anios": 4, "tipo": "sostenida", "horizonte": "60",
                          "delta": [0, 0.05, 0.10, 0.20],
                          "potencia": [0.05, 0.25, 0.65, 1.0]})
    costos = pd.DataFrame([{"horizonte": "60", "costo_pips": 1.0, "unidades_mediana": 0.025}])
    tabla = cp.potencia_contra_costo(celda, "potencia", costos, [0.02, 0.10]).iloc[0]
    # 0,10 - 0,025 = 0,075: a mitad de camino entre 0,25 y 0,65.
    assert tabla[0.10] == pytest.approx(0.45)
    # 0,02 - 0,025 < 0: el efecto neto no es positivo, no hay potencia que leer.
    assert np.isnan(tabla[0.02])


# --- estimacion del tiempo --------------------------------------------------

def test_la_estimacion_reparte_los_mercados_de_cada_etapa_entre_los_procesos():
    medidas = pd.DataFrame([{"etapa": "D", "anios": 4, "segundos": 60.0, "pico_gb": 0.0001},
                            {"etapa": "B", "anios": 4, "segundos": 30.0, "pico_gb": 0.0001}])
    estimacion = cp.estimar_corrida(medidas, [("D", 4, 30), ("B", 4, 10)],
                                    {"B": 3.0}).set_index("etapa")
    assert estimacion.loc["D", "minutos_estimados"] == pytest.approx(
        30 * 60.0 / estimacion.loc["D", "procesos"] / 60)
    # B se escala por el factor (el piloto midio un escenario, se corren tres).
    assert estimacion.loc["B", "minutos_estimados"] == pytest.approx(
        10 * 90.0 / estimacion.loc["B", "procesos"] / 60)


def test_una_duracion_sin_medir_se_interpola_y_fuera_del_rango_no_se_extrapola():
    medidas = pd.DataFrame([{"etapa": "D", "anios": 4, "segundos": 8.0, "pico_gb": 0.5},
                            {"etapa": "D", "anios": 13, "segundos": 26.0, "pico_gb": 1.4}])
    fila = cp.estimar_corrida(medidas, [("D", 6, 100)]).iloc[0]
    assert fila["origen"] == "interpolado"
    assert fila["segundos_por_mercado"] == pytest.approx(12.0)      # 8 + 18 * 2/9
    assert fila["pico_gb"] == pytest.approx(0.7)
    with pytest.raises(ValueError):
        cp.estimar_corrida(medidas, [("D", 20, 10)])


def test_si_pasa_del_tope_se_recortan_primero_los_mercados_de_la_duracion_mas_larga():
    estimacion = pd.DataFrame([
        {"etapa": "D", "anios": 4, "segundos_por_mercado": 60.0, "procesos": 1,
         "mercados": 30, "minutos_estimados": 30.0},
        {"etapa": "D", "anios": 13, "segundos_por_mercado": 120.0, "procesos": 1,
         "mercados": 30, "minutos_estimados": 60.0}])
    igual, nota = cp.recortar_por_tiempo(estimacion, 100)
    assert nota is None and igual["mercados"].tolist() == [30, 30]
    recortada, nota = cp.recortar_por_tiempo(estimacion, 60)
    # Quedan 30 minutos para 13 anos: 15 mercados de 2 minutos.
    assert recortada["mercados"].tolist() == [30, 15]
    assert recortada["minutos_estimados"].sum() == pytest.approx(60.0)
    assert "13 anos" in nota


# --- regla de ALFA_PRINCIPAL -------------------------------------------------

def test_la_regla_del_alfa_cubre_los_casos_escritos():
    regla = cp.regla_alfa_principal
    # El IC con 0,05 contiene a 0,05: se queda 0,05.
    assert regla((0.06, 0.04, 0.08), (0.03, 0.02, 0.04), 0.05, 0.025)[0] == 0.05
    # Exceso demostrado con 0,05 y con 0,025 el borde inferior no pasa de 0,05.
    assert regla((0.08, 0.06, 0.10), (0.045, 0.03, 0.06), 0.05, 0.025)[0] == 0.025
    # Incluso con 0,025 el borde inferior pasa de 0,05: el control falla.
    decision, motivo = regla((0.12, 0.10, 0.14), (0.07, 0.06, 0.08), 0.05, 0.025)
    assert decision is None and "falla" in motivo
    # IC entero bajo 0,05 (caso no listado): el objetivo se cumple, se queda 0,05.
    decision, motivo = regla((0.03, 0.02, 0.04), (0.01, 0.005, 0.02), 0.05, 0.025)
    assert decision == 0.05 and "no listado" in motivo


def test_la_regla_del_alfa_mira_solo_delta_cero_de_la_duracion_que_confirma():
    cfg = ayuda.cfg_prueba(ANIOS_REGLA_ALFA=4, REMUESTREOS_IC_MERCADOS=200)
    filas = []
    for anios, p in ((4, 0.5), (13, 0.001)):
        for mercado_k in range(20):
            for delta in (0, 0.1):
                filas.append({"anios": anios, "mercado": mercado_k, "delta": delta,
                              "confirmatoria": True,
                              "p_bruto": 0.001 if delta > 0 else p})
    regla = cp.aplicar_regla_alfa(pd.DataFrame(filas), cfg)
    # En 4 anos y delta = 0 nadie rechaza: los p de 13 anos y de delta > 0 no entran.
    assert regla["ic"][cfg.ALFA][0] == 0.0
    assert regla["decision"] == cfg.ALFA and regla["mercados"] == 20


# --- diseno D sobre un mercado simulado ------------------------------------

SEMILLA_D = 5
REPETICIONES_D = 30


@pytest.fixture(scope="module")
def mercado_d():
    """Un ano de mercado sin patron, con la parte cara del diseno D ya hecha."""
    cfg = ayuda.cfg_prueba()
    datos, noticias = mercado.generar(1, SEMILLA_D, cfg)
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    materiales = nula.sortear_nula(barras, cal, eventos, cfg, SEMILLA_D,
                                   repeticiones=REPETICIONES_D, candidatos=candidatos)
    return cfg, barras, cal, eventos, candidatos, materiales


def test_sumar_delta_mueve_la_media_observada_exactamente_delta_y_no_toca_la_nula(mercado_d):
    cfg, _, _, _, _, materiales = mercado_d
    signo = inyeccion.signos(cfg)
    base, dist_base = nula.resumir_nula(materiales, cfg)
    t_antes = [m["t_validas"].copy() for m in materiales if not m["vacio"]]
    for delta in (0.01, 0.1):
        movida, dist = nula.resumir_nula(materiales, cfg,
                                         {t: s * delta for t, s in signo.items()})
        for tipo in ("sostenida", "reingreso", "ruptura"):
            esperado = signo.get(tipo, 0.0) * delta
            a = base[base["tipo"] == tipo]
            b = movida[movida["tipo"] == tipo]
            assert np.allclose(b["media_observada"].to_numpy() - a["media_observada"].to_numpy(),
                               esperado, rtol=0, atol=1e-12)
            # La nula queda identica, bit a bit.
            for columna in ("media_nula", "sd_nula", "n_eventos", "repeticiones"):
                assert b[columna].tolist() == a[columna].tolist()
        assert dist.keys() == dist_base.keys()
        assert all(np.array_equal(dist[k], dist_base[k]) for k in dist)
    # Resumir no modifica lo sorteado.
    despues = [m["t_validas"] for m in materiales if not m["vacio"]]
    assert all(np.array_equal(a, b) for a, b in zip(t_antes, despues))


def test_sin_desplazamiento_resumir_es_lo_mismo_que_correr(mercado_d):
    cfg, barras, cal, eventos, candidatos, materiales = mercado_d
    tabla, _ = nula.correr(barras, cal, eventos, cfg, SEMILLA_D,
                           repeticiones=REPETICIONES_D, candidatos=candidatos)
    assert tabla.equals(nula.resumir_nula(materiales, cfg)[0])


def test_romano_wolf_con_la_celda_desplazada_es_mover_solo_el_t_observado(mercado_d):
    cfg, _, _, eventos, _, _ = mercado_d
    signo = inyeccion.signos(cfg)
    familia = cfg.FAMILIA_PRINCIPAL
    celdas, dias = inferencia.construir_celdas(eventos, cfg)
    beta, error, w = inferencia.romano_wolf_remuestreos(celdas, familia, dias, 50, 3)

    delta = 0.1
    movidos = eventos.copy()
    s = movidos["tipo"].map(signo).fillna(0.0).to_numpy()
    for h in cfg.HORIZONTES:
        movidos[f"ret_{h}"] = movidos[f"ret_{h}"] + s * delta
    celdas_m, dias_m = inferencia.construir_celdas(movidos, cfg)
    directo = inferencia.romano_wolf(celdas_m, familia, dias_m, 50, 3)

    s_familia = np.array([signo[t] for t, _, _, _ in familia])
    atajo = inferencia.romano_wolf_stepdown(inferencia.t_de(beta + s_familia * delta, error), w)
    np.testing.assert_array_equal(directo, atajo)
    _, _, w_m = inferencia.romano_wolf_remuestreos(celdas_m, familia, dias_m, 50, 3)
    np.testing.assert_allclose(w_m, w, rtol=0, atol=1e-9)


@pytest.fixture(scope="module")
def curva_d():
    cambios = {"TAMANOS_EFECTO": [0, 0.2], "GRILLA_POTENCIA": [0, 0.05, 0.1]}
    curva = cp.corrida_curva(semilla=SEMILLA_D, anios=1, cambios=cambios,
                             repeticiones=REPETICIONES_D)
    return ayuda.cfg_prueba(**cambios), curva


def test_la_curva_d_tiene_una_fila_por_delta_tipo_y_horizonte(curva_d):
    cfg, curva = curva_d
    assert sorted(curva["delta"].unique()) == [0, 0.05, 0.1, 0.2]
    assert len(curva) == 4 * 2 * len(cfg.HORIZONTES)
    assert set(curva.loc[curva["en_tamanos"], "delta"]) == {0, 0.2}
    assert curva["confirmatoria"].sum() == 4 * len(cfg.FAMILIA_PRINCIPAL)


def test_en_la_curva_d_el_delta_realizado_es_exactamente_el_nominal(curva_d):
    cfg, curva = curva_d
    realizado = cp.delta_realizado(curva, cfg)
    assert np.allclose(realizado["realizado"], realizado["delta"], rtol=0, atol=1e-12)


def test_en_delta_cero_la_curva_d_reproduce_el_pipeline_normal(curva_d, mercado_d):
    cfg, curva = curva_d
    _, barras, cal, eventos, candidatos, _ = mercado_d
    tabla_nula, _ = nula.correr(barras, cal, eventos, cfg, SEMILLA_D,
                                repeticiones=REPETICIONES_D, candidatos=candidatos)
    principal = inferencia.analizar(
        eventos, cfg, cfg.FAMILIA_PRINCIPAL, SEMILLA_D,
        p_brutos=inferencia.p_brutos_desde_nula(tabla_nula, cfg),
        con_romano_wolf=True, repeticiones_rw=REPETICIONES_D, alfa=cfg.ALFA_PRINCIPAL)
    principal = principal.assign(horizonte=principal["horizonte"].astype(str)) \
        .set_index(["tipo", "horizonte"])
    cero = curva[(curva["delta"] == 0) & curva["confirmatoria"]] \
        .set_index(["tipo", "horizonte"]).loc[principal.index]
    np.testing.assert_array_equal(cero["p_holm"], principal["p_holm"])
    np.testing.assert_array_equal(cero["p_romano_wolf"], principal["p_romano_wolf"])
    np.testing.assert_array_equal(cero["estimacion"], principal["estimacion"])


def test_en_la_curva_d_los_p_no_suben_cuando_delta_sube(curva_d):
    _, curva = curva_d
    confirmatorias = curva[curva["confirmatoria"]].sort_values("delta")
    for _, bloque in confirmatorias.groupby(["tipo", "horizonte"]):
        assert (np.diff(bloque["p_bruto"].to_numpy()) <= 0).all()
        assert (np.diff(bloque["p_holm"].to_numpy()) <= 1e-12).all()


# --- control B --------------------------------------------------------------

def test_la_inyeccion_autoconsistente_es_un_punto_fijo():
    cfg = ayuda.cfg_prueba()
    limpio, noticias = mercado.generar(1, 11, cfg)
    _, _, eventos_l = motor.preparar(limpio, cfg, noticias=noticias)
    _, _, eventos, iteraciones, convergio = cp.inyeccion_autoconsistente(
        limpio, noticias, eventos_l, 0.2, cfg)
    assert convergio and iteraciones >= 2
    # Inyectar con los eventos del punto fijo y volver a detectar da los mismos.
    _, _, otra_vez = motor.preparar(inyeccion.inyectar(limpio, eventos, 0.2, cfg), cfg,
                                    noticias=noticias)
    tipos = ["sostenida", "reingreso"]
    assert cp._firma(otra_vez, tipos).equals(cp._firma(eventos, tipos))


def test_el_control_b_mide_un_efecto_de_precio_que_llega_en_parte_a_las_celdas():
    cambios = {"DELTAS_CONTROL_B": [0.2]}
    control = cp.corrida_control_b(semilla=11, anios=1, cambios=cambios)
    cfg = ayuda.cfg_prueba(**cambios)
    assert len(control) == len(cfg.ESCENARIOS_CONTROL_B) * 2 * len(cfg.HORIZONTES)
    assert control["convergio"].all()
    ambos = control[control["escenario"] == "ambos"]
    treinta = ambos[ambos["horizonte"] == "30"].set_index("tipo")
    # Con los mismos eventos, el retorno se movio hacia donde se inyecto y del
    # orden del delta (cuanto exactamente es lo que mide el control B).
    assert (treinta["realizado_por_evento"] > 0.05).all()
    assert (treinta["realizado_por_evento"] < 0.25).all()
    # En los escenarios "solo", la celda no inyectada queda marcada y se mide.
    solo = control[control["escenario"] == "solo_sostenidas"].set_index("tipo")
    assert solo.loc["sostenida", "inyectado"].all()
    assert not solo.loc["reingreso", "inyectado"].any()
    assert solo.loc["reingreso", "realizado_por_evento"].notna().all()
    resumen = cp.resumen_control_b(control)
    assert np.allclose(resumen["razon_por_evento"], resumen["realizado_por_evento"] / 0.2)


def test_con_un_solo_tipo_inyectado_el_punto_fijo_mira_solo_ese_tipo():
    cfg = ayuda.cfg_prueba()
    limpio, noticias = mercado.generar(1, 11, cfg)
    _, _, eventos_l = motor.preparar(limpio, cfg, noticias=noticias)
    _, _, eventos, _, convergio = cp.inyeccion_autoconsistente(
        limpio, noticias, eventos_l, 0.2, cfg, tipos=["reingreso"])
    assert convergio
    solo = eventos[eventos["tipo"] == "reingreso"]
    _, _, otra_vez = motor.preparar(inyeccion.inyectar(limpio, solo, 0.2, cfg), cfg,
                                    noticias=noticias)
    assert cp._firma(otra_vez, ["reingreso"]).equals(cp._firma(eventos, ["reingreso"]))


def test_la_potencia_aproximada_de_b_es_la_de_d_en_el_delta_realizado():
    celda = pd.DataFrame({"anios": 4, "tipo": "sostenida", "horizonte": "60",
                          "delta": [0, 0.05, 0.10], "potencia": [0.05, 0.45, 0.95]})
    resumen = pd.DataFrame([
        {"escenario": "ambos", "delta": 0.1, "tipo": "sostenida", "horizonte": "60",
         "inyectado": True, "realizado_por_evento": 0.075},
        {"escenario": "solo_reingresos", "delta": 0.1, "tipo": "sostenida",
         "horizonte": "60", "inyectado": False, "realizado_por_evento": -0.01}])
    tabla = cp.potencia_aproximada_b(resumen, celda, "potencia", 4)
    assert tabla.loc[0, "potencia_aprox"] == pytest.approx(0.70)
    # Contagio en contra de la hipotesis: la curva de D no lo cubre.
    assert np.isnan(tabla.loc[1, "potencia_aprox"])
