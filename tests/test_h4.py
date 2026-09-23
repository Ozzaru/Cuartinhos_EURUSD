# -*- coding: utf-8 -*-
"""
Pruebas de H4 por inferencia de aleatorizacion.

Lo que se vigila:
  - los pseudo-eventos "con anuncio" salen SOLO de minutos dentro de una
    ventana de anuncio, y los "sin anuncio" SOLO de minutos fuera;
  - el estadistico de la nula se calcula con la misma funcion que el de los
    datos reales;
  - una prueba con pocos dias tratados queda marcada como descriptiva y no
    entra en la correccion;
  - el modo "franja" marca mas eventos tratados que el modo "ventana".
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import inferencia, moderadores, nula


def calendario_macro(inicio="2016-01-04", dias=200, cada=3):
    """Anuncios frecuentes, para que los conjuntos de sorteo no queden vacios."""
    momentos = pd.date_range(pd.Timestamp(inicio, tz="UTC") + pd.Timedelta(hours=13, minutes=30),
                             periods=dias // cada, freq=f"{cada}D")
    return pd.DataFrame({"t_utc": momentos, "tipo": ["ipc"] * len(momentos)})


def escenario(modo="ventana", dias=200, semilla=42, **cambios):
    cfg = ayuda.cfg_prueba(NOTICIA_MODO=modo, **cambios)
    idx = ayuda.indice("2016-01-04 00:00", dias * 24 * 60)
    velas = ayuda.camino_aleatorio(len(idx), semilla=semilla)
    noticias = calendario_macro(dias=dias)
    barras, cal, ev = motor.preparar(ayuda.datos(velas, idx=idx), cfg, noticias=noticias)
    return cfg, barras, cal, ev, noticias


# --- el sorteo respeta el lado del anuncio ----------------------------------

def test_los_pseudo_eventos_salen_del_lado_que_les_toca(monkeypatch):
    cfg, barras, cal, ev, noticias = escenario()
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    tratado_cand = candidatos["tratado"]
    assert 0 < tratado_cand.sum() < len(tratado_cand), "hacen falta minutos de los dos lados"

    registro = []
    original = nula._sortear

    def espia(rng, pools, claves, franja_evento, pos_cand, repeticiones, **kw):
        indices, usable = original(rng, pools, claves, franja_evento, pos_cand,
                                   repeticiones, **kw)
        registro.append((indices.copy(), usable.copy()))
        return indices, usable

    monkeypatch.setattr(nula, "_sortear", espia)
    nula.correr_h4(barras, cal, ev, cfg, semilla=1, repeticiones=20,
                   candidatos=candidatos)

    assert registro, "la nula de H4 no sorteo nada"
    # `correr_h4` llama a _sortear una vez por lado: primero tratados, despues
    # no tratados. Cada bloque de indices tiene que venir de su propio lado.
    for indices, usable in registro:
        if not usable.any():
            continue
        sorteados = indices[:, usable]
        marcas = np.unique(tratado_cand[sorteados])
        assert len(marcas) == 1, "un sorteo mezclo minutos con y sin anuncio"


def test_el_conjunto_de_tratados_solo_tiene_minutos_con_anuncio():
    cfg, barras, cal, ev, noticias = escenario()
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    disponible = candidatos["sirve"] & np.isfinite(candidatos["retornos"][60])

    con = nula._armar_pools(candidatos, disponible & (candidatos["tratado"] == 1.0))
    sin = nula._armar_pools(candidatos, disponible & (candidatos["tratado"] == 0.0))
    assert con and sin

    for pool in con.values():
        assert np.all(candidatos["tratado"][pool] == 1.0)
    for pool in sin.values():
        assert np.all(candidatos["tratado"][pool] == 0.0)


# --- un solo calculo del estadistico ----------------------------------------

def test_el_estadistico_es_el_mismo_codigo_en_los_datos_y_en_la_nula(monkeypatch):
    cfg, barras, cal, ev, noticias = escenario(MIN_DIAS_TRATADOS=1)
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)

    llamadas = {"n": 0}
    original = inferencia.diferencia_agrupada

    def contar(y, tratado, dia):
        llamadas["n"] += 1
        return original(y, tratado, dia)

    monkeypatch.setattr(nula.mod_inferencia, "diferencia_agrupada", contar)
    repeticiones = 15
    tabla = nula.correr_h4(barras, cal, ev, cfg, semilla=1, repeticiones=repeticiones,
                           candidatos=candidatos)

    corridas = tabla[tabla["n_con"] > 0]
    assert len(corridas) > 0
    # Por cada celda: una vez con los datos reales y una por repeticion.
    assert llamadas["n"] == len(corridas) * (1 + repeticiones)


def test_el_t_observado_coincide_con_el_calculo_directo():
    # Con un solo grupo de volatilidad los conjuntos de sorteo son grandes y
    # ningun evento se queda sin pareja. Asi el estadistico observado se puede
    # comparar contra el calculo directo sobre TODOS los eventos.
    cfg, barras, cal, ev, noticias = escenario(MIN_DIAS_TRATADOS=1, NULA_DECILES_VOL=1)
    tabla = nula.correr_h4(barras, cal, ev, cfg, semilla=1, repeticiones=10,
                           noticias=noticias)
    fila = tabla[(tabla["tipo"] == "reingreso") & (tabla["horizonte"] == 60)].iloc[0]
    assert fila["n_con"] > 0
    assert fila["n_descartados"] == 0, "no deberia faltar ningun evento por emparejar"

    sub = ev[(ev["tipo"] == "reingreso") & np.isfinite(ev["ret_60"])]
    sub = sub[np.isfinite(sub["noticia"])]
    dia = pd.factorize(pd.DatetimeIndex(sub["fecha_londres"]))[0]
    diferencia, error, t = inferencia.diferencia_agrupada(
        sub["ret_60"].to_numpy(float), sub["noticia"].to_numpy(float), dia)
    assert fila["diferencia"] == pytest.approx(diferencia, rel=1e-9)
    assert fila["t_observado"] == pytest.approx(t, rel=1e-9)
    assert fila["error"] == pytest.approx(error, rel=1e-9)


def test_el_observado_se_calcula_sobre_los_mismos_eventos_que_la_nula():
    # Si un evento no encuentra con quien emparejarse, queda fuera de las DOS
    # puntas de la comparacion. Si no, el estadistico observado y el nulo
    # estarian midiendo muestras distintas.
    cfg, barras, cal, ev, noticias = escenario(MIN_DIAS_TRATADOS=1)
    tabla = nula.correr_h4(barras, cal, ev, cfg, semilla=1, repeticiones=10,
                           noticias=noticias)
    for _, fila in tabla[tabla["n_con"] > 0].iterrows():
        usados = fila["n_con"] + fila["n_sin"]
        disponibles = int((
            (ev["tipo"] == fila["tipo"])
            & np.isfinite(ev[f"ret_{fila['horizonte']}"])
            & np.isfinite(ev["noticia"])).sum())
        assert usados + fila["n_descartados"] == disponibles
        assert fila["t_observado"] == pytest.approx(
            fila["diferencia"] / fila["error"], rel=1e-9)


def test_la_diferencia_agrupada_es_la_resta_de_promedios():
    y = np.array([1.0, 2.0, 3.0, 10.0, 12.0])
    tratado = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
    dia = np.array([0, 1, 2, 3, 4])
    diferencia, error, t = inferencia.diferencia_agrupada(y, tratado, dia)
    assert diferencia == pytest.approx(11.0 - 2.0)
    assert error > 0 and np.isfinite(t)
    # Sin variacion en el tratamiento no hay nada que comparar.
    assert np.isnan(inferencia.diferencia_agrupada(y, np.zeros(5), dia)[0])


# --- guardia de tamano ------------------------------------------------------

def test_con_pocos_dias_tratados_la_prueba_queda_descriptiva():
    cfg, barras, cal, ev, noticias = escenario()
    tabla = nula.correr_h4(barras, cal, ev, cfg, semilla=1, repeticiones=20,
                           noticias=noticias)

    exigente = inferencia.corregir_h4(tabla, ayuda.cfg_prueba(MIN_DIAS_TRATADOS=10_000))
    assert not exigente["entra_en_familia"].any()
    assert (exigente["estado"] == "descriptivo, muestra insuficiente").all()
    assert exigente["p_holm"].isna().all(), "una prueba descriptiva no se corrige"
    assert not exigente["rechaza"].any(), "una prueba descriptiva no concluye"

    permisiva = inferencia.corregir_h4(tabla, ayuda.cfg_prueba(MIN_DIAS_TRATADOS=1))
    assert permisiva["entra_en_familia"].any()
    entran = permisiva[permisiva["entra_en_familia"]]
    assert entran["p_holm"].notna().all()


def test_las_descriptivas_no_castigan_a_las_demas():
    # Holm reparte el castigo entre las pruebas que ENTRAN. Si una prueba queda
    # fuera por muestra insuficiente, no debe consumir lugar en la familia.
    base = pd.DataFrame({
        "tipo": ["sostenida"] * 4, "horizonte": [30, 60, 120, "fin_franja"],
        "dias_tratados": [100, 100, 2, 2],
        "p_estudentizado": [0.01, 0.02, 0.001, 0.001],
    })
    salida = inferencia.corregir_h4(base, ayuda.cfg_prueba(MIN_DIAS_TRATADOS=30))
    assert list(salida["entra_en_familia"]) == [True, True, False, False]
    # Dos pruebas en la familia: 0.01 * 2 = 0.02 y 0.02 * 1 = 0.02.
    assert salida["p_holm"].iloc[0] == pytest.approx(0.02)
    assert salida["p_holm"].iloc[1] == pytest.approx(0.02)
    assert salida["p_holm"].iloc[2:].isna().all()


# --- las dos definiciones de noticia ----------------------------------------

def test_el_modo_franja_marca_mas_eventos_que_el_modo_ventana():
    _, _, _, ev_ventana, _ = escenario(modo="ventana")
    _, _, _, ev_franja, _ = escenario(modo="franja")
    assert len(ev_ventana) == len(ev_franja), "los eventos son los mismos"
    tratados_ventana = ev_ventana["noticia"].sum()
    tratados_franja = ev_franja["noticia"].sum()
    assert tratados_franja > tratados_ventana
    # Todo evento tratado por ventana lo esta tambien por franja: si el anuncio
    # ocurrio en los minutos previos, esta dentro de la misma franja... salvo
    # que el anuncio caiga en la franja anterior. Por eso se compara el total.
    assert tratados_ventana > 0


def test_un_modo_desconocido_revienta():
    cfg, barras, cal, ev, noticias = escenario()
    malo = ayuda.cfg_prueba(NOTICIA_MODO="inventado")
    with pytest.raises(ValueError):
        moderadores.marcar_noticia(ev["t_evento_ns"].to_numpy(),
                                   ev["pos_franja"].to_numpy(), cal, noticias, malo)


def test_noticia_sale_de_la_familia_de_moderadores_pero_sigue_de_control():
    cfg = ayuda.cfg_prueba()
    assert "noticia" in cfg.MODERADORES, "sigue como regresor de control"
    assert "noticia" not in cfg.MODERADORES_PROBADOS
    probados = {coef for _, _, coef, _ in cfg.FAMILIA_MODERADORES}
    assert "noticia" not in probados
    assert len(cfg.FAMILIA_MODERADORES) == 24
    assert len(cfg.FAMILIA_H4) == 8
    assert {cola for _, _, _, cola in cfg.FAMILIA_H4} == {"mayor"}


def test_la_regresion_sigue_estimando_noticia_aunque_no_la_pruebe():
    cfg, _, _, ev, _ = escenario()
    celdas, _ = inferencia.construir_celdas(ev, cfg)
    alguna = next(c for (t, h, m), c in celdas.items() if m == "moderadores")
    assert "noticia" in alguna.nombres, "noticia tiene que seguir controlando la regresion"
