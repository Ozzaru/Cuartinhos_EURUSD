# -*- coding: utf-8 -*-
"""
CALIDAD — control de calidad de los datos reales (pre-registro, seccion 3.3).

Corre sobre las dos fuentes, ano por ano. De las rupturas usa SOLO si hay, la
direccion y el minuto (regla 1 del punto G): no mide nada de lo que pasa
despues de una ruptura ni clasifica eventos mas alla de ella. Por eso importa
`motor.franjas` y `motor.rupturas`, y nunca `eventos`, `resultados`, `nula` ni
`inferencia` (tests/test_candado.py lo vigila). Es el unico modulo al que el
cargador le entrega precios mientras no exista la etiqueta `prerregistro-v1`.

Chequeos (todos por ano; los de una sola fuente, por fuente):
  1. Barras: velas planas (faltantes), barras invalidas por motivo y su
     porcentaje sobre las no planas. Criterio: menos de 0,1%.
  2. Zona horaria: correlacion entre fuentes de los cambios logaritmicos de 1
     minuto del bid de cierre, para desfases de -120 a +120 minutos (Dukascopy
     en t contra HistData en t + desfase). El maximo tiene que estar en 0.
  3. Semana: primera barra despues del cierre de fin de semana (domingo, entre
     21:00 y 23:00 UTC) y ultima antes de el (viernes, entre 20:00 y 22:00
     UTC). Se listan las semanas fuera de rango.
  4. Huecos de mas de 60 minutos fuera del fin de semana, listados, y el
     porcentaje de franjas de lunes a viernes bajo la cobertura minima.
  5. Horario de verano: las franjas que no duran 6 horas tienen que caer en los
     dias de cambio de hora del Reino Unido (5 o 7 horas). En las semanas en que
     EE. UU. y el Reino Unido no coinciden, la apertura y el cierre tienen que
     seguir a Nueva York.
  6. Spread (Dukascopy): mediana y percentil 95 por hora UTC; barras con mas de
     10 pips (se reportan, no se borran).
  7. Extremos por franja: diferencia entre fuentes de H y L del bid, en pips.
  8. Rupturas coincidentes: el detector del motor sobre el bid de las dos
     fuentes, con el umbral principal. Acuerdo en "hay ruptura y en que
     direccion" (al menos 90%) y, cuando coinciden, diferencia de hora de 2
     minutos o menos.

Todo lo que no es "barras" (1) se calcula sobre las barras que cuentan: sin
velas planas ni invalidas, igual que las vera el analisis.

Uso:
    python -m fuentes.calidad --desde 2016-01-01 --hasta 2016-01-31 --salida resultados/calidad_piloto.md
"""
import argparse
import datetime as dt
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                    # noqa: E402
from fuentes import cargador     # noqa: E402
from motor import franjas, rupturas, tiempo   # noqa: E402

LADOS = ("open", "high", "low", "close")
UN_MINUTO = pd.Timedelta(minutes=1)
CATEGORIAS = {1: "alcista", -1: "bajista", 0: "sin ruptura"}


# -----------------------------------------------------------------------------
#  Piezas comunes
# -----------------------------------------------------------------------------
def _barras_bid(datos, cfg):
    """Barras del motor armadas con el bid: su "precio medio" es el bid exacto."""
    bid = datos[[f"bid_{x}" for x in LADOS]]
    tabla = pd.concat([bid, bid.set_axis([f"ask_{x}" for x in LADOS], axis=1)], axis=1)
    return franjas.Barras.desde(tabla, cfg)


def _huecos(indice, cfg):
    """
    Huecos de mas de HUECO_CIERRE_MIN minutos entre barras consecutivas.
    `inicio` es el cierre de la ultima barra antes del hueco y `fin` la apertura
    de la primera despues. Un hueco es "de fin de semana" si contiene el
    mediodia UTC de un sabado.
    """
    if len(indice) < 2:
        return pd.DataFrame(columns=["ultima_barra", "inicio", "fin", "minutos",
                                     "fin_de_semana", "sabado"])
    ap = tiempo.a_ns(indice)
    minutos = np.diff(ap) // tiempo.NS_MIN - 1
    i = np.flatnonzero(minutos > cfg.HUECO_CIERRE_MIN)
    ultima = indice[i]
    inicio = ultima + UN_MINUTO
    fin = indice[i + 1]
    dias = (5 - inicio.dayofweek) % 7
    sabado = inicio.normalize() + pd.to_timedelta(dias, unit="D") + pd.Timedelta(hours=12)
    sabado = sabado.where(sabado >= inicio, sabado + pd.Timedelta(days=7))
    return pd.DataFrame({"ultima_barra": ultima, "inicio": inicio, "fin": fin,
                         "minutos": minutos[i], "fin_de_semana": np.asarray(sabado < fin),
                         "sabado": sabado.normalize()})


