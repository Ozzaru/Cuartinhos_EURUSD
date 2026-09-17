# -*- coding: utf-8 -*-
"""
Pruebas de la volatilidad de referencia y de los retornos posteriores.

Lo que se vigila aqui:
  - sigma_ref usa dias ANTERIORES y nunca el dia del propio evento;
  - el signo: positivo = el precio siguio la direccion de la ruptura;
  - la normalizacion: dividir por sigma_ref * raiz(h);
  - los horizontes que cruzan un cierre de mercado quedan en NaN;
  - "fin_franja" se corta en el cierre del viernes.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
from motor import franjas, resultados, tiempo


def hora(momento):
    return pd.Timestamp(momento, tz="UTC")


def serie_con_volatilidad(dias, r_por_dia, inicio="2020-06-01 00:00", precio=1.10):
    """
    Una serie donde la franja [6,12) de Londres (05:00 a 11:00 UTC en verano)
    se mueve con retornos de 1 minuto de magnitud exacta r, alternando arriba y
    abajo. Asi la desviacion tipica de esa franja es exactamente r y se puede
    comparar contra un numero escrito a mano.
    """
    idx = ayuda.indice(inicio, dias * 24 * 60)
    velas = ayuda.plano(len(idx), precio)

    dia = (idx.normalize() - idx.normalize()[0]).days.to_numpy()
    en_franja = (idx.hour >= 5) & (idx.hour < 11)
    alterna = (np.arange(len(idx)) % 2) == 1
    r = np.asarray(r_por_dia, dtype=float)[np.minimum(dia, len(r_por_dia) - 1)]

    cierres = precio * np.exp(np.where(alterna, r, 0.0))
    velas[en_franja, 3] = cierres[en_franja]
    aperturas = np.concatenate([[velas[0, 3]], velas[:-1, 3]])
    velas[en_franja, 0] = aperturas[en_franja]
    velas[:, 1] = np.maximum(velas[:, 0], velas[:, 3])
    velas[:, 2] = np.minimum(velas[:, 0], velas[:, 3])
    return ayuda.datos(velas, idx=idx)


def test_sigma_ref_no_usa_el_dia_del_evento():
    # Catorce dias tranquilos y el ultimo mucho mas movido. Si sigma_ref del
    # ultimo dia se contagiara de su propio dia, saltaria a 1e-2. Es la trampa
    # clasica del rolling de pandas, que incluye la fila actual.
    dias = 15
    r = [1e-4] * (dias - 1) + [1e-2]
    cfg = ayuda.cfg_prueba(DIAS_VOL_REF=20, DIAS_VOL_REF_MIN=10)
    datos = serie_con_volatilidad(dias, r)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    sigma = resultados.sigma_por_franja(barras, cal, cfg)

    ultimo = cal[(cal["fecha_londres"] == pd.Timestamp("2020-06-15")) & (cal["idx_franja"] == 1)]
    valor = sigma[ultimo.index[0]]
    assert valor == pytest.approx(1e-4, rel=1e-6), "sigma_ref se contagio del dia del evento"


def test_sigma_ref_es_nan_hasta_juntar_los_dias_minimos():
    dias = 15
    cfg = ayuda.cfg_prueba(DIAS_VOL_REF=20, DIAS_VOL_REF_MIN=10)
    datos = serie_con_volatilidad(dias, [1e-4] * dias)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    sigma = resultados.sigma_por_franja(barras, cal, cfg)

    solo_franja_1 = cal["idx_franja"] == 1
    filas = cal[solo_franja_1].index.to_numpy()
    # Las primeras 10 franjas de ese tipo no tienen 10 dias previos validos.
    assert np.all(np.isnan(sigma[filas[:10]]))
    assert np.all(np.isfinite(sigma[filas[10:]]))
    assert sigma[filas[10]] == pytest.approx(1e-4, rel=1e-6)


def test_la_mediana_del_rango_tampoco_usa_el_dia_actual():
    cfg = ayuda.cfg_prueba(DIAS_COMPRESION=20, DIAS_COMPRESION_MIN=3)
    idx = ayuda.indice("2020-06-01 00:00", 10 * 24 * 60)
    velas = ayuda.plano(len(idx), 1.10)
    # La franja [6,12) de cada dia tiene un rango conocido: 10 pips los primeros
    # dias y 100 pips el ultimo.
    dia = (idx.normalize() - idx.normalize()[0]).days.to_numpy()
    en_franja = (idx.hour >= 5) & (idx.hour < 11)
    alto = np.where(dia < 9, 1.10100, 1.11000)
    velas[en_franja, 1] = alto[en_franja]
    datos = ayuda.datos(velas, idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    mediana = resultados.mediana_rango_pasada(cal, cfg)

    ultimo = cal[(cal["fecha_londres"] == pd.Timestamp("2020-06-10")) & (cal["idx_franja"] == 1)]
    assert mediana[ultimo.index[0]] == pytest.approx(0.00100, rel=1e-9)
    assert cal.loc[ultimo.index[0], "rango"] == pytest.approx(0.01000, rel=1e-9)


# --- retornos ---------------------------------------------------------------

def evento_a_mano(cal, momento, direccion=1, sigma=1e-4):
    """Un evento minimo, escrito a mano, para probar solo el calculo de retornos."""
    t = tiempo.a_ns(hora(momento))
    # La franja del evento es la de la barra que CIERRA en t, o sea la que abre
    # un minuto antes.
    pos = int(np.searchsorted(cal["inicio_ns"].to_numpy(), t - tiempo.NS_MIN, side="right") - 1)
    return pd.DataFrame([{
        "id_franja": "prueba", "fecha_londres": cal["fecha_londres"].iloc[pos],
        "idx_franja": int(cal["idx_franja"].iloc[pos]), "tipo": "ruptura",
        "direccion": direccion, "t_evento_utc": hora(momento),
        "t_ruptura_utc": hora(momento), "extremo_roto": 1.10100,
        "precio_evento": np.nan, "dia_semana": int(cal["dia_semana"].iloc[pos]),
        "pos_franja": pos, "t_evento_ns": t, "t_ruptura_ns": t, "sigma_ref": sigma,
    }])


def serie_con_escalon(precio_final, momento_escalon="2020-06-16 07:00"):
    """Plana en 1.10000 y a partir de `momento_escalon` plana en otro precio."""
    idx = ayuda.indice("2020-06-15 00:00", 3 * 24 * 60)
    velas = ayuda.plano(len(idx), 1.10000)
    desde = idx >= hora(momento_escalon)
    velas[desde, :] = precio_final
    return ayuda.datos(velas, idx=idx)


@pytest.mark.parametrize("direccion, esperado", [(1, 1.82483), (-1, -1.82483)])
def test_signo_y_normalizacion_del_retorno(direccion, esperado):
    # El precio pasa de 1.10000 a 1.10110, o sea 1.001 veces. A mano:
    #   ln(1.001) = 0.00099950033
    #   sigma * raiz(30) = 1e-4 * 5.4772256 = 0.00054772256
    #   cociente = 1.824834
    # Con direccion +1 el precio siguio la ruptura y el retorno es positivo;
    # con direccion -1, la misma subida significa que se devolvio.
    cfg = ayuda.cfg_prueba(HORIZONTES=[30])
    datos = serie_con_escalon(1.10110, "2020-06-16 07:00")
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    ev = evento_a_mano(cal, "2020-06-16 06:31", direccion=direccion)
    salida = resultados.agregar_retornos(barras, cal, ev, cfg)
    assert salida["ret_30"].iloc[0] == pytest.approx(esperado, abs=1e-5)


def test_el_retorno_usa_el_precio_de_la_barra_que_cierra_en_t_mas_h():
    cfg = ayuda.cfg_prueba(HORIZONTES=[30])
    datos = serie_con_escalon(1.10110, "2020-06-16 07:00")
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    # El evento es a las 06:30 y el horizonte cae a las 07:00. La barra que
    # cierra a las 07:00 es la que abre a las 06:59, que todavia vale 1.10000:
    # el escalon recien se ve en la barra siguiente. Retorno cero.
    ev = evento_a_mano(cal, "2020-06-16 06:30")
    salida = resultados.agregar_retornos(barras, cal, ev, cfg)
    assert salida["ret_30"].iloc[0] == pytest.approx(0.0, abs=1e-12)


def test_un_horizonte_que_cruza_un_cierre_de_mercado_queda_en_nan():
    cfg = ayuda.cfg_prueba(HORIZONTES=[10, 30])
    idx = ayuda.indice("2020-06-15 00:00", 3 * 24 * 60)
    # Cierre de mercado de dos horas a partir de las 06:50.
    cerrado = (idx >= hora("2020-06-16 06:50")) & (idx < hora("2020-06-16 08:50"))
    idx = idx[~cerrado]
    datos = ayuda.datos(ayuda.plano(len(idx), 1.10000), idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)

    ev = evento_a_mano(cal, "2020-06-16 06:31")
    salida = resultados.agregar_retornos(barras, cal, ev, cfg)
    assert np.isfinite(salida["ret_10"].iloc[0]), "a 10 minutos el mercado sigue abierto"
    assert np.isnan(salida["ret_30"].iloc[0]), "a 30 minutos el horizonte cruza el cierre"


def test_fin_de_franja_se_corta_en_el_cierre_del_viernes():
    # Viernes 19-jun-2020. La franja [18,24) de Londres va de 17:00 a 23:00 UTC,
    # pero el mercado cierra a las 21:00 UTC. Un evento a las 19:00 mide hasta
    # las 21:00 (120 minutos), no hasta las 23:00.
    cfg = ayuda.cfg_prueba(HORIZONTES=["fin_franja"])
    idx = ayuda.indice("2020-06-19 00:00", 3 * 24 * 60)
    cerrado = (idx >= hora("2020-06-19 21:00")) & (idx < hora("2020-06-21 21:00"))
    idx = idx[~cerrado]
    datos = ayuda.datos(ayuda.plano(len(idx), 1.10000), idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)

    ev = evento_a_mano(cal, "2020-06-19 19:00")
    salida = resultados.agregar_retornos(barras, cal, ev, cfg)
    assert salida["h_fin_franja"].iloc[0] == pytest.approx(120.0)
    assert np.isfinite(salida["ret_fin_franja"].iloc[0])

    # En cambio, un evento de un jueves a la misma hora, con el mercado abierto
    # toda la franja, mide los 240 minutos completos.
    cfg2 = ayuda.cfg_prueba(HORIZONTES=["fin_franja"])
    idx2 = ayuda.indice("2020-06-17 00:00", 2 * 24 * 60)
    datos2 = ayuda.datos(ayuda.plano(len(idx2), 1.10000), idx=idx2)
    barras2 = franjas.Barras.desde(datos2, cfg2)
    cal2 = franjas.calendario(barras2, cfg2)
    salida2 = resultados.agregar_retornos(barras2, cal2,
                                          evento_a_mano(cal2, "2020-06-18 19:00"), cfg2)
    assert salida2["h_fin_franja"].iloc[0] == pytest.approx(240.0)


def test_si_falta_la_barra_se_acepta_una_de_hasta_dos_minutos_antes():
    cfg = ayuda.cfg_prueba(HORIZONTES=[30], TOLERANCIA_PRECIO_MIN=2)
    idx = ayuda.indice("2020-06-15 00:00", 3 * 24 * 60)
    # Falta la barra que cierra a las 07:01 (la que abre a las 07:00).
    falta = idx == hora("2020-06-16 07:00")
    idx_corto = idx[~falta]
    datos = ayuda.datos(ayuda.plano(len(idx_corto), 1.10000), idx=idx_corto)
    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    ev = evento_a_mano(cal, "2020-06-16 06:31")
    assert np.isfinite(resultados.agregar_retornos(barras, cal, ev, cfg)["ret_30"].iloc[0])

    # Con un hueco de tres minutos ya no hay barra aceptable: NaN.
    falta3 = (idx >= hora("2020-06-16 06:58")) & (idx < hora("2020-06-16 07:01"))
    idx_corto3 = idx[~falta3]
    datos3 = ayuda.datos(ayuda.plano(len(idx_corto3), 1.10000), idx=idx_corto3)
    barras3 = franjas.Barras.desde(datos3, cfg)
    cal3 = franjas.calendario(barras3, cfg)
    ev3 = evento_a_mano(cal3, "2020-06-16 06:31")
    assert np.isnan(resultados.agregar_retornos(barras3, cal3, ev3, cfg)["ret_30"].iloc[0])
