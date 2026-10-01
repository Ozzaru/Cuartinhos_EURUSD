# -*- coding: utf-8 -*-
"""
Calendario de anuncios (pre-registro 4.8): lectores de las fuentes y hora UTC.
Con trozos de HTML escritos a mano; ningun test sale a la red.
"""
import datetime as dt
import os

import pandas as pd
import pytest

import ayuda
from fuentes import calendario

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOMC_ANTIGUA = """
<div class="panel-heading"><h5>January 28-29 Meeting - 2003</h5></div>
<p><a href="/boarddocs/press/monetary/2003/20030129/default.htm">Statement</a></p>
<p><a href="/fomc/minutes/20030129.htm">Minutes</a></p>
<div class="panel-heading"><h5>March 25 Conference Call - 2003</h5></div>
<p><a href="/fomc/minutes/20030325.htm">Minutes</a></p>
<div class="panel-heading"><h5>September 15 Meeting - 2003</h5></div>
<p><a href="/monetarypolicy/files/x.pdf">Agenda</a></p>
"""
FOMC_NUEVA = """
<h5 class="panel-heading panel-heading--shaded">March 2 (unscheduled) Meeting - 2020</h5>
<p><a href="/newsevents/pressreleases/monetary20200303a.htm">Statement</a></p>
<h5 class="panel-heading panel-heading--shaded">March 17-18 (cancelled) Meeting - 2020</h5>
<h5 class="panel-heading panel-heading--shaded">April 28-29 Meeting - 2020</h5>
<p><a href="/newsevents/pressreleases/monetary20200429a.htm">Statement</a></p>
<p><a href="/newsevents/pressreleases/monetary20200429b.htm">Implementation Note</a></p>
"""


def test_reuniones_fomc_separa_las_programadas():
    antigua = calendario.reuniones_fomc(FOMC_ANTIGUA)
    assert [(r["programada"], r["comunicado"] is not None) for r in antigua] == [
        (True, True), (False, False), (True, False)]
    assert antigua[0]["minutas"] == "/fomc/minutes/20030129.htm"
    nueva = calendario.reuniones_fomc(FOMC_NUEVA)
    assert [r["programada"] for r in nueva] == [False, False, True]
    assert nueva[2]["comunicado"] == "/newsevents/pressreleases/monetary20200429a.htm"


def test_hora_y_fecha_de_los_comunicados_de_la_fed():
    nuevo = "<p>Release Date: January 27, 2016</p><p>For release at 2:00 p.m. EST</p>"
    assert calendario.hora_del_comunicado(nuevo) == (14, 0)
    assert calendario.fecha_del_comunicado(nuevo) == dt.date(2016, 1, 27)
    assert calendario.hora_del_comunicado("<p>For release at 12:30 p.m. EDT</p>") == (12, 30)
    antiguo = "<p>Release Date: May 6, 2003</p><p>For immediate release</p>"
    assert calendario.hora_del_comunicado(antiguo) is None
    minutas = "<p>The vote encompassed approval of the statement to be released at 2:15 p.m.:</p>"
    assert calendario.hora_de_las_minutas(minutas) == (14, 15)
    assert calendario.fecha_de_url_fomc("/boarddocs/press/monetary/2003/20030506/default.htm") == dt.date(2003, 5, 6)
    assert calendario.fecha_de_url_fomc("/newsevents/pressreleases/monetary20160127a.htm") == dt.date(2016, 1, 27)
    assert calendario.fecha_de_url_fomc("/boarddocs/press/monetary/2005/20050920/") == dt.date(2005, 9, 20)


def test_comunicados_del_bls_salen_de_la_pagina_de_archivo():
    html = ('<a href="/news.release/archives/empsit_10222013.htm">September 2013</a>'
            '<a href="/news.release/archives/empsit_10222013.pdf">PDF</a>'
            '<a href="/news.release/archives/empsit_2027.htm">futuro</a>'
            '<a href="/news.release/archives/empsit_01102003.htm">December 2002</a>')
    lista = calendario.comunicados_bls(html, "empsit")
    assert [f for f, _ in lista] == [dt.date(2003, 1, 10), dt.date(2013, 10, 22)]
    assert calendario.verificar_hora_bls("embargoed until 8:30 a.m. (ET) Friday")
    assert not calendario.verificar_hora_bls("embargoed until 10:00 a.m. (ET)")


def test_decisiones_del_bce():
    html = ('<dt isoDate="2008-10-08"><div class="date">8 October 2008</div></dt><dd>'
            '<div class="title"><a href="/press/pr/date/2008/html/pr081008.en.html" >Monetary policy decisions</a></div></dd>'
            '<dt isoDate="2008-10-02"><div class="date">2 October 2008</div></dt><dd>'
            '<div class="title"><a href="/press/pr/date/2008/html/pr081002.en.html" >Monetary policy decisions</a></div></dd>')
    decisiones = calendario.decisiones_bce(html)
    assert [(f, f.weekday()) for f, _, _ in decisiones] == [(dt.date(2008, 10, 8), 2), (dt.date(2008, 10, 2), 3)]
    cfg = ayuda.cfg_prueba()
    assert calendario.hora_bce(dt.date(2016, 12, 8), cfg) == (13, 45)
    assert calendario.hora_bce(dt.date(2022, 7, 21), cfg) == (14, 15)


@pytest.mark.parametrize("fecha, hora, zona, utc", [
    (dt.date(2016, 1, 27), (14, 0), "America/New_York", "2016-01-27 19:00"),    # EST
    (dt.date(2016, 6, 15), (14, 0), "America/New_York", "2016-06-15 18:00"),    # EDT
    (dt.date(2016, 3, 11), (8, 30), "America/New_York", "2016-03-11 13:30"),    # antes del cambio (13-03)
    (dt.date(2016, 3, 18), (8, 30), "America/New_York", "2016-03-18 12:30"),    # EE. UU. ya en verano
    (dt.date(2016, 12, 8), (13, 45), "Europe/Berlin", "2016-12-08 12:45"),      # CET
    (dt.date(2016, 7, 21), (13, 45), "Europe/Berlin", "2016-07-21 11:45"),      # CEST
])
def test_conversion_a_utc(fecha, hora, zona, utc):
    assert calendario.a_utc(fecha, *hora, zona) == pd.Timestamp(utc, tz="UTC")


def test_el_contacto_del_bls_solo_sale_de_la_variable_de_entorno(monkeypatch):
    monkeypatch.delenv("CUARTINHOS_CONTACTO", raising=False)
    with pytest.raises(calendario.CalendarioError):
        calendario.agente(con_contacto=True)
    monkeypatch.setenv("CUARTINHOS_CONTACTO", "alguien@ejemplo.invalid")
    assert "alguien@ejemplo.invalid" in calendario.agente(con_contacto=True)
    assert "@" not in calendario.agente(con_contacto=False)
    # Ningun archivo del codigo trae una direccion de correo escrita.
    with open(os.path.join(RAIZ, "fuentes", "calendario.py"), encoding="utf-8") as f:
        assert "@" not in f.read()
