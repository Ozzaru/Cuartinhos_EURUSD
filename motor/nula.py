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

H4 (anuncios macro) se mide aparte, en `correr_h4`, por inferencia de
aleatorizacion. Ver ahi la explicacion y las referencias.
"""
import numpy as np
import pandas as pd

from . import eventos as mod_eventos
from . import inferencia as mod_inferencia
from . import moderadores as mod_moderadores
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


def preparar_candidatos(barras, cal, cfg, sigma=None, noticias=None):
    """
    Precalcula, para cada minuto, su grupo de emparejamiento y su retorno a
    cada horizonte con direccion +1.

    Esto es lo que permite que despues cada repeticion sea solo sortear
    indices: el trabajo pesado se hace una sola vez.

    Si se pasa el calendario de anuncios, tambien se marca que minutos estan
    "con anuncio", que es lo que necesita la nula de H4.
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

    fecha = cal["fecha_londres"].to_numpy()[pos]
    return {
        "pos_franja": pos,
        "idx_franja": cal["idx_franja"].to_numpy()[pos],
        "dia_semana": cal["dia_semana"].to_numpy()[pos],
        "grupo_vol": grupo_vol[pos],
        "sirve": sirve_minuto,
        "retornos": {h: columnas[f"ret_{h}"] for h in cfg.HORIZONTES},
        "grupo_vol_por_franja": grupo_vol,
        "dia_codigo": pd.factorize(pd.DatetimeIndex(fecha))[0],
        "tratado": mod_moderadores.marcar_noticia(barras.cierre_ns, pos, cal, noticias, cfg),
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


def correr_h4(barras, cal, tabla_eventos, cfg, semilla, repeticiones=None,
              candidatos=None, sigma=None, noticias=None):
    """
    H4 por INFERENCIA DE ALEATORIZACION.

    La pregunta de H4 es si el efecto del evento es distinto cuando hubo un
    anuncio macro cerca. El camino obvio -- meter una variable "noticia" en la
    regresion y mirar su coeficiente -- no sirve aqui: los eventos con anuncio
    son poquisimos y caben en muy pocos dias, y con tan pocos grupos tratados el
    error estandar agrupado sale demasiado chico y rechaza de mas. Lo medimos en
    el punto C: 25% de falsos positivos en vez de 5%.

    El camino que si sirve (MacKinnon y Webb, 2020):

      1. El estadistico observado es la DIFERENCIA entre submuestras,
         estudentizada:
             t_dif = (media_con_anuncio - media_sin_anuncio) / error agrupado
         Va estudentizada a proposito: con pocos grupos tratados y grupos
         heterogeneos, la inferencia por aleatorizacion sobre el coeficiente
         crudo se porta mal, mientras que sobre el estadistico t se mantiene
         cerca del nivel nominal, a cambio de algo de potencia.
      2. La nula sortea pseudo-eventos con la MISMA estructura que los reales:
         misma cantidad, mismo indice de franja, mismo dia de semana y mismo
         decil de volatilidad. Y la condicion que hace todo el trabajo:
             los pseudo-eventos "con anuncio" salen SOLO de minutos que estan
             dentro de una ventana de anuncio, y los "sin anuncio" SOLO de
             minutos que estan fuera.
      3. Como la nula ya incorpora que los minutos de anuncio se mueven mas, lo
         que sobrevive a la comparacion es el efecto propio del evento. Es una
         diferencia en diferencias hecha por sorteo.
      4. p-valor de Phipson y Smyth, a una cola "mayor", porque H4 predice mas
         continuacion cuando hay anuncio.

    Se informan las dos versiones del estadistico, estudentizada y sin
    estudentizar, para tener evidencia propia sobre cual se comporta mejor.
    """
    repeticiones = cfg.NULA_REPETICIONES if repeticiones is None else repeticiones
    if candidatos is None:
        candidatos = preparar_candidatos(barras, cal, cfg, sigma=sigma, noticias=noticias)

    rng = np.random.default_rng(semilla)
    grupo_por_franja = candidatos["grupo_vol_por_franja"]
    pos_cand = candidatos["pos_franja"]
    tratado_cand = candidatos["tratado"]
    dia_cand = candidatos["dia_codigo"]

    filas = []
    for h in cfg.HORIZONTES:
        columna = f"ret_{h}"
        ret_cand = candidatos["retornos"][h]
        disponible = candidatos["sirve"] & np.isfinite(ret_cand)
        # Dos conjuntos de candidatos separados: los minutos de anuncio y el
        # resto. Un pseudo-evento tratado solo puede salir del primero.
        pools = {
            1: _armar_pools(candidatos, disponible & (tratado_cand == 1.0)),
            0: _armar_pools(candidatos, disponible & (tratado_cand == 0.0)),
        }

        for tipo in ("sostenida", "reingreso"):
            del_tipo = tabla_eventos[tabla_eventos["tipo"] == tipo]
            usables = del_tipo[np.isfinite(del_tipo[columna].to_numpy(float))
                               & np.isfinite(del_tipo["noticia"].to_numpy(float))]
            filas.append(_una_prueba_h4(rng, usables, columna, tipo, h, ret_cand,
                                        pools, grupo_por_franja, pos_cand, dia_cand,
                                        repeticiones))
    return pd.DataFrame(filas)


def _una_prueba_h4(rng, usables, columna, tipo, h, ret_cand, pools,
                   grupo_por_franja, pos_cand, dia_cand, repeticiones):
    """Una celda de H4: un tipo de evento y un horizonte."""
    vacia = {"tipo": tipo, "horizonte": h, "cola": "mayor", "n_con": 0, "n_sin": 0,
             "dias_tratados": 0, "diferencia": np.nan, "error": np.nan,
             "t_observado": np.nan, "p_estudentizado": np.nan,
             "p_sin_estudentizar": np.nan, "repeticiones": 0, "n_descartados": 0}
    if len(usables) == 0:
        return vacia

    tratado = usables["noticia"].to_numpy(float)
    franja_evento = usables["pos_franja"].to_numpy(int)
    claves = _clave(usables["idx_franja"].to_numpy(int),
                    usables["dia_semana"].to_numpy(int),
                    grupo_por_franja[franja_evento])

    # Cada evento se sortea dentro de su propio conjunto: tratados con tratados.
    indices = np.full((repeticiones, len(usables)), -1, dtype=np.int64)
    usable = np.zeros(len(usables), dtype=bool)
    for marca in (1.0, 0.0):
        cuales = np.flatnonzero(tratado == marca)
        if len(cuales) == 0:
            continue
        parcial, ok = _sortear(rng, pools[int(marca)], claves[cuales],
                               franja_evento[cuales], pos_cand, repeticiones)
        indices[:, cuales] = parcial
        usable[cuales] = ok

    if not usable.any() or len(np.unique(tratado[usable])) < 2:
        vacia["n_descartados"] = int((~usable).sum())
        return vacia

    direccion = usables["direccion"].to_numpy(float)[usable]
    y = usables[columna].to_numpy(float)[usable]
    tratado_ok = tratado[usable]
    dia_real = pd.factorize(pd.DatetimeIndex(usables["fecha_londres"]))[0][usable]

    diferencia, error, t_obs = mod_inferencia.diferencia_agrupada(y, tratado_ok, dia_real)

    # La nula: el mismo calculo, con los pseudo-eventos de cada repeticion.
    t_nulas = np.full(repeticiones, np.nan)
    dif_nulas = np.full(repeticiones, np.nan)
    for r in range(repeticiones):
        sorteo = indices[r, usable]
        y_nulo = ret_cand[sorteo] * direccion
        dif_nulas[r], _, t_nulas[r] = mod_inferencia.diferencia_agrupada(
            y_nulo, tratado_ok, dia_cand[sorteo])

    dias_tratados = int(pd.Series(dia_real[tratado_ok == 1.0]).nunique())
    return {
        "tipo": tipo, "horizonte": h, "cola": "mayor",
        "n_con": int((tratado_ok == 1.0).sum()), "n_sin": int((tratado_ok == 0.0).sum()),
        "dias_tratados": dias_tratados,
        "diferencia": diferencia, "error": error, "t_observado": t_obs,
        "p_estudentizado": _p_una_cola(t_obs, t_nulas[np.isfinite(t_nulas)], "mayor"),
        "p_sin_estudentizar": _p_una_cola(diferencia, dif_nulas[np.isfinite(dif_nulas)],
                                          "mayor"),
        "repeticiones": int(np.isfinite(t_nulas).sum()),
        "n_descartados": int((~usable).sum()),
    }


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
    nulas = np.asarray(nulas, dtype=float)
    if len(nulas) == 0 or not np.isfinite(observado):
        return np.nan
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
    nulas = np.asarray(nulas, dtype=float)
    if len(nulas) == 0 or not np.isfinite(observado):
        return np.nan
    centro = np.mean(nulas)
    extremas = np.sum(np.abs(nulas - centro) >= abs(observado - centro))
    return float((1 + extremas) / (1 + len(nulas)))
