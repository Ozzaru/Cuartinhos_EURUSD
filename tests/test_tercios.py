# -*- coding: utf-8 -*-
"""
Pruebas del emparejamiento por tercio de franja.

La posicion dentro de la franja se mide sobre el largo REAL, no sobre seis
horas fijas. Eso importa en dos sitios donde es facil equivocarse: los dias de
cambio de hora, cuando una franja dura cinco o siete horas, y la franja del
viernes, que termina cuando cierra el mercado.
"""
import numpy as np
import pandas as pd
import pytest

import ayuda
import motor
from motor import franjas, nula, tiempo


def hora(momento):
    return pd.Timestamp(momento, tz="UTC")


def contexto(idx, cfg, precio=1.10):
    datos = ayuda.datos(ayuda.plano(len(idx), precio), idx=idx)
    barras = franjas.Barras.desde(datos, cfg)
    return barras, franjas.calendario(barras, cfg)


def fila_de(cal, fecha, idx_franja):
    sel = cal[(cal["fecha_londres"] == pd.Timestamp(fecha))
              & (cal["idx_franja"] == idx_franja)]
    assert len(sel) == 1
    return sel.index[0], sel.iloc[0]


# --- fin real de la franja --------------------------------------------------

def test_el_fin_real_es_el_fin_de_la_franja_cuando_no_hay_cierre():
    cfg = ayuda.cfg_prueba()
    barras, cal = contexto(ayuda.indice("2020-06-15 00:00", 3 * 24 * 60), cfg)
    _, f = fila_de(cal, "2020-06-16", 1)
    assert f["fin_real_ns"] == f["fin_ns"]


def test_el_fin_real_del_viernes_es_el_cierre_de_mercado():
    # Viernes 19-jun-2020: la franja [18,24) de Londres va de 17:00 a 23:00 UTC,
    # pero el mercado cierra a las 21:00.
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2020-06-19 00:00", 3 * 24 * 60)
    cerrado = (idx >= hora("2020-06-19 21:00")) & (idx < hora("2020-06-21 21:00"))
    barras, cal = contexto(idx[~cerrado], cfg)
    _, f = fila_de(cal, "2020-06-19", 3)
    assert tiempo.de_ns(f["fin_ns"]) == hora("2020-06-19 23:00")
    assert tiempo.de_ns(f["fin_real_ns"]) == hora("2020-06-19 21:00")


# --- cortes de los tercios --------------------------------------------------