def _hora_ny_en_utc(fechas, cfg, minutos_menos=0):
    """El corte semanal de Nueva York (17:00) de cada fecha, en UTC."""
    local = (pd.DatetimeIndex(fechas).normalize().tz_localize(None)
             + pd.Timedelta(hours=cfg.CALIDAD_CORTE_SEMANAL_NY)
             - pd.Timedelta(minutes=minutos_menos))
    return local.tz_localize(cfg.CALIDAD_ZONA_NUEVA_YORK).tz_convert("UTC")


def _desfase_ny_londres_horas(instantes, cfg):
    """Diferencia horaria Nueva York - Londres (normalmente -5; -4 si no coinciden)."""
    ny = pd.DatetimeIndex(instantes).tz_convert(cfg.CALIDAD_ZONA_NUEVA_YORK)
    lo = pd.DatetimeIndex(instantes).tz_convert(cfg.ZONA)
    off_ny = np.array([t.utcoffset().total_seconds() for t in ny]) / 3600
    off_lo = np.array([t.utcoffset().total_seconds() for t in lo]) / 3600
    return off_ny - off_lo


def _dentro(hora, rango_horas):
    """hora (con minutos) dentro de [desde:00, hasta:00]."""
    h = hora.hour + hora.minute / 60
    return (h >= rango_horas[0]) & (h <= rango_horas[1])


# -----------------------------------------------------------------------------
#  0. Formato y escala
# -----------------------------------------------------------------------------
def _decimales(valores, maximo=8):
    """Menor numero de decimales con que se escriben todos los precios."""
    valores = valores[np.isfinite(valores)]
    for k in range(maximo + 1):
        escalados = valores * 10 ** k
        if np.all(np.abs(escalados - np.round(escalados)) < 1e-6):
            return k
    return np.nan


def chequeo_formato(datos, fuente, anio, cfg):
    """Que trae el archivo: primera y ultima barra, escala, decimales y volumen."""
    precios = datos[[f"{lado}_{x}" for lado in ("bid", "ask") for x in LADOS
                     if f"{lado}_{x}" in datos.columns]].to_numpy(float)
    fila = {"anio": anio, "fuente": fuente,
            "primera_barra": datos.index.min(), "ultima_barra": datos.index.max(),
            "minutos_exactos": bool((datos.index.second == 0).all()
                                    and (datos.index.microsecond == 0).all()),
            "precio_min": float(np.nanmin(precios)), "precio_max": float(np.nanmax(precios)),
            "decimales": _decimales(precios.ravel()),
            "pct_un_solo_precio": float((datos["bid_high"] == datos["bid_low"]).mean()),
            "mediana_rango_barra_pips": float(((datos["bid_high"] - datos["bid_low"]) / cfg.PIP).median())}
    volumen = [c for c in datos.columns if "volumen" in c]
    fila["volumen_mediano"] = float(datos[volumen[0]].median())
    fila["volumen_cero"] = float((datos[volumen[0]] == 0).mean())
    return fila


# -----------------------------------------------------------------------------
#  1. Barras
# -----------------------------------------------------------------------------
def chequeo_barras(datos, fuente, anio, cfg):
    marcas = cargador.diagnostico(datos, fuente)
    no_planas = int((~marcas["plana"]).sum())
    invalidas = int(marcas["invalida"].sum())
    fila = {"anio": anio, "fuente": fuente, "barras": len(datos),
            "planas": int(marcas["plana"].sum()), "no_planas": no_planas,
            "invalidas": invalidas,
            "pct_invalidas": invalidas / no_planas if no_planas else np.nan}
    validas = ~marcas["plana"]
    for motivo in [c for c in marcas.columns if c not in ("plana", "invalida")]:
        fila[f"inv_{motivo}"] = int((marcas[motivo] & validas).sum())
    if fuente == "dukascopy":
        un_lado = (datos["bid_volumen"] == 0) != (datos["ask_volumen"] == 0)
        fila["planas_un_solo_lado"] = int(un_lado.sum())
        # Planas con el mercado abierto (fuera de viernes 22:00 a domingo 21:00
        # UTC): esas son las que pasan a ser huecos de verdad.
        dia, hora = datos.index.dayofweek, datos.index.hour
        finde = (dia == 5) | ((dia == 4) & (hora >= 22)) | ((dia == 6) & (hora < 21))
        fila["planas_mercado_abierto"] = int((marcas["plana"].to_numpy() & ~finde).sum())
    fila["cumple"] = bool(fila["pct_invalidas"] < cfg.CALIDAD_MAX_INVALIDAS)
    return fila


