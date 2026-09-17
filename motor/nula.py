# -*- coding: utf-8 -*-
"""
NULA — hipotesis nula emparejada.

La pregunta que responde: el retorno promedio despues de los eventos, ise
parece al de cualquier otro minuto comparable, o es distinto?

"Comparable" significa tres cosas a la vez: el mismo indice de franja, el mismo
dia de semana y el mismo decil de volatilidad. Sin emparejar, un efecto podria
salir solo porque los eventos se concentran, por ejemplo, en la franja de la
tarde de los miercoles movidos.

Como funciona, en simple:
  1. Se arma el conjunto de minutos CANDIDATOS: todos los minutos de franjas que
     podrian haber generado eventos y que tienen resultado definido a ese
     horizonte.
  2. A cada evento real se le sortea un minuto candidato de su mismo grupo,
     excluyendo su propia franja.
  3. Al minuto sorteado se le asigna la direccion del evento real y se calcula
     el mismo retorno normalizado.
  4. Se promedia sobre todos los eventos. Eso es UNA repeticion.
  5. Se repite NULA_REPETICIONES veces y se mira donde cae el promedio real.

El decil de volatilidad se calcula aqui y no en moderadores.py porque necesita
la distribucion de toda la muestra: en el instante t ese numero no existe. Sirve
solo para emparejar, nunca como variable explicativa.

p-valor segun Phipson y Smyth (2010): se suma 1 arriba y 1 abajo. El p-valor
nunca puede dar 0, porque el promedio observado tambien es una de las
ordenaciones posibles. Con R repeticiones el minimo alcanzable es 1 / (R + 1).
"""
import numpy as np
import pandas as pd

from . import eventos as mod_eventos
from . import resultados


def deciles_de_volatilidad(sigma, utilizable, n_grupos):
    """
    Parte las franjas utilizables en grupos de igual tamano segun sigma_ref.

    Los cortes salen de las franjas CANDIDATAS y no de los eventos: asi ningun
    grupo queda sin minutos de donde sortear. Las franjas no utilizables quedan
    con grupo -1.
    """
    grupo = np.full(len(sigma), -1, dtype=int)
    validas = utilizable & np.isfinite(sigma)
    if not validas.any():
        return grupo
    valores = sigma[validas]
    cortes = np.quantile(valores, np.linspace(0, 1, n_grupos + 1)[1:-1])
    grupo[validas] = np.searchsorted(cortes, valores, side="right")
    return grupo


def preparar_candidatos(barras, cal, cfg, sigma=None):
    """
    Precalcula, para cada minuto, su grupo de emparejamiento y su retorno a
    cada horizonte con direccion +1.

    Esto es lo que permite que despues cada repeticion sea solo sortear
    indices: el trabajo pesado se hace una sola vez.
    """
    if sigma is None:
        sigma = resultados.sigma_por_franja(barras, cal, cfg)

    utilizable = mod_eventos.franjas_utilizables(cal, sigma, cfg)
    grupo_vol = deciles_de_volatilidad(sigma, utilizable, cfg.NULA_DECILES_VOL)

    # A que franja pertenece cada barra.
    pos = np.searchsorted(cal["inicio_ns"].to_numpy(), barras.apertura_ns, side="right") - 1
    sirve_minuto = utilizable[pos]

    columnas = resultados.calcular_retornos(
        barras, cal, cfg,
        t_ns=barras.cierre_ns,
        direccion=np.ones(len(barras)),
        sigma=sigma[pos],
        pos_franja=pos)

    return {
        "pos_franja": pos,
        "idx_franja": cal["idx_franja"].to_numpy()[pos],
        "dia_semana": cal["dia_semana"].to_numpy()[pos],
        "grupo_vol": grupo_vol[pos],
        "sirve": sirve_minuto,
        "retornos": {h: columnas[f"ret_{h}"] for h in cfg.HORIZONTES},
        "grupo_vol_por_franja": grupo_vol,
    }


def _clave(idx_franja, dia_semana, grupo_vol):
    """Un entero unico por combinacion de franja, dia y decil."""
    return (np.asarray(idx_franja) * 1000 + np.asarray(dia_semana) * 100
            + np.asarray(grupo_vol))


def _sortear(rng, pools, claves_evento, franja_evento, pos_franja_candidato,
             repeticiones, intentos_max=50):
    """
    Sortea, para cada evento y cada repeticion, un minuto candidato de su grupo.

    Se descarta el sorteo que cae en la MISMA franja del evento real: si no, el
    evento se estaria comparando consigo mismo. Como cada grupo tiene miles de
    minutos y una franja aporta unos 360, esos choques son raros y se resuelven
    volviendo a sortear.

    Devuelve (indices, utilizable). `utilizable` marca los eventos para los que
    el grupo, sin su propia franja, quedo vacio.
    """
    n = len(claves_evento)
    salida = np.full((repeticiones, n), -1, dtype=np.int64)
    usable = np.zeros(n, dtype=bool)

    for clave in np.unique(claves_evento):
        cuales = np.flatnonzero(claves_evento == clave)
        pool = pools.get(int(clave))
        if pool is None or len(pool) == 0:
            continue

        propia = franja_evento[cuales][None, :]
        sorteo = pool[rng.integers(0, len(pool), size=(repeticiones, len(cuales)))]
        choca = pos_franja_candidato[sorteo] == propia
        intentos = 0
        while choca.any() and intentos < intentos_max:
            sorteo[choca] = pool[rng.integers(0, len(pool), size=int(choca.sum()))]
            choca = pos_franja_candidato[sorteo] == propia
            intentos += 1

        # Si despues de tantos intentos un evento sigue chocando, es que su
        # grupo es practicamente su propia franja. Ese evento queda fuera de la
        # comparacion, en vez de emparejarse consigo mismo.
        limpio = ~choca.any(axis=0)
        salida[:, cuales[limpio]] = sorteo[:, limpio]
        usable[cuales[limpio]] = True
    return salida, usable


