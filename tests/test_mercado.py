# -*- coding: utf-8 -*-
"""
Pruebas del mercado simulado.

No se comprueba que "parezca" EUR/USD, que no es el objetivo. Se comprueba que
tenga exactamente los ingredientes declarados y ninguno mas: semana de mercado,
perfil horario, volatilidad calibrada, spread y anuncios.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import franjas
from simulacion import mercado


@pytest.fixture(scope="module")
def mercado_corto():
    cfg = ayuda.cfg_prueba()
    datos, noticias = mercado.generar(1, semilla=7, cfg=cfg)
    return cfg, datos, noticias


# --- semana de mercado ------------------------------------------------------

def test_no_hay_minutos_de_fin_de_semana(mercado_corto):
    cfg, datos, _ = mercado_corto
    ny = datos.index.tz_convert(cfg.ZONA_MERCADO)
    dia, hora = ny.dayofweek, ny.hour
    assert not ((dia == 5).any()), "no puede haber sabados"
    assert not ((dia == 4) & (hora >= 17)).any(), "el viernes cierra a las 17:00 de NY"
    assert not ((dia == 6) & (hora < 17)).any(), "el domingo abre a las 17:00 de NY"
    assert ((dia == 6) & (hora >= 17)).any(), "el domingo por la tarde si opera"


def test_el_motor_ve_los_cierres_de_fin_de_semana(mercado_corto):
    cfg, datos, _ = mercado_corto
    barras = franjas.Barras.desde(datos, cfg)
    # Un ano tiene unas 52 semanas, o sea unos 52 cierres de fin de semana.
    assert 48 <= barras.sesion.max() <= 56, f"sesiones detectadas: {barras.sesion.max()}"


def test_los_minutos_van_seguidos_dentro_de_la_semana(mercado_corto):
    _, datos, _ = mercado_corto
    saltos = np.diff(datos.index.view("int64")) // 60_000_000_000
    # Solo dos clases de salto: un minuto, o el fin de semana entero.
    assert set(np.unique(saltos)) <= {1} | set(np.unique(saltos[saltos > 1]))
    assert (saltos == 1).mean() > 0.99


# --- volatilidad ------------------------------------------------------------

def test_la_volatilidad_anual_queda_donde_se_pidio(mercado_corto):
    cfg, datos, _ = mercado_corto
    medido = mercado.resumen(datos, cfg)["vol_anual"]
    assert medido == pytest.approx(cfg.VOL_ANUAL_SIMULACION, rel=0.10)


def test_la_volatilidad_sigue_el_perfil_horario(mercado_corto):
    cfg, datos, _ = mercado_corto
    mid = (datos["bid_close"] + datos["ask_close"]) / 2.0
    ret = pd.Series(np.diff(np.log(mid.to_numpy())), index=datos.index[1:])
    por_hora = ret.groupby(datos.index[1:].tz_convert(cfg.ZONA).hour).std()
    medido = (por_hora / por_hora.mean()).reindex(range(24)).to_numpy()
    esperado = np.asarray(cfg.PERFIL_HORARIO_VOL) / np.mean(cfg.PERFIL_HORARIO_VOL)
    assert np.corrcoef(medido, esperado)[0, 1] > 0.95
    assert np.max(np.abs(medido - esperado)) < 0.25


def test_el_regimen_diario_hace_que_haya_dias_tranquilos_y_dias_movidos(mercado_corto):
    cfg, datos, _ = mercado_corto
    mid = (datos["bid_close"] + datos["ask_close"]) / 2.0
    ret = pd.Series(np.diff(np.log(mid.to_numpy())), index=datos.index[1:])
    por_dia = ret.groupby(datos.index[1:].tz_convert(cfg.ZONA).normalize()).std()
    # Sin regimen lento, la dispersion entre dias seria mucho menor.
    assert por_dia.max() / por_dia.min() > 2.0
    # Y los dias movidos vienen en rachas: la correlacion con el dia anterior.
    assert np.log(por_dia).autocorr(lag=1) > 0.3


# --- spread -----------------------------------------------------------------

def test_el_spread_se_triplica_de_noche(mercado_corto):
    cfg, datos, _ = mercado_corto
    ancho = (datos["ask_close"] - datos["bid_close"]) / cfg.PIP
    hora = datos.index.hour
    h0, h1 = cfg.SPREAD_HORAS_NOCTURNAS
    de_noche = (hora >= h0) & (hora < h1)
    assert ancho[de_noche].mean() == pytest.approx(
        cfg.SPREAD_BASE_PIPS * cfg.SPREAD_FACTOR_NOCTURNO, rel=1e-9)
    assert ancho[~de_noche].mean() == pytest.approx(cfg.SPREAD_BASE_PIPS, rel=1e-9)
    assert (datos["ask_close"] > datos["bid_close"]).all()


def test_el_precio_medio_se_recupera_exacto(mercado_corto):
    _, datos, _ = mercado_corto
    con_medios = franjas.agregar_medios(datos)
    assert (con_medios["mid_high"] >= con_medios["mid_low"]).all()
    assert (con_medios["mid_high"] >= con_medios["mid_open"]).all()
    assert (con_medios["mid_high"] >= con_medios["mid_close"]).all()
    assert (con_medios["mid_low"] <= con_medios["mid_open"]).all()


# --- calendario de anuncios -------------------------------------------------

def test_el_calendario_de_anuncios_tiene_los_horarios_declarados(mercado_corto):
    _, _, noticias = mercado_corto
    assert set(noticias["tipo"]) == {"empleo", "ipc", "fomc"}
    cuentas = noticias["tipo"].value_counts()
    assert cuentas["empleo"] == 12 and cuentas["ipc"] == 12
    assert cuentas["fomc"] == 8, "ocho reuniones al ano"

    empleo = noticias[noticias["tipo"] == "empleo"]["t_utc"]
    assert (empleo.dt.dayofweek == 4).all(), "empleo es viernes"
    assert (empleo.dt.day <= 7).all(), "primer viernes del mes"
    assert ((empleo.dt.hour == 13) & (empleo.dt.minute == 30)).all()

    # El IPC sale el dia 12, salvo que caiga en fin de semana: ahi se corre al
    # siguiente dia con mercado abierto, como en la realidad.
    ipc = noticias[noticias["tipo"] == "ipc"]["t_utc"]
    assert (ipc.dt.day >= 12).all() and (ipc.dt.day <= 15).all()
    assert (ipc.dt.dayofweek < 5).all(), "ningun IPC queda en fin de semana"
    assert (ipc.dt.day == 12).sum() >= 6, "la mayoria si cae el dia 12"

    fomc = noticias[noticias["tipo"] == "fomc"]["t_utc"]
    assert (fomc.dt.dayofweek == 2).all(), "fomc es miercoles"
    assert (fomc.dt.hour == 19).all()


def test_todos_los_anuncios_caen_en_minutos_con_mercado_abierto(mercado_corto):
    # Antes se perdian los anuncios de fin de semana, que eran alrededor de un
    # 15% de la muestra tratada de H4.
    _, datos, noticias = mercado_corto
    assert noticias["t_utc"].isin(datos.index).all()


def test_los_anuncios_suben_la_volatilidad_pero_no_empujan_el_precio(mercado_corto):
    cfg, datos, noticias = mercado_corto
    mid = (datos["bid_close"] + datos["ask_close"]) / 2.0
    ret = pd.Series(np.diff(np.log(mid.to_numpy())), index=datos.index[1:])

    dentro = np.zeros(len(ret), dtype=bool)
    for t in noticias["t_utc"]:
        dentro |= (ret.index >= t) & (ret.index < t + pd.Timedelta(
            minutes=cfg.NOTICIA_DURACION_MIN))
    assert dentro.sum() > 100, "hacen falta minutos de anuncio para medir"

    # Se mueve mas...
    assert ret[dentro].std() > 2.0 * ret[~dentro].std()
    # ...pero sin direccion: el promedio no se distingue de cero.
    t_stat = ret[dentro].mean() / (ret[dentro].std() / np.sqrt(dentro.sum()))
    assert abs(t_stat) < 3.0, f"los anuncios estan empujando el precio (t = {t_stat:.2f})"


# --- reproducibilidad -------------------------------------------------------

def test_la_misma_semilla_da_el_mismo_mercado():
    cfg = ayuda.cfg_prueba()
    a, _ = mercado.generar(1, semilla=3, cfg=cfg)
    b, _ = mercado.generar(1, semilla=3, cfg=cfg)
    c, _ = mercado.generar(1, semilla=4, cfg=cfg)
    pd.testing.assert_frame_equal(a, b)
    assert not np.allclose(a["bid_close"].to_numpy(), c["bid_close"].to_numpy())


def test_el_mercado_simulado_pasa_por_el_motor_completo(mercado_corto):
    cfg, datos, noticias = mercado_corto
    barras, cal, ev = motor.preparar(datos, cfg, noticias=noticias)
    assert len(ev) > 100
    assert set(ev["tipo"]) == {"ruptura", "sostenida", "reingreso"}
    assert ev["sigma_ref"].notna().all()
    assert ev["noticia"].isin([0.0, 1.0]).all()
    # Las franjas de sabado no generan nada.
    assert not (ev["dia_semana"] == 5).any()