# -----------------------------------------------------------------------------
#  2. Zona horaria
# -----------------------------------------------------------------------------
def correlacion_por_desfase(a, b, max_desfase):
    """
    Correlacion entre a[t] y b[t + k] para k en -max..+max, sobre una grilla
    comun de minutos (NaN donde falta). Devuelve un DataFrame (desfase, n, correlacion).
    """
    filas = []
    n = len(a)
    for k in range(-max_desfase, max_desfase + 1):
        if k >= 0:
            x, y = a[:n - k], b[k:]
        else:
            x, y = a[-k:], b[:n + k]
        ok = np.isfinite(x) & np.isfinite(y)
        c = np.corrcoef(x[ok], y[ok])[0, 1] if ok.sum() > 2 else np.nan
        filas.append((k, int(ok.sum()), float(c)))
    return pd.DataFrame(filas, columns=["desfase_min", "pares", "correlacion"])


def chequeo_zona(limpias, anio, cfg):
    d, h = limpias["dukascopy"], limpias["histdata"]
    ini = min(d.index.min(), h.index.min())
    fin = max(d.index.max(), h.index.max())
    grilla = pd.date_range(ini, fin, freq="min")
    cambios = {}
    for nombre, tabla in (("dukascopy", d), ("histdata", h)):
        cierre = tabla["bid_close"].reindex(grilla).to_numpy(float)
        cambios[nombre] = np.diff(np.log(cierre))
    detalle = correlacion_por_desfase(cambios["dukascopy"], cambios["histdata"],
                                      cfg.CALIDAD_DESFASE_MAX_MIN)
    detalle.insert(0, "anio", anio)
    mejor = detalle.loc[detalle["correlacion"].idxmax()]
    en_cero = detalle.loc[detalle["desfase_min"] == 0].iloc[0]
    resumen = {"anio": anio, "desfase_del_maximo": int(mejor["desfase_min"]),
               "correlacion_maxima": float(mejor["correlacion"]),
               "correlacion_en_0": float(en_cero["correlacion"]),
               "pares_en_0": int(en_cero["pares"]),
               "segunda_mayor": float(detalle.loc[detalle["desfase_min"] != mejor["desfase_min"],
                                                  "correlacion"].max()),
               "cumple": bool(mejor["desfase_min"] == 0)}
    # Diagnostico, no criterio: el mismo calculo en +-15 horas, para que una
    # zona equivocada por mas de dos horas (hora de Chile, de Europa del Este)
    # no pase sin ser vista.
    amplio = correlacion_por_desfase(cambios["dukascopy"], cambios["histdata"],
                                     cfg.CALIDAD_DESFASE_DIAGNOSTICO_MIN)
    mejor_amplio = amplio.loc[amplio["correlacion"].idxmax()]
    resumen["desfase_del_maximo_amplio"] = int(mejor_amplio["desfase_min"])
    resumen["correlacion_maxima_amplia"] = float(mejor_amplio["correlacion"])
    return resumen, detalle


# -----------------------------------------------------------------------------
#  3 y 5. Semanas y horario de verano
# -----------------------------------------------------------------------------
def chequeo_semanas(limpia, fuente, anio, cfg):
    """Una fila por cierre de fin de semana: ultima barra del viernes y primera del domingo."""
    huecos = _huecos(limpia.index, cfg)
    finde = huecos[huecos["fin_de_semana"]]
    if finde.empty:
        return pd.DataFrame()
    viernes = pd.DatetimeIndex(finde["ultima_barra"])
    domingo = pd.DatetimeIndex(finde["fin"])
    # Lo que se espera, por la hora de Nueva York, alrededor del sabado que
    # contiene el hueco: el viernes, la ultima barra abre a las 16:59 de Nueva
    # York; el domingo, la primera abre a las 17:00.
    sabado = pd.DatetimeIndex(finde["sabado"])
    viernes_teorico = sabado - pd.Timedelta(days=1)
    domingo_teorico = sabado + pd.Timedelta(days=1)
    esperado_viernes = _hora_ny_en_utc(viernes_teorico, cfg, minutos_menos=1)
    esperado_domingo = _hora_ny_en_utc(domingo_teorico, cfg)
    tabla = pd.DataFrame({
        "fuente": fuente,
        "domingo": domingo_teorico.tz_localize(None).date,
        "ultima_viernes_utc": viernes,
        "primera_domingo_utc": domingo,
        "cierre_es_viernes": viernes.dayofweek == 4,
        "apertura_es_domingo": domingo.dayofweek == 6,
        "cierre_en_rango": _dentro(viernes, cfg.CALIDAD_CIERRE_VIERNES_UTC),
        "apertura_en_rango": _dentro(domingo, cfg.CALIDAD_APERTURA_DOMINGO_UTC),
        "cierre_vs_ny_min": ((viernes - esperado_viernes) / UN_MINUTO).astype(int),
        "apertura_vs_ny_min": ((domingo - esperado_domingo) / UN_MINUTO).astype(int),
        "ny_menos_londres_h": _desfase_ny_londres_horas(esperado_domingo, cfg),
    })
    tabla.insert(0, "anio", anio)
    tabla["fuera_de_rango"] = ~(tabla["cierre_es_viernes"] & tabla["apertura_es_domingo"]
                                & tabla["cierre_en_rango"] & tabla["apertura_en_rango"])
    return tabla[domingo_teorico.year == anio].reset_index(drop=True)