def correr(barras, cal, tabla_eventos, cfg, semilla, repeticiones=None,
           candidatos=None, sigma=None):
    """
    Corre la nula emparejada para cada tipo de evento y cada horizonte.

    Devuelve (tabla, distribuciones):
      tabla          una fila por (tipo, horizonte) con el promedio observado,
                     el promedio nulo, el p-valor de una cola y el de dos colas;
      distribuciones diccionario (tipo, horizonte) -> array de promedios nulos,
                     que los experimentos usan para los histogramas.
    """
    repeticiones = cfg.NULA_REPETICIONES if repeticiones is None else repeticiones
    if candidatos is None:
        candidatos = preparar_candidatos(barras, cal, cfg, sigma=sigma)

    colas = {t: c for t, _, _, c in cfg.FAMILIA_PRINCIPAL}
    filas, distribuciones = [], {}
    rng = np.random.default_rng(semilla)

    grupo_por_franja = candidatos["grupo_vol_por_franja"]
    pos_cand = candidatos["pos_franja"]

    # El bucle va por horizonte y despues por tipo: los grupos de minutos
    # candidatos dependen solo del horizonte, asi que se arman una sola vez.
    for h in cfg.HORIZONTES:
        columna = f"ret_{h}"
        ret_cand = candidatos["retornos"][h]
        disponible = candidatos["sirve"] & np.isfinite(ret_cand)
        pools = _armar_pools(candidatos, disponible) if disponible.any() else {}

        for tipo in cfg.TIPOS_EVENTO:
            del_tipo = tabla_eventos[tabla_eventos["tipo"] == tipo]
            usables = del_tipo[np.isfinite(del_tipo[columna].to_numpy(float))]
            if len(usables) == 0 or not disponible.any():
                filas.append(_fila_vacia(tipo, h, colas.get(tipo, "dos")))
                continue

            franja_evento = usables["pos_franja"].to_numpy(int)
            claves = _clave(usables["idx_franja"].to_numpy(int),
                            usables["dia_semana"].to_numpy(int),
                            grupo_por_franja[franja_evento])

            indices, usable = _sortear(rng, pools, claves, franja_evento, pos_cand,
                                       repeticiones)
            if not usable.any():
                filas.append(_fila_vacia(tipo, h, colas.get(tipo, "dos")))
                continue

            direccion = usables["direccion"].to_numpy(float)[usable]
            observado = float(np.mean(usables[columna].to_numpy(float)[usable]))
            nulas = np.mean(ret_cand[indices[:, usable]] * direccion[None, :], axis=1)

            cola = colas.get(tipo, "dos")
            filas.append({
                "tipo": tipo, "horizonte": h, "cola": cola,
                "n_eventos": int(usable.sum()),
                "n_descartados": int((~usable).sum()),
                "media_observada": observado,
                "media_nula": float(np.mean(nulas)),
                "sd_nula": float(np.std(nulas, ddof=1)) if len(nulas) > 1 else np.nan,
                "p_una_cola": _p_una_cola(observado, nulas, cola),
                "p_dos_colas": _p_dos_colas(observado, nulas),
                "repeticiones": repeticiones,
            })
            distribuciones[(tipo, h)] = nulas

    return pd.DataFrame(filas), distribuciones


def _armar_pools(candidatos, disponible):
    """Diccionario clave de grupo -> posiciones de los minutos candidatos."""
    posiciones = np.flatnonzero(disponible)
    claves = _clave(candidatos["idx_franja"][posiciones],
                    candidatos["dia_semana"][posiciones],
                    candidatos["grupo_vol"][posiciones])
    orden = np.argsort(claves, kind="stable")
    claves_ord, posiciones_ord = claves[orden], posiciones[orden]
    cortes = np.flatnonzero(np.diff(claves_ord)) + 1
    trozos = np.split(posiciones_ord, cortes)
    etiquetas = claves_ord[np.concatenate([[0], cortes])] if len(claves_ord) else []
    return {int(k): v for k, v in zip(etiquetas, trozos)}


def _fila_vacia(tipo, h, cola):
    return {"tipo": tipo, "horizonte": h, "cola": cola, "n_eventos": 0,
            "n_descartados": 0, "media_observada": np.nan, "media_nula": np.nan,
            "sd_nula": np.nan, "p_una_cola": np.nan, "p_dos_colas": np.nan,
            "repeticiones": 0}


def _p_una_cola(observado, nulas, cola):
    """
    p-valor de una cola, con la correccion de Phipson y Smyth (2010).

    Para H1 (sostenida) la hipotesis dice "mayor que cero", asi que cuentan las
    nulas que igualan o superan lo observado. Para H2 (reingreso) dice "menor
    que cero" y se cuenta al reves.
    """
    if cola == "mayor":
        extremas = np.sum(nulas >= observado)
    elif cola == "menor":
        extremas = np.sum(nulas <= observado)
    else:
        return np.nan
    return float((1 + extremas) / (1 + len(nulas)))


def _p_dos_colas(observado, nulas):
    """
    p-valor de dos colas: cuantas nulas se alejan de su propio centro tanto o
    mas que lo observado. Se centra en el promedio de las nulas porque esa
    distribucion no tiene por que estar exactamente en cero.
    """
    centro = np.mean(nulas)
    extremas = np.sum(np.abs(nulas - centro) >= abs(observado - centro))
    return float((1 + extremas) / (1 + len(nulas)))
