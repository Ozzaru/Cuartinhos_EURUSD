# -*- coding: utf-8 -*-
"""
Pruebas de los moderadores de H3 y H4.

Todos se calculan con informacion anterior al evento. Los tests fijan a mano el
extremo roto y la fecha, y comprueban el valor exacto.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
from motor import franjas, moderadores, tiempo


def hora(momento):
    return pd.Timestamp(momento, tz="UTC")


def contexto(cfg, velas=None, idx=None, dias=3, inicio="2020-06-15 00:00"):
    if idx is None:
        idx = ayuda.indice(inicio, dias * 24 * 60)
    if velas is None:
        velas = ayuda.plano(len(idx), 1.10000)
    datos = ayuda.datos(velas, idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    return barras, franjas.calendario(barras, cfg)


def evento(cal, momento, extremo, direccion=1):
    t = tiempo.a_ns(hora(momento))
    pos = int(np.searchsorted(cal["inicio_ns"].to_numpy(), t - tiempo.NS_MIN, side="right") - 1)
    return pd.DataFrame([{
        "id_franja": "prueba", "fecha_londres": cal["fecha_londres"].iloc[pos],
        "idx_franja": int(cal["idx_franja"].iloc[pos]), "tipo": "ruptura",
        "direccion": direccion, "t_evento_utc": hora(momento),
        "t_ruptura_utc": hora(momento), "extremo_roto": extremo,
        "precio_evento": extremo, "dia_semana": int(cal["dia_semana"].iloc[pos]),
        "pos_franja": pos, "t_evento_ns": t, "t_ruptura_ns": t, "sigma_ref": 1e-4,
    }])


# --- numeros redondos -------------------------------------------------------

@pytest.mark.parametrize("extremo, dist_esperada, cerca", [
    (1.10000, 0.0, True),      # justo en un numero redondo
    (1.10030, 3.0, True),      # a 3 pips: dentro del radio de 5
    (1.10500, 0.0, True),      # los "50" tambien son redondos con paso 0.0050
    (1.10250, 25.0, False),    # el punto mas lejano entre dos redondos
    (1.09960, 4.0, True),      # se acerca a 1.10000 desde abajo
    (1.09940, 6.0, False),     # a 6 pips ya queda fuera del radio
])
def test_distancia_al_numero_redondo(extremo, dist_esperada, cerca):
    cfg = ayuda.cfg_prueba(PASO_REDONDO=0.0050, RADIO_REDONDO_PIPS=5)
    barras, cal = contexto(cfg)
    salida = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 06:31", extremo), cfg)
    assert salida["dist_redondo_pips"].iloc[0] == pytest.approx(dist_esperada, abs=1e-6)
    assert salida["cerca_redondo"].iloc[0] == (1.0 if cerca else 0.0)


# --- extremos del dia anterior ---------------------------------------------

def test_cerca_del_extremo_del_dia_anterior():
    cfg = ayuda.cfg_prueba(RADIO_EXTREMO_PREVIO_PIPS=3)
    idx = ayuda.indice("2020-06-15 00:00", 3 * 24 * 60)
    velas = ayuda.plano(len(idx), 1.10000)
    # El maximo del lunes 15 queda en 1.10200 y el minimo en 1.09800.
    ayuda.fijar(velas, idx, "2020-06-15 10:00", alto=1.10200)
    ayuda.fijar(velas, idx, "2020-06-15 11:00", bajo=1.09800)
    barras, cal = contexto(cfg, velas=velas, idx=idx)

    # Ruptura alcista del martes 16 con el extremo a 2 pips del maximo del lunes.
    cerca = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 06:31", 1.10180), cfg)
    assert cerca["cerca_extremo_previo"].iloc[0] == 1.0

    lejos = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 06:31", 1.10100), cfg)
    assert lejos["cerca_extremo_previo"].iloc[0] == 0.0

    # Una ruptura BAJISTA se compara contra el minimo del dia anterior, no
    # contra el maximo.
    bajista = moderadores.agregar(
        barras, cal, evento(cal, "2020-06-16 06:31", 1.09820, direccion=-1), cfg)
    assert bajista["cerca_extremo_previo"].iloc[0] == 1.0


def test_sin_dia_anterior_utilizable_el_moderador_queda_en_nan():
    cfg = ayuda.cfg_prueba(DIA_PREVIO_MIN_COBERTURA=0.50)
    # Los datos empiezan el mismo dia del evento: no hay dia anterior.
    barras, cal = contexto(cfg, inicio="2020-06-16 00:00", dias=2)
    salida = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 06:31", 1.10100), cfg)
    assert np.isnan(salida["cerca_extremo_previo"].iloc[0])


def test_el_lunes_se_compara_contra_el_viernes_y_no_contra_el_domingo():
    # El domingo solo trae un par de horas de mercado: sus extremos no son
    # comparables con los de un dia completo. En vez de perder el moderador, se
    # retrocede al ultimo dia con mercado suficiente, que es el viernes.
    cfg = ayuda.cfg_prueba(DIA_PREVIO_MIN_COBERTURA=0.50, RADIO_EXTREMO_PREVIO_PIPS=3)
    idx = ayuda.indice("2020-06-19 00:00", 4 * 24 * 60)      # viernes a lunes
    cerrado = (idx >= hora("2020-06-19 21:00")) & (idx < hora("2020-06-21 21:00"))
    idx = idx[~cerrado]
    velas = ayuda.plano(len(idx), 1.10000)
    # Maximo y minimo del VIERNES.
    velas[int(idx.get_loc(hora("2020-06-19 10:00"))), 1] = 1.10300
    velas[int(idx.get_loc(hora("2020-06-19 11:00"))), 2] = 1.09700
    # El domingo se mueve a otros niveles, que NO deben usarse.
    velas[int(idx.get_loc(hora("2020-06-21 22:00"))), 1] = 1.10900
    velas[int(idx.get_loc(hora("2020-06-21 22:30"))), 2] = 1.09100
    barras, cal = contexto(cfg, velas=velas, idx=idx)

    # Ruptura alcista del lunes a 2 pips del maximo del VIERNES.
    cerca = moderadores.agregar(barras, cal, evento(cal, "2020-06-22 01:01", 1.10280), cfg)
    assert cerca["cerca_extremo_previo"].iloc[0] == 1.0

    # A 2 pips del maximo del DOMINGO, que es el que no se debe mirar.
    domingo = moderadores.agregar(barras, cal, evento(cal, "2020-06-22 01:01", 1.10880), cfg)
    assert domingo["cerca_extremo_previo"].iloc[0] == 0.0, "el domingo no sirve de referencia"

    # Y lo mismo por el lado bajista.
    bajista = moderadores.agregar(
        barras, cal, evento(cal, "2020-06-22 01:01", 1.09720, direccion=-1), cfg)
    assert bajista["cerca_extremo_previo"].iloc[0] == 1.0


# --- compresion -------------------------------------------------------------

def test_ratio_de_compresion_y_su_corte():
    cfg = ayuda.cfg_prueba(DIAS_COMPRESION=20, DIAS_COMPRESION_MIN=3, CORTE_COMPRESION=0.75)
    idx = ayuda.indice("2020-06-01 00:00", 10 * 24 * 60)
    velas = ayuda.plano(len(idx), 1.10000)
    dia = (idx.normalize() - idx.normalize()[0]).days.to_numpy()
    # La franja [6,12) de Londres (05:00 a 11:00 UTC en verano) tiene 20 pips de
    # rango todos los dias, salvo el ultimo, que tiene 10: la mitad.
    # Se elige esa franja porque cae entera dentro del mismo dia UTC, asi el
    # escenario se puede leer sin pensar en el desfase con Londres.
    en_franja = (idx.hour >= 5) & (idx.hour < 11)
    ancho = np.where(dia < 9, 1.10200, 1.10100)
    velas[en_franja, 1] = ancho[en_franja]
    barras, cal = contexto(cfg, velas=velas, idx=idx)

    # El evento vive en la franja [12,18) del 10-jun y su referencia es la
    # franja [6,12) de ese mismo dia, la que quedo comprimida.
    salida = moderadores.agregar(barras, cal, evento(cal, "2020-06-10 11:31", 1.10100), cfg)
    assert salida["ratio_compresion"].iloc[0] == pytest.approx(0.5, rel=1e-9)
    assert salida["comprimida"].iloc[0] == 1.0

    # Un dia normal, con el rango igual a la mediana, no esta comprimido.
    normal = moderadores.agregar(barras, cal, evento(cal, "2020-06-09 11:31", 1.10100), cfg)
    assert normal["ratio_compresion"].iloc[0] == pytest.approx(1.0, rel=1e-9)
    assert normal["comprimida"].iloc[0] == 0.0


# --- noticias ---------------------------------------------------------------

def test_noticia_dentro_de_la_ventana_previa():
    cfg = ayuda.cfg_prueba(VENTANA_NOTICIAS_MIN=60)
    barras, cal = contexto(cfg)
    calendario_macro = pd.DataFrame({
        "t_utc": [hora("2020-06-16 06:00"), hora("2020-06-16 12:30")],
        "tipo": ["empleo", "ipc"],
    })

    # 31 minutos despues del anuncio: cuenta.
    dentro = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 06:31", 1.10100),
                                 cfg, noticias=calendario_macro)
    assert dentro["noticia"].iloc[0] == 1.0

    # 61 minutos despues: ya quedo fuera de la ventana.
    fuera = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 07:01", 1.10100),
                                cfg, noticias=calendario_macro)
    assert fuera["noticia"].iloc[0] == 0.0

    # Un anuncio POSTERIOR al evento no cuenta: seria mirar el futuro.
    antes = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 12:00", 1.10100),
                                cfg, noticias=calendario_macro)
    assert antes["noticia"].iloc[0] == 0.0


def test_sin_calendario_de_noticias_la_columna_es_cero():
    cfg = ayuda.cfg_prueba()
    barras, cal = contexto(cfg)
    salida = moderadores.agregar(barras, cal, evento(cal, "2020-06-16 06:31", 1.10100), cfg)
    assert salida["noticia"].iloc[0] == 0.0
    assert set(moderadores.NOMBRES) <= set(salida.columns)