def chequeo_franjas_verano(cal, anio, cfg):
    """Franjas que no duran 6 horas: tienen que ser las de los dias de cambio del Reino Unido."""
    distintas = cal[(cal["minutos_esperados"] != 360)
                    & (cal["fecha_londres"].dt.year == anio)].copy()
    fecha = distintas["fecha_londres"]
    dia_de_cambio = ((fecha.dt.dayofweek == 6) & fecha.dt.month.isin([3, 10])
                     & (fecha.dt.day >= 25))
    largo_esperado = np.where(fecha.dt.month == 3, 300, 420)
    distintas["dia_de_cambio_uk"] = dia_de_cambio.to_numpy()
    distintas["cumple"] = dia_de_cambio.to_numpy() & (distintas["minutos_esperados"].to_numpy()
                                                      == largo_esperado)
    distintas.insert(0, "anio", anio)
    return distintas[["anio", "fecha_londres", "idx_franja", "minutos_esperados",
                      "dia_de_cambio_uk", "cumple"]].reset_index(drop=True)


# -----------------------------------------------------------------------------
#  4. Huecos y cobertura
# -----------------------------------------------------------------------------
def chequeo_huecos(limpia, fuente, anio, cfg):
    huecos = _huecos(limpia.index, cfg)
    # Un hueco cuenta en el ano en que termina: el que empieza el 31 de
    # diciembre solo se ve completo en la corrida del ano siguiente.
    huecos = huecos[~huecos["fin_de_semana"] & (huecos["fin"].dt.year == anio)]
    huecos = huecos.drop(columns=["ultima_barra", "fin_de_semana", "sabado"])
    huecos.insert(0, "fuente", fuente)
    huecos.insert(0, "anio", anio)
    return huecos.reset_index(drop=True)


def chequeo_cobertura(cal, fuente, anio, cfg):
    habiles = cal[(cal["dia_semana"] < 5) & (cal["fecha_londres"].dt.year == anio)]
    bajo = habiles["cobertura"] < cfg.COBERTURA_MIN_REFERENCIA
    sin_viernes_tarde = ~((habiles["dia_semana"] == 4) & (habiles["idx_franja"] == 3))
    fila = {"anio": anio, "fuente": fuente, "franjas_lun_vie": len(habiles),
            "bajo_cobertura": int(bajo.sum()),
            "pct_bajo_cobertura": float(bajo.mean()) if len(habiles) else np.nan,
            "pct_sin_viernes_18_24": float(bajo[sin_viernes_tarde].mean()) if sin_viernes_tarde.any() else np.nan}
    for k in range(len(cfg.LIMITES_HORAS) - 1):
        de_k = habiles["idx_franja"] == k
        fila[f"pct_franja_{k}"] = float(bajo[de_k].mean()) if de_k.any() else np.nan
    return fila


# -----------------------------------------------------------------------------
#  6. Spread
# -----------------------------------------------------------------------------
def chequeo_spread(limpia, anio, cfg):
    spread = (limpia["ask_close"] - limpia["bid_close"]) / cfg.PIP
    maximo = pd.concat([(limpia[f"ask_{x}"] - limpia[f"bid_{x}"]) / cfg.PIP for x in LADOS],
                       axis=1).max(axis=1)
    por_hora = spread.groupby(spread.index.hour).agg(
        barras="size", mediana="median",
        p95=lambda s: s.quantile(0.95), maximo="max").reset_index(names="hora_utc")
    por_hora.insert(0, "anio", anio)
    alto = maximo[maximo > cfg.CALIDAD_SPREAD_ALTO_PIPS]
    altos = pd.DataFrame({"anio": anio, "apertura_utc": alto.index, "spread_max_pips": alto.to_numpy()})
    resumen = {"anio": anio, "mediana_pips": float(spread.median()),
               "p95_pips": float(spread.quantile(0.95)),
               "hora_mediana_mas_ancha": int(por_hora.loc[por_hora["mediana"].idxmax(), "hora_utc"]),
               "barras_mas_de_10_pips": len(alto)}
    return resumen, por_hora, altos