@pytest.mark.parametrize("fecha, inicio_utc, largo_horas, etiqueta", [
    ("2020-06-16", "2020-06-15 23:00", 6, "dia normal de verano"),
    ("2020-03-29", "2020-03-29 00:00", 5, "dia en que Londres adelanta el reloj"),
    ("2020-10-25", "2020-10-24 23:00", 7, "dia en que Londres atrasa el reloj"),
])
def test_los_cortes_de_los_tercios_caen_donde_corresponde(fecha, inicio_utc,
                                                          largo_horas, etiqueta):
    # La franja [0,6) de Londres dura 5, 6 o 7 horas segun el dia. Los cortes
    # tienen que partir ESE largo en tres, no seis horas siempre.
    cfg = ayuda.cfg_prueba()
    comienzo = (pd.Timestamp(fecha) - pd.Timedelta(days=1)).strftime("%Y-%m-%d 00:00")
    barras, cal = contexto(ayuda.indice(comienzo, 3 * 24 * 60), cfg)
    pos, f = fila_de(cal, fecha, 0)

    assert f["minutos_esperados"] == largo_horas * 60, etiqueta
    inicio = hora(inicio_utc)
    assert tiempo.de_ns(f["inicio_ns"]) == inicio

    minutos = largo_horas * 60
    # Se consulta el instante de CIERRE de cada barra, que es como lo hace el
    # motor: la barra que abre en inicio + k cierra en inicio + k + 1.
    momentos = tiempo.a_ns(pd.DatetimeIndex(
        [inicio + pd.Timedelta(minutes=k + 1) for k in range(minutos)]))
    tercios = franjas.tercio_de_franja(momentos, np.full(minutos, pos), cal)

    assert set(np.unique(tercios)) == {0, 1, 2}
    cuentas = np.bincount(tercios, minlength=3)
    assert abs(cuentas[0] - minutos / 3) <= 1
    assert abs(cuentas[1] - minutos / 3) <= 1
    # El corte cae a un tercio del largo REAL de la franja. La convencion es la
    # habitual: el instante justo EN el corte ya pertenece al tercio siguiente.
    primer_corte = inicio + pd.Timedelta(minutes=minutos // 3)
    assert franjas.tercio_de_franja(
        [tiempo.a_ns(primer_corte - pd.Timedelta(minutes=1))], [pos], cal)[0] == 0
    assert franjas.tercio_de_franja(
        [tiempo.a_ns(primer_corte)], [pos], cal)[0] == 1
    segundo_corte = inicio + pd.Timedelta(minutes=2 * minutos // 3)
    assert franjas.tercio_de_franja(
        [tiempo.a_ns(segundo_corte - pd.Timedelta(minutes=1))], [pos], cal)[0] == 1
    assert franjas.tercio_de_franja(
        [tiempo.a_ns(segundo_corte)], [pos], cal)[0] == 2


def test_la_posicion_relativa_va_de_cero_a_uno():
    cfg = ayuda.cfg_prueba()
    barras, cal = contexto(ayuda.indice("2020-06-15 00:00", 3 * 24 * 60), cfg)
    pos, f = fila_de(cal, "2020-06-16", 1)
    inicio, fin = int(f["inicio_ns"]), int(f["fin_real_ns"])

    proporciones = franjas.posicion_en_franja(
        [inicio, (inicio + fin) // 2, fin], [pos] * 3, cal)
    assert proporciones[0] == pytest.approx(0.0)
    assert proporciones[1] == pytest.approx(0.5, abs=1e-6)
    assert proporciones[2] == pytest.approx(1.0)


def test_el_viernes_recortado_reparte_los_tercios_sobre_el_largo_real():
    # Si los tercios se calcularan sobre las seis horas nominales, un evento de
    # las 20:00 (que esta al final del mercado) caeria en el tercio del medio.
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2020-06-19 00:00", 3 * 24 * 60)
    cerrado = (idx >= hora("2020-06-19 21:00")) & (idx < hora("2020-06-21 21:00"))
    barras, cal = contexto(idx[~cerrado], cfg)
    pos, _ = fila_de(cal, "2020-06-19", 3)
    # Franja real: 17:00 a 21:00, o sea cuatro horas. Los cortes van a las
    # 18:20 y 19:40.
    tercios = franjas.tercio_de_franja(
        tiempo.a_ns(pd.DatetimeIndex([hora("2020-06-19 18:00"),
                                      hora("2020-06-19 19:00"),
                                      hora("2020-06-19 20:00")])),
        [pos] * 3, cal)
    assert list(tercios) == [0, 1, 2]


# --- la nula usa el tercio --------------------------------------------------

def mercado_de_prueba(semilla=3, dias=200):
    cfg = ayuda.cfg_prueba()
    idx = ayuda.indice("2016-01-04 00:00", dias * 24 * 60)
    velas = ayuda.camino_aleatorio(len(idx), semilla=semilla)
    barras, cal, ev = motor.preparar(ayuda.datos(velas, idx=idx), cfg)
    return cfg, barras, cal, ev


def test_la_nula_solo_sortea_minutos_del_mismo_tercio(monkeypatch):
    cfg, barras, cal, ev = mercado_de_prueba()
    candidatos = nula.preparar_candidatos(barras, cal, cfg)
    tercio_cand = candidatos["tercio"]
    assert set(np.unique(tercio_cand)) == {0, 1, 2}

    registro = []
    original = nula._sortear

    def espia(rng, pools, claves, franja_evento, pos_cand, repeticiones, **kw):
        indices, usable = original(rng, pools, claves, franja_evento, pos_cand,
                                   repeticiones, **kw)
        registro.append((claves.copy(), indices.copy(), usable.copy()))
        return indices, usable

    monkeypatch.setattr(nula, "_sortear", espia)
    nula.correr(barras, cal, ev, cfg, semilla=1, repeticiones=15,
                candidatos=candidatos)

    assert registro
    revisados = 0
    for claves, indices, usable in registro:
        if not usable.any():
            continue
        # El tercio esta en las dos ultimas cifras de la clave.
        tercio_evento = claves % 100
        for i in np.flatnonzero(usable):
            sorteados = indices[:, i]
            assert np.all(tercio_cand[sorteados] == tercio_evento[i]), \
                "se sorteo un minuto de otro tercio de la franja"
            revisados += 1
    assert revisados > 50, "hacen falta eventos revisados para que valga"


def test_la_clave_de_emparejamiento_junta_las_cuatro_variables():
    a = nula._clave(1, 2, 3, 0)
    assert nula._clave(1, 2, 3, 1) != a, "el tercio tiene que cambiar la clave"
    assert nula._clave(1, 2, 4, 0) != a, "el decil tiene que cambiar la clave"
    assert nula._clave(1, 3, 3, 0) != a, "el dia tiene que cambiar la clave"
    assert nula._clave(2, 2, 3, 0) != a, "la franja tiene que cambiar la clave"
    # Y ninguna combinacion distinta puede dar la misma clave.
    todas = [nula._clave(f, d, g, t) for f in range(4) for d in range(7)
             for g in range(10) for t in range(3)]
    assert len(set(todas)) == len(todas)


def test_los_estratos_quedan_con_candidatos_suficientes():
    # Si al agregar el tercio los estratos quedaran casi vacios, habria que
    # bajar los deciles a quintiles. Esta prueba vigila que eso no pase sin
    # que nos enteremos.
    cfg, barras, cal, ev = mercado_de_prueba()
    candidatos = nula.preparar_candidatos(barras, cal, cfg)
    disponible = candidatos["sirve"] & np.isfinite(candidatos["retornos"][60])
    pools = nula._armar_pools(candidatos, disponible)

    claves = nula.claves_de_eventos(ev, cal, candidatos)
    tamanos = np.array([len(pools.get(int(k), [])) for k in claves])
    assert np.median(tamanos) > 200
    assert (tamanos < 30).mean() < 0.05, "demasiados eventos con estrato pobre"
