# -*- coding: utf-8 -*-
"""
Pruebas de la deteccion de eventos, con series escritas minuto a minuto.

Escenario base, siempre el mismo para que los numeros se puedan seguir a mano:

  - tres dias de junio de 2020, o sea Londres = UTC + 1;
  - todo plano en 1.10000 salvo lo que cada test indique;
  - franja de REFERENCIA: 2020-06-16 idx 0, que en UTC va del 15-jun 23:00 al
    16-jun 05:00. Ahi se fijan H = 1.10100 y L = 1.09900;
  - franja EN CURSO: 2020-06-16 idx 1, que en UTC va de 05:00 a 11:00.

Con UMBRAL_PIPS = 1.0 hay que superar 1.10110 para romper hacia arriba y bajar
de 1.09890 para romper hacia abajo.

Los tests pasan sigma_ref a mano: estas series duran tres dias y sigma_ref de
verdad necesita DIAS_VOL_REF_MIN dias previos. El calculo real de sigma_ref
tiene sus propias pruebas en test_resultados.py.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
from motor import eventos, franjas, tiempo

PRECIO = 1.10000
H = 1.10100
L = 1.09900
FRANJA = "2020-06-16_1"


def escenario(cfg, cambios=(), quitar=None):
    """Arma el escenario base y aplica los cambios que pide el test."""
    idx = ayuda.indice("2020-06-15 00:00", 3 * 24 * 60)
    velas = ayuda.plano(len(idx), PRECIO)
    ayuda.fijar(velas, idx, "2020-06-16 01:00", alto=H)      # H de la referencia
    ayuda.fijar(velas, idx, "2020-06-16 02:00", bajo=L)      # L de la referencia
    for cambio in cambios:
        ayuda.fijar(velas, idx, **cambio)
    if quitar is not None:
        fuera = quitar(idx)
        idx, velas = idx[~fuera], velas[~fuera]
    datos = ayuda.datos(velas, idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    tabla = eventos.detectar(barras, cal, cfg, sigma=ayuda.sigma_fija(len(cal)))
    return barras, cal, tabla


def de_la_franja(tabla, franja=FRANJA):
    return tabla[tabla["id_franja"] == franja].set_index("tipo")


def hora(momento):
    return pd.Timestamp(momento, tz="UTC")


def afuera(desde, hasta, precio=1.10115):
    """
    Deja el precio FUERA del extremo entre dos minutos, ambos incluidos.

    Sin esto, las barras siguientes a la ruptura se quedan en 1.10000, o sea
    adentro, y el reingreso ocurre al minuto siguiente. Que el precio aguante
    afuera hay que escribirlo barra por barra.
    """
    return [dict(momento=t.strftime("%Y-%m-%d %H:%M"), apertura=precio,
                 alto=precio + 0.00005, bajo=precio - 0.00003, cierre=precio)
            for t in pd.date_range(hora(desde), hora(hasta), freq="min")]


# --- rupturas ---------------------------------------------------------------

def test_ruptura_alcista_en_el_minuto_conocido():
    cfg = ayuda.cfg_prueba()
    _, _, tabla = escenario(cfg, [
        # 1.10105 se queda a media pip: NO alcanza a romper.
        dict(momento="2020-06-16 06:10", alto=1.10105),
        # 1.10120 si supera H + 1 pip = 1.10110.
        dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115),
    ])
    r = de_la_franja(tabla).loc["ruptura"]
    assert r["t_evento_utc"] == hora("2020-06-16 06:31"), "el evento ocurre al CIERRE de la barra"
    assert r["direccion"] == 1
    assert r["extremo_roto"] == pytest.approx(H)
    assert r["precio_evento"] == pytest.approx(1.10115)


def test_ruptura_bajista_en_el_minuto_conocido():
    cfg = ayuda.cfg_prueba()
    _, _, tabla = escenario(cfg, [
        dict(momento="2020-06-16 07:00", bajo=1.09880, cierre=1.09885),
    ])
    r = de_la_franja(tabla).loc["ruptura"]
    assert r["t_evento_utc"] == hora("2020-06-16 07:01")
    assert r["direccion"] == -1
    assert r["extremo_roto"] == pytest.approx(L)
    assert r["precio_evento"] == pytest.approx(1.09885)


def test_si_hay_rupturas_de_los_dos_lados_vale_la_primera_en_el_tiempo():
    cfg = ayuda.cfg_prueba()
    _, _, tabla = escenario(cfg, [
        dict(momento="2020-06-16 06:00", bajo=1.09850, cierre=1.09860),   # primero abajo
        dict(momento="2020-06-16 08:00", alto=1.10200, cierre=1.10150),   # despues arriba
    ])
    r = de_la_franja(tabla).loc["ruptura"]
    assert r["direccion"] == -1
    assert r["t_evento_utc"] == hora("2020-06-16 06:01")


def test_la_barra_ambigua_se_excluye():
    cfg = ayuda.cfg_prueba(EXCLUIR_BARRA_AMBIGUA=True)
    cambios = [dict(momento="2020-06-16 06:00", alto=1.10200, bajo=1.09800, cierre=PRECIO)]
    _, _, tabla = escenario(cfg, cambios)
    assert len(de_la_franja(tabla)) == 0, "una barra que rompe los dos lados no da direccion"

    # Con la exclusion apagada si hay evento, y gana el lado que penetro mas.
    cfg2 = ayuda.cfg_prueba(EXCLUIR_BARRA_AMBIGUA=False)
    _, _, tabla2 = escenario(cfg2, cambios)
    r = de_la_franja(tabla2).loc["ruptura"]
    assert r["direccion"] == 1, "10 pips arriba contra 10 pips abajo: empata y gana el alcista"


def test_como_maximo_un_evento_de_cada_tipo_por_franja():
    # Dos rupturas y dos reingresos en la misma franja: solo cuenta el primero
    # de cada tipo.
    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=5)
    cambios = [dict(momento="2020-06-16 06:00", alto=1.10120, cierre=1.10115)]
    cambios += afuera("2020-06-16 06:01", "2020-06-16 06:19")
    cambios += [dict(momento="2020-06-16 06:20", apertura=1.10115, alto=1.10115,
                     bajo=PRECIO, cierre=PRECIO),
                dict(momento="2020-06-16 07:00", alto=1.10300, cierre=1.10250)]
    cambios += afuera("2020-06-16 07:01", "2020-06-16 07:29", precio=1.10250)
    cambios += [dict(momento="2020-06-16 07:30", apertura=1.10250, alto=1.10250,
                     bajo=PRECIO, cierre=PRECIO)]
    _, _, tabla = escenario(cfg, cambios)
    ev = de_la_franja(tabla)
    assert ev.index.value_counts().max() == 1
    assert ev.loc["ruptura"]["t_evento_utc"] == hora("2020-06-16 06:01")
    assert ev.loc["reingreso"]["t_evento_utc"] == hora("2020-06-16 06:21")


# --- sostenida --------------------------------------------------------------

def aguanta_quince_minutos():
    """Rompe a las 06:31 y se queda arriba del extremo hasta pasadas las 06:46."""
    cambios = [dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115)]
    for m in range(31, 60):
        cambios.append(dict(momento=f"2020-06-16 06:{m}", apertura=1.10115,
                            alto=1.10120, bajo=1.10112, cierre=1.10115))
    return cambios


@pytest.mark.parametrize("regla", ["sin_reingreso", "fuera_en_t_mas_m"])
def test_sostenida_ocurre_en_t_mas_m_con_las_dos_reglas(regla):
    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=15, REGLA_SOSTENIDA=regla)
    _, _, tabla = escenario(cfg, aguanta_quince_minutos())
    s = de_la_franja(tabla).loc["sostenida"]
    assert s["t_ruptura_utc"] == hora("2020-06-16 06:31")
    assert s["t_evento_utc"] == hora("2020-06-16 06:46"), "t_ruptura + 15 minutos"
    assert s["direccion"] == 1, "la sostenida hereda la direccion de la ruptura"
    assert s["extremo_roto"] == pytest.approx(H)
    assert s["precio_evento"] == pytest.approx(1.10115)


def test_si_reingresa_y_vuelve_a_salir_antes_de_m_no_hay_sostenida():
    # Rompe a las 06:31, se devuelve adentro a las 06:36 y vuelve a salir a las
    # 06:41. En t+M (06:46) esta fuera, pero hubo un reingreso en el camino.
    cambios = aguanta_quince_minutos()
    cambios.append(dict(momento="2020-06-16 06:35", apertura=1.10115, alto=1.10115,
                        bajo=1.10050, cierre=1.10050))

    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=15, REGLA_SOSTENIDA="sin_reingreso")
    _, _, tabla = escenario(cfg, cambios)
    ev = de_la_franja(tabla)
    assert "sostenida" not in ev.index, "con sin_reingreso, un reingreso previo anula la sostenida"
    assert ev.loc["reingreso"]["t_evento_utc"] == hora("2020-06-16 06:36")

    # La otra regla solo mira el instante t+M, asi que si la declara. Sirve para
    # dejar claro que las dos reglas NO son intercambiables.
    cfg2 = ayuda.cfg_prueba(M_SOSTENIDA_MIN=15, REGLA_SOSTENIDA="fuera_en_t_mas_m")
    _, _, tabla2 = escenario(cfg2, cambios)
    assert de_la_franja(tabla2).loc["sostenida"]["t_evento_utc"] == hora("2020-06-16 06:46")


@pytest.mark.parametrize("regla", ["sin_reingreso", "fuera_en_t_mas_m"])
def test_sin_la_barra_exacta_de_t_mas_m_no_hay_sostenida(regla):
    # Declarar que una ruptura aguanto es afirmar algo sobre un instante
    # preciso. Si falta la barra que cierra en t + M, no se declara, aunque la
    # barra de un minuto antes serviria para medir un retorno.
    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=15, REGLA_SOSTENIDA=regla,
                           TOLERANCIA_PRECIO_MIN=2)

    def quitar(idx):
        # La barra que cierra a las 06:46 es la que ABRE a las 06:45.
        return idx == hora("2020-06-16 06:45")

    _, _, tabla = escenario(cfg, aguanta_quince_minutos(), quitar=quitar)
    ev = de_la_franja(tabla)
    assert "ruptura" in ev.index, "la ruptura si ocurrio y no depende de esa barra"
    assert "sostenida" not in ev.index

    # Con la barra presente, el evento aparece: lo que falta es la barra y no
    # otra cosa del escenario.
    _, _, completo = escenario(cfg, aguanta_quince_minutos())
    assert "sostenida" in de_la_franja(completo).index


def test_la_sostenida_no_puede_caer_despues_del_fin_de_la_franja():
    # La franja termina a las 11:00 UTC. Una ruptura a las 10:55 con M = 15
    # caeria a las 11:10, ya fuera de la franja.
    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=15)
    _, _, tabla = escenario(cfg, [
        dict(momento="2020-06-16 10:54", alto=1.10120, cierre=1.10115),
    ])
    ev = de_la_franja(tabla)
    assert ev.loc["ruptura"]["t_evento_utc"] == hora("2020-06-16 10:55")
    assert "sostenida" not in ev.index


# --- reingreso --------------------------------------------------------------

def test_reingreso_en_el_minuto_conocido():
    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=5)
    cambios = [dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115)]
    cambios += afuera("2020-06-16 06:31", "2020-06-16 06:44")
    # A las 06:45 el cierre vuelve por debajo de H: ese es el reingreso.
    cambios += [dict(momento="2020-06-16 06:45", apertura=1.10115, alto=1.10115,
                     bajo=1.10000, cierre=1.10050)]
    _, _, tabla = escenario(cfg, cambios)
    r = de_la_franja(tabla).loc["reingreso"]
    assert r["t_evento_utc"] == hora("2020-06-16 06:46")
    assert r["direccion"] == 1, "el reingreso hereda la direccion de la ruptura"
    assert r["precio_evento"] == pytest.approx(1.10050)


def test_la_ventana_de_reingreso_acota_la_busqueda():
    cambios = [dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115)]
    cambios += afuera("2020-06-16 06:31", "2020-06-16 07:29")
    cambios += [dict(momento="2020-06-16 07:30", apertura=1.10115, alto=1.10115,
                     bajo=1.10000, cierre=1.10050)]
    # Sin ventana (None) se busca hasta el fin de la franja: lo encuentra.
    cfg = ayuda.cfg_prueba(VENTANA_REINGRESO_MIN=None)
    _, _, tabla = escenario(cfg, cambios)
    assert "reingreso" in de_la_franja(tabla).index

    # Con ventana de 30 minutos, el reingreso de una hora despues queda fuera.
    cfg2 = ayuda.cfg_prueba(VENTANA_REINGRESO_MIN=30)
    _, _, tabla2 = escenario(cfg2, cambios)
    assert "reingreso" not in de_la_franja(tabla2).index


# --- cobertura, huecos y cierres de mercado ---------------------------------

def test_una_franja_de_referencia_incompleta_no_genera_eventos():
    cambios = [dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115)]
    # Se borran 60 de los 360 minutos de la referencia: cobertura 0.833.
    def quitar(idx):
        return (idx >= hora("2020-06-16 03:00")) & (idx < hora("2020-06-16 04:00"))

    cfg = ayuda.cfg_prueba(COBERTURA_MIN_REFERENCIA=0.90)
    _, cal, tabla = escenario(cfg, cambios, quitar=quitar)
    referencia = cal[(cal["fecha_londres"] == pd.Timestamp("2020-06-16")) & (cal["idx_franja"] == 0)]
    assert referencia["cobertura"].iloc[0] == pytest.approx(300 / 360)
    assert len(de_la_franja(tabla)) == 0

    # Bajando la exigencia, la misma franja si genera eventos: lo que manda es
    # la cobertura y no otra cosa.
    cfg2 = ayuda.cfg_prueba(COBERTURA_MIN_REFERENCIA=0.80)
    _, _, tabla2 = escenario(cfg2, cambios, quitar=quitar)
    assert "ruptura" in de_la_franja(tabla2).index


def test_los_huecos_posteriores_al_evento_no_impiden_el_evento():
    # A la franja EN CURSO nunca se le exige cobertura: en el instante t no se
    # sabe si mas adelante faltaran datos.
    cambios = [dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115)]
    cambios += afuera("2020-06-16 06:31", "2020-06-16 06:50")

    def quitar(idx):
        return (idx >= hora("2020-06-16 08:00")) & (idx < hora("2020-06-16 10:30"))

    cfg = ayuda.cfg_prueba(M_SOSTENIDA_MIN=15)
    _, cal, tabla = escenario(cfg, cambios, quitar=quitar)
    en_curso = cal[(cal["fecha_londres"] == pd.Timestamp("2020-06-16")) & (cal["idx_franja"] == 1)]
    assert en_curso["cobertura"].iloc[0] < 0.90, "la franja en curso quedo incompleta"
    ev = de_la_franja(tabla)
    assert ev.loc["ruptura"]["t_evento_utc"] == hora("2020-06-16 06:31")
    assert "sostenida" in ev.index


def test_una_franja_de_lunes_precedida_por_un_cierre_no_genera_eventos():
    # Fin de semana de verdad: el mercado cierra el viernes a las 21:00 UTC y
    # vuelve el domingo a las 21:00 UTC. La franja [0,6) del lunes tiene como
    # referencia la [18,24) del domingo, que empieza con el mercado cerrado.
    def construir(cfg):
        idx = ayuda.indice("2020-06-19 00:00", 4 * 24 * 60)      # viernes a lunes
        cerrado = (idx >= hora("2020-06-19 21:00")) & (idx < hora("2020-06-21 21:00"))
        idx = idx[~cerrado]
        velas = ayuda.plano(len(idx), PRECIO)
        pos = int(idx.get_loc(hora("2020-06-21 22:00")))
        velas[pos, 1] = 1.10100                                  # H de la referencia
        pos2 = int(idx.get_loc(hora("2020-06-22 01:00")))
        velas[pos2, 1] = 1.10200                                 # ruptura del lunes
        velas[pos2, 3] = 1.10150
        datos = ayuda.datos(velas, idx=idx)
        barras = franjas.Barras.desde(datos, cfg)
        cal = franjas.calendario(barras, cfg)
        tabla = eventos.detectar(barras, cal, cfg, sigma=ayuda.sigma_fija(len(cal)))
        return cal, tabla[tabla["id_franja"] == "2020-06-22_0"]

    # 1) Por cobertura: la referencia del domingo tiene 2 horas de 6.
    _, ev = construir(ayuda.cfg_prueba())
    assert len(ev) == 0

    # 2) Aun regalando la cobertura, la regla del cierre la sigue bloqueando.
    cal, ev = construir(ayuda.cfg_prueba(COBERTURA_MIN_REFERENCIA=0.0))
    domingo = cal[(cal["fecha_londres"] == pd.Timestamp("2020-06-21")) & (cal["idx_franja"] == 3)]
    assert domingo["hueco_inicial"].iloc[0] > 60, "la franja del domingo empieza cerrada"
    assert len(ev) == 0

    # 3) Y si el grupo decidiera permitirlo, el evento aparece. Queda demostrado
    #    que lo que bloquea es la regla y no un accidente de los datos.
    _, ev = construir(ayuda.cfg_prueba(COBERTURA_MIN_REFERENCIA=0.0,
                                       REFERENCIA_CRUZA_CIERRE=True))
    assert list(ev["tipo"]) != []
    assert ev.iloc[0]["t_evento_utc"] == hora("2020-06-22 01:01")


def test_sin_sigma_de_referencia_no_hay_eventos():
    # Con tres dias de datos no alcanzan los DIAS_VOL_REF_MIN dias previos, asi
    # que sigma_ref es NaN y el motor no emite eventos.
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2020-06-15 00:00", 3 * 24 * 60)
    velas = ayuda.plano(len(idx), PRECIO)
    ayuda.fijar(velas, idx, "2020-06-16 01:00", alto=H)
    ayuda.fijar(velas, idx, "2020-06-16 06:30", alto=1.10120, cierre=1.10115)
    datos = ayuda.datos(velas, idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    assert len(eventos.detectar(barras, cal, cfg)) == 0


# --- regla 3a ---------------------------------------------------------------

def test_precio_evento_es_el_cierre_de_la_barra_de_indice_t_menos_un_minuto():
    # La barra que ABRE a las 06:30 cierra a las 06:31. El precio del evento de
    # las 06:31 es el cierre de ESA barra, no el de la barra que abre a las
    # 06:31 (que en ese instante todavia no existe).
    cfg = ayuda.cfg_prueba()
    barras, _, tabla = escenario(cfg, [
        dict(momento="2020-06-16 06:30", alto=1.10120, cierre=1.10115),
        dict(momento="2020-06-16 06:31", apertura=1.10115, alto=1.10500, cierre=1.10480),
    ])
    r = de_la_franja(tabla).loc["ruptura"]
    assert r["t_evento_utc"] == hora("2020-06-16 06:31")
    assert r["precio_evento"] == pytest.approx(1.10115)
    assert r["precio_evento"] != pytest.approx(1.10480)
    # Y lo mismo dicho con la herramienta que usa el motor: la barra observable
    # a las 06:31 es la que ABRE a las 06:30.
    k = barras.indice_al_cierre(np.int64(tiempo.a_ns(hora("2020-06-16 06:31"))))
    assert barras.indice[k] == hora("2020-06-16 06:30")
    assert barras.mid_c[k] == pytest.approx(1.10115)