# -----------------------------------------------------------------------------
#  7 y 8. Extremos y rupturas entre fuentes
# -----------------------------------------------------------------------------
def _clave(cal):
    return list(zip(cal["fecha_londres"], cal["idx_franja"]))


def chequeo_extremos(cals, anio, cfg):
    d = cals["dukascopy"].set_index(["fecha_londres", "idx_franja"])
    h = cals["histdata"].set_index(["fecha_londres", "idx_franja"])
    juntos = d[["H", "L", "cobertura"]].join(h[["H", "L", "cobertura"]], how="inner",
                                              lsuffix="_d", rsuffix="_h")
    fechas = juntos.index.get_level_values(0)
    juntos = juntos[(fechas.year == anio)
                    & (juntos["cobertura_d"] >= cfg.COBERTURA_MIN_REFERENCIA)
                    & (juntos["cobertura_h"] >= cfg.COBERTURA_MIN_REFERENCIA)]
    dif_h = (juntos["H_d"] - juntos["H_h"]) / cfg.PIP
    dif_l = (juntos["L_d"] - juntos["L_h"]) / cfg.PIP
    return {"anio": anio, "franjas": len(juntos),
            "H_mediana_abs": float(dif_h.abs().median()), "H_p95_abs": float(dif_h.abs().quantile(0.95)),
            "H_mediana_d_menos_h": float(dif_h.median()),
            "L_mediana_abs": float(dif_l.abs().median()), "L_p95_abs": float(dif_l.abs().quantile(0.95)),
            "L_mediana_d_menos_h": float(dif_l.median())}


def _categoria(tabla):
    cat = tabla["direccion"].map(CATEGORIAS)
    return cat.where(~tabla["ambigua"].astype(bool), "ambigua")


def chequeo_rupturas(barras, cals, anio, cfg):
    """Si hay ruptura, en que direccion y en que minuto, en las dos fuentes."""
    detectadas = {}
    for fuente in ("dukascopy", "histdata"):
        cal = cals[fuente]
        mascara = rupturas.franjas_con_referencia(cal, cfg)
        tabla = rupturas.detectar(barras[fuente], cal, cfg, mascara)
        tabla["categoria"] = _categoria(tabla)
        detectadas[fuente] = tabla.set_index(["fecha_londres", "idx_franja"])[
            ["categoria", "t_ruptura_ns"]]
    d, h = detectadas["dukascopy"], detectadas["histdata"]
    juntos = d.join(h, how="inner", lsuffix="_d", rsuffix="_h")
    juntos = juntos[juntos.index.get_level_values(0).year == anio]
    solo_d = d[~d.index.isin(h.index) & (d.index.get_level_values(0).year == anio)]
    solo_h = h[~h.index.isin(d.index) & (h.index.get_level_values(0).year == anio)]

    acuerdo = juntos["categoria_d"] == juntos["categoria_h"]
    rompen = acuerdo & juntos["categoria_d"].isin(["alcista", "bajista"])
    dif_min = (juntos.loc[rompen, "t_ruptura_ns_d"] - juntos.loc[rompen, "t_ruptura_ns_h"]).abs() / tiempo.NS_MIN
    pct = float(acuerdo.mean()) if len(juntos) else np.nan
    if pct >= cfg.CALIDAD_ACUERDO_MIN:
        veredicto = "cumple"
    elif pct >= cfg.CALIDAD_ACUERDO_ALERTA:
        veredicto = "advertencia (80%-90%)"
    else:
        veredicto = "FALLA (<80%): se detiene la etapa de datos"
    resumen = {"anio": anio, "franjas_comparables": len(juntos),
               "solo_dukascopy": len(solo_d), "solo_histdata": len(solo_h),
               "acuerdo": int(acuerdo.sum()), "pct_acuerdo": pct,
               "rompen_igual": int(rompen.sum()),
               "pct_hora_a_2_min": float((dif_min <= cfg.CALIDAD_TOLERANCIA_HORA_MIN).mean()) if rompen.any() else np.nan,
               "pct_misma_hora": float((dif_min == 0).mean()) if rompen.any() else np.nan,
               "veredicto": veredicto}
    matriz = juntos.groupby(["categoria_d", "categoria_h"]).size().rename("franjas").reset_index()
    matriz.columns = ["dukascopy", "histdata", "franjas"]
    matriz.insert(0, "anio", anio)
    return resumen, matriz


# -----------------------------------------------------------------------------
#  La corrida
# -----------------------------------------------------------------------------
def _anios(desde, hasta):
    a, b = dt.date.fromisoformat(desde), dt.date.fromisoformat(hasta)
    for anio in range(a.year, b.year + 1):
        yield anio, max(a, dt.date(anio, 1, 1)), min(b, dt.date(anio, 12, 31))


def analizar_anio(datos, anio, a_desde, cfg):
    """Todos los chequeos de un ano. `datos` puede traer un margen antes de `a_desde`."""
    inicio = pd.Timestamp(a_desde.isoformat(), tz="UTC")
    salida = {k: [] for k in ("formato", "barras", "semanas", "huecos", "cobertura", "verano_franjas",
                              "spread", "spread_hora", "spread_alto")}
    limpias, barras, cals = {}, {}, {}
    for fuente, tabla in datos.items():
        del_anio = tabla[tabla.index >= inicio]
        salida["formato"].append(pd.DataFrame([chequeo_formato(del_anio, fuente, anio, cfg)]))
        salida["barras"].append(pd.DataFrame([chequeo_barras(del_anio, fuente, anio, cfg)]))
        limpia = cargador.limpiar(tabla, fuente)
        limpias[fuente] = limpia
        barras[fuente] = _barras_bid(limpia, cfg)
        cals[fuente] = franjas.calendario(barras[fuente], cfg)
        salida["semanas"].append(chequeo_semanas(limpia, fuente, anio, cfg))
        salida["huecos"].append(chequeo_huecos(limpia, fuente, anio, cfg))
        salida["cobertura"].append(pd.DataFrame([chequeo_cobertura(cals[fuente], fuente, anio, cfg)]))
        if fuente == "dukascopy":
            resumen, por_hora, altos = chequeo_spread(limpia[limpia.index >= inicio], anio, cfg)
            salida["spread"].append(pd.DataFrame([resumen]))
            salida["spread_hora"].append(por_hora)
            salida["spread_alto"].append(altos)
    salida["verano_franjas"].append(chequeo_franjas_verano(next(iter(cals.values())), anio, cfg))

    if {"dukascopy", "histdata"} <= set(datos):
        limpias_anio = {f: t[t.index >= inicio] for f, t in limpias.items()}
        resumen, detalle = chequeo_zona(limpias_anio, anio, cfg)
        salida["zona"] = [pd.DataFrame([resumen])]
        salida["zona_detalle"] = [detalle]
        salida["extremos"] = [pd.DataFrame([chequeo_extremos(cals, anio, cfg)])]
        resumen, matriz = chequeo_rupturas(barras, cals, anio, cfg)
        salida["rupturas"] = [pd.DataFrame([resumen])]
        salida["rupturas_matriz"] = [matriz]
    return salida


def correr(desde, hasta, cfg=None, repo=None, fuentes=None):
    """
    Corre el control de calidad entre dos fechas UTC (incluidas), ano por ano.
    Devuelve un diccionario de tablas. Lee solo a traves del cargador, con
    proposito "calidad".
    """
    cfg = cfg or config
    if cfg.UMBRAL_MODO != "pips":
        raise ValueError("el control de calidad usa el umbral principal (UMBRAL_MODO 'pips')")
    if "sellado" in cargador.tramos(desde, hasta, cfg):
        raise cargador.CandadoError("el control de calidad no lee el sellado en esta etapa")
    fuentes = list(fuentes or cfg.FUENTES)
    primero = dt.date.fromisoformat(desde)
    tablas = {}
    for anio, a_desde, a_hasta in _anios(desde, hasta):
        # Margen antes del 1 de enero: la primera franja del ano necesita su
        # referencia (la ultima del ano anterior), y la primera semana y el
        # primer hueco del ano, la ultima barra del ano anterior.
        margen = a_desde if a_desde == primero else a_desde - dt.timedelta(days=cfg.CALIDAD_MARGEN_DIAS)
        datos = {}
        for fuente in fuentes:
            datos[fuente] = cargador.leer(fuente, margen.isoformat(), a_hasta.isoformat(),
                                          proposito=cargador.PROPOSITO_CALIDAD, cfg=cfg, repo=repo)
        for nombre, partes in analizar_anio(datos, anio, a_desde, cfg).items():
            tablas.setdefault(nombre, []).extend(partes)
    return {k: pd.concat([p for p in v if len(p)], ignore_index=True) if any(len(p) for p in v)
            else pd.DataFrame() for k, v in tablas.items()}


# -----------------------------------------------------------------------------
#  Informe
# -----------------------------------------------------------------------------
def _md(tabla, decimales=3):
    """Tabla markdown simple, sin dependencias extra."""
    if tabla is None or len(tabla) == 0:
        return "_(ninguna)_\n"
    # Los conteos de una columna que tiene un vacio (una fuente sin ese
    # chequeo) quedan como decimales; convert_dtypes los devuelve a enteros.
    tabla = tabla.copy()
    for c in tabla.select_dtypes("float").columns:
        valores = tabla[c].dropna()
        if len(valores) and (valores == np.round(valores)).all() and c.startswith(("inv_", "planas")):
            tabla[c] = tabla[c].astype("Int64")

    def celda(v):
        if v is pd.NA or v is pd.NaT:
            return ""
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else f"{v:.{decimales}f}"
        if isinstance(v, (bool, np.bool_)):
            return "si" if v else "no"
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d %H:%M")
        return str(v)
    columnas = list(tabla.columns)
    lineas = ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
    for fila in tabla.itertuples(index=False):
        lineas.append("| " + " | ".join(celda(v) for v in fila) + " |")
    return "\n".join(lineas) + "\n"


def informe(tablas, desde, hasta, cfg, segundos, titulo="Control de calidad de los datos"):
    t = tablas
    partes = [f"# {titulo}\n",
              f"Rango: {desde} a {hasta} (UTC). Generado por `fuentes/calidad.py` en "
              f"{segundos:.0f} s. Pre-registro, seccion 3.3. Solo usa rupturas: si hay, "
              "direccion y minuto.\n"]

    partes.append("## 0. Formato y escala\n")
    partes.append("Lo que trae cada fuente tal como se convirtio (planas incluidas): primera y "
                  "ultima barra (hora de apertura, UTC), rango de precios, decimales con que "
                  "vienen escritos, porcentaje de barras de un solo precio, rango mediano de una "
                  "barra en pips y volumen.\n")
    partes.append(_md(t.get("formato"), 5))

    partes.append("## 1. Integridad de las barras\n")
    partes.append(f"Criterio: menos de {cfg.CALIDAD_MAX_INVALIDAS:.1%} de barras invalidas "
                  "(sobre las no planas). Las velas planas de Dukascopy (minutos sin ticks, "
                  "volumen 0) pasan a faltantes; las invalidas tambien, sin corregirlas.\n")
    partes.append(_md(t.get("barras"), 5))

    partes.append("## 2. Zona horaria\n")
    partes.append(f"Correlacion de los cambios logaritmicos de 1 minuto del bid de cierre, "
                  f"Dukascopy en t contra HistData en t + desfase, desfases de "
                  f"-{cfg.CALIDAD_DESFASE_MAX_MIN} a +{cfg.CALIDAD_DESFASE_MAX_MIN} minutos. "
                  "Criterio: el maximo en 0 todos los anos. Las dos ultimas columnas son "
                  f"un diagnostico, no un criterio: el mismo calculo en +-"
                  f"{cfg.CALIDAD_DESFASE_DIAGNOSTICO_MIN // 60} horas, para ver una zona "
                  "equivocada por mas de dos horas.\n")
    partes.append(_md(t.get("zona"), 4))
    if "zona_detalle" in t and len(t["zona_detalle"]):
        cerca = t["zona_detalle"][t["zona_detalle"]["desfase_min"].abs() <= 3]
        partes.append("\nDesfases cercanos a 0:\n\n" + _md(cerca, 4))

    partes.append("## 3. Apertura del domingo y cierre del viernes\n")
    partes.append(f"Ultima barra antes del cierre de fin de semana entre "
                  f"{cfg.CALIDAD_CIERRE_VIERNES_UTC[0]}:00 y {cfg.CALIDAD_CIERRE_VIERNES_UTC[1]}:00 UTC "
                  f"un viernes; primera despues, entre {cfg.CALIDAD_APERTURA_DOMINGO_UTC[0]}:00 y "
                  f"{cfg.CALIDAD_APERTURA_DOMINGO_UTC[1]}:00 UTC un domingo. Las columnas *_vs_ny_min "
                  "son la distancia, en minutos, a las 17:00 de Nueva York (la ultima barra del "
                  "viernes abre a las 16:59).\n")
    sem = t.get("semanas")
    if sem is not None and len(sem):
        resumen = sem.groupby(["anio", "fuente"]).agg(
            semanas=("domingo", "size"), fuera_de_rango=("fuera_de_rango", "sum"),
            apertura_vs_ny_mediana=("apertura_vs_ny_min", "median"),
            cierre_vs_ny_mediana=("cierre_vs_ny_min", "median")).reset_index()
        partes.append(_md(resumen, 1))
        partes.append("\nSemanas fuera de rango:\n\n")
        partes.append(_md(sem[sem["fuera_de_rango"]].drop(columns=["fuera_de_rango"])))

    partes.append("## 4. Huecos\n")
    partes.append(f"Huecos de mas de {cfg.HUECO_CIERRE_MIN} minutos fuera del fin de semana "
                  "(sobre las barras que cuentan). `inicio` es el cierre de la ultima barra y "
                  "`fin` la apertura de la siguiente.\n")
    partes.append(_md(t.get("huecos")))
    partes.append(f"\nFranjas de lunes a viernes (fecha de Londres) bajo la cobertura minima "
                  f"({cfg.COBERTURA_MIN_REFERENCIA:.2f}). La franja [18,24) del viernes queda "
                  "siempre bajo el minimo, porque el mercado cierra a las 22:00 de Londres; "
                  "`pct_sin_viernes_18_24` la excluye.\n\n")
    partes.append(_md(t.get("cobertura"), 4))

    partes.append("## 5. Horario de verano\n")
    partes.append("Franjas que no duran 6 horas: tienen que ser las de los domingos de cambio "
                  "de hora del Reino Unido (5 horas en marzo, 7 en octubre).\n")
    partes.append(_md(t.get("verano_franjas")))
    if sem is not None and len(sem):
        cruzadas = sem[sem["ny_menos_londres_h"] != -5]
        partes.append("\nSemanas en que EE. UU. y el Reino Unido no coinciden (Nueva York - "
                      "Londres = -4 h): la apertura y el cierre tienen que seguir a Nueva York.\n\n")
        partes.append(_md(cruzadas))

    if "spread" in t and len(t["spread"]):
        partes.append("## 6. Spread (Dukascopy)\n")
        partes.append(f"Spread de cierre (ask - bid) en pips, por ano y por hora UTC. Mas de "
                      f"{cfg.CALIDAD_SPREAD_ALTO_PIPS} pips (en cualquiera de los cuatro precios): "
                      "se reporta, no se borra.\n")
        partes.append(_md(t["spread"], 3))
        partes.append("\nPor hora UTC:\n\n" + _md(t["spread_hora"], 3))
        alto = t.get("spread_alto")
        if alto is not None and len(alto):
            partes.append(f"\nBarras con mas de {cfg.CALIDAD_SPREAD_ALTO_PIPS} pips por hora UTC:\n\n")
            partes.append(_md(alto.groupby([alto["anio"], alto["apertura_utc"].dt.hour.rename("hora_utc")])
                              .size().rename("barras").reset_index()))

    if "extremos" in t:
        partes.append("## 7. Extremos por franja\n")
        partes.append("Diferencia de H y L del bid entre fuentes (Dukascopy - HistData), en pips, "
                      "en las franjas con cobertura minima en las dos.\n")
        partes.append(_md(t["extremos"], 3))

    if "rupturas" in t:
        partes.append("## 8. Rupturas coincidentes\n")
        partes.append(f"Detector del motor (`motor.rupturas`) sobre el bid de las dos fuentes, "
                      f"umbral {cfg.UMBRAL_PIPS:g} pip, en las franjas con referencia valida en "
                      f"las dos. Acuerdo = misma categoria (sin ruptura, alcista, bajista o "
                      f"ambigua). Criterio: al menos {cfg.CALIDAD_ACUERDO_MIN:.0%}; entre "
                      f"{cfg.CALIDAD_ACUERDO_ALERTA:.0%} y {cfg.CALIDAD_ACUERDO_MIN:.0%}, advertencia; "
                      f"menos de {cfg.CALIDAD_ACUERDO_ALERTA:.0%}, se detiene la etapa de datos. "
                      f"`pct_hora_a_2_min`: entre las que rompen igual, diferencia de hora de "
                      f"{cfg.CALIDAD_TOLERANCIA_HORA_MIN} minutos o menos.\n")
        partes.append(_md(t["rupturas"], 4))
        partes.append("\nMatriz de categorias:\n\n" + _md(t["rupturas_matriz"]))
    return "\n".join(partes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Control de calidad (pre-registro 3.3)")
    parser.add_argument("--desde", required=True)
    parser.add_argument("--hasta", required=True)
    parser.add_argument("--fuentes", nargs="+", choices=config.FUENTES)
    parser.add_argument("--salida", default=os.path.join("resultados", "calidad.md"))
    parser.add_argument("--titulo", default="Control de calidad de los datos")
    args = parser.parse_args(argv)
    comienzo = time.perf_counter()
    tablas = correr(args.desde, args.hasta, fuentes=args.fuentes)
    texto = informe(tablas, args.desde, args.hasta, config, time.perf_counter() - comienzo,
                    args.titulo)
    base = os.path.splitext(args.salida)[0]
    os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as f:
        f.write(texto)
    for nombre, tabla in tablas.items():
        if len(tabla):
            tabla.to_csv(f"{base}_{nombre}.csv", index=False)
    print(texto)


if __name__ == "__main__":
    main()
