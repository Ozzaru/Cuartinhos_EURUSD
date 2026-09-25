# -*- coding: utf-8 -*-
"""
CONTROL POSITIVO — cuanta potencia tiene el motor.

Definiciones, acordadas en el punto E antes de ver la curva:

  - Efecto: +delta en las sostenidas y -delta en los reingresos, en la
    direccion de la ruptura, IGUAL en los cuatro horizontes.
  - Potencia por celda: proporcion de mercados en que esa prueba rechaza con
    el signo que predice su hipotesis.
  - Potencia por familia: proporcion de mercados con AL MENOS un rechazo
    correcto entre las pruebas de la familia principal.
  - La lectura principal es Holm sobre la nula emparejada con ALFA_PRINCIPAL.
    Las cuatro combinaciones (Holm y Romano-Wolf, con cada alfa de
    ALFAS_POTENCIA) se reportan solo como descripcion: Romano-Wolf es otra
    prueba (t de la regresion contra cero, dos colas, sin la nula).

La curva usa el DISENO D, decidido por el grupo al cerrar la primera parte del
punto E (MacKinlay, 1997, seccion de potencia): el mercado queda limpio y el
efecto se suma al retorno normalizado de cada evento. Asi el delta que llega a
cada celda es exactamente el nominal, en la misma unidad en que estan escritas
las hipotesis. Por cada mercado, lo caro se hace UNA vez (eventos, candidatos,
sorteo de la nula y remuestreos de Romano-Wolf) y cada delta solo recalcula lo
observado:

  - la distribucion nula no depende de los retornos de los eventos (sale de
    los minutos sorteados), asi que no cambia;
  - en Romano-Wolf, sumar una constante a una celda mueve igual la estimacion
    de la muestra y la de cada remuestreo, y no toca los errores: los
    estadisticos centrados de los remuestreos no cambian.

Con eso la curva se evalua sobre TAMANOS_EFECTO y sobre una grilla fina
(GRILLA_POTENCIA) al mismo costo.

El CONTROL B es descriptivo y no decide nada: inyecta el efecto en los PRECIOS
(simulacion/inyeccion.py) y repite inyectar -> detectar hasta que los eventos
que reciben el efecto son los que el motor detecta. Tres escenarios (los dos
tipos a la vez, solo sostenidas, solo reingresos) miden cuanto de un efecto de
precio llega a cada celda y cuanto se contagia a la celda no inyectada.

La corrida larga tambien fija ALFA_PRINCIPAL: la regla (`regla_alfa_principal`,
escrita antes de correr) usa la tasa por prueba en delta = 0 del bloque de
ANIOS_REGLA_ALFA anos, que reemplaza la medicion del punto D.

Etapas, en el orden acordado:

    python -m experimentos.control_positivo --piso        piso sin la nula y traduccion a pips
    python -m experimentos.control_positivo --piloto      tiempo y memoria de D y de B
    python -m experimentos.control_positivo               la curva (D) y el control B
    python -m experimentos.control_positivo --solo-reporte
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                              # noqa: E402
import motor                                               # noqa: E402
from experimentos import recursos                          # noqa: E402
from experimentos.control_negativo import (                # noqa: E402
    CARPETA, _en_paralelo, _tabla, error_monte_carlo, intervalo_binomial,
    tasa_por_prueba_ic)
from motor import inferencia, nula, resultados             # noqa: E402
from simulacion import inyeccion, mercado                  # noqa: E402

# Bloques de semillas. El piso reusa a proposito las del control negativo
# (SEMILLA + k): sus primeros 50 mercados son los mismos del punto D, asi que
# el piso tiene que reproducir aquella tabla.
DESPLAZAMIENTO_CURVA = 20000
DESPLAZAMIENTO_CONTROL_B = 40000
DESPLAZAMIENTO_PILOTO = 90000

COMBINACIONES = [("holm", "p_holm"), ("romano_wolf", "p_romano_wolf")]


def _tipos(cfg):
    """Los tipos de la familia principal, en el orden de config."""
    return list(dict.fromkeys(t for t, _, _, _ in cfg.FAMILIA_PRINCIPAL))


# =============================================================================
#  Piso y unidades
# =============================================================================
def medias_por_celda(eventos, cfg):
    """
    Promedio del retorno normalizado por tipo y horizonte, sin la nula.

    Es la misma cantidad que `media_observada` del punto D, con una diferencia
    menor declarada: aqui entran TODOS los eventos con retorno definido, y alla
    solo los que tenian con quien emparejarse en la nula (7 de 5.383 en un
    mercado de 3 anos).
    """
    filas = []
    for tipo in _tipos(cfg):
        del_tipo = eventos[eventos["tipo"] == tipo]
        for h in cfg.HORIZONTES:
            ret = del_tipo[f"ret_{h}"].to_numpy(float)
            ret = ret[np.isfinite(ret)]
            filas.append({"tipo": tipo, "horizonte": str(h), "n_eventos": len(ret),
                          "media": float(ret.mean()) if len(ret) else np.nan})
    return pd.DataFrame(filas)


def factores_pips(eventos, cfg):
    """
    Cuantos pips vale una unidad de retorno normalizado, evento por evento:

        pips por unidad = sigma_ref * raiz(h) * precio_evento / PIP

    Una unidad es un movimiento de sigma_ref * raiz(h) en logaritmo del precio,
    o sea precio * sigma_ref * raiz(h) en precio. Solo sostenidas y reingresos
    con retorno definido a ese horizonte; para "fin_franja", h es el largo real
    del horizonte de cada evento.
    """
    base = eventos[eventos["tipo"].isin(_tipos(cfg))]
    sigma = base["sigma_ref"].to_numpy(float)
    precio = base["precio_evento"].to_numpy(float)
    partes = []
    for h in cfg.HORIZONTES:
        minutos = (base["h_fin_franja"].to_numpy(float) if h == "fin_franja"
                   else np.full(len(base), float(h)))
        definido = np.isfinite(base[f"ret_{h}"].to_numpy(float))
        partes.append(pd.DataFrame({
            "tipo": base["tipo"].to_numpy()[definido],
            "idx_franja": base["idx_franja"].to_numpy()[definido],
            "horizonte": str(h),
            "factor": (sigma * np.sqrt(minutos) * precio / cfg.PIP)[definido],
        }))
    return pd.concat(partes, ignore_index=True)


def corrida_piso(semilla, anios, cambios, con_factores):
    """Un mercado sin ningun patron: medias por celda y, si se pide, factores."""
    cfg = config.copia(**cambios)
    datos, noticias = mercado.generar(anios, semilla, cfg)
    _, _, eventos = motor.preparar(datos, cfg, noticias=noticias)
    medias = medias_por_celda(eventos, cfg)
    medias["mercado"] = semilla
    medias["vol"] = cfg.VOL_ANUAL_SIMULACION
    factores = None
    if con_factores:
        factores = factores_pips(eventos, cfg)
        factores["mercado"] = semilla
        factores["vol"] = cfg.VOL_ANUAL_SIMULACION
    return medias, factores


def _tarea_piso(argumentos):
    return corrida_piso(*argumentos)


def resumen_piso(medias):
    """Promedio entre mercados por tipo y horizonte, con su error de Monte Carlo."""
    tabla = medias.groupby(["tipo", "horizonte"])["media"].agg(["mean", "std", "count"])
    tabla["error_mc"] = tabla["std"] / np.sqrt(tabla["count"])
    return tabla.rename(columns={"mean": "piso", "count": "mercados"}).reset_index()


def resumen_factores(factores):
    """Mediana y cuartiles del factor pips / unidad por volatilidad, horizonte y franja."""
    def cuartiles(serie):
        q = np.quantile(serie.to_numpy(float), [0.25, 0.5, 0.75])
        return pd.Series({"eventos": len(serie), "q25": q[0], "mediana": q[1], "q75": q[2]})

    por_franja = factores.groupby(["vol", "horizonte", "idx_franja"])["factor"].apply(
        cuartiles).unstack().reset_index()
    todas = factores.groupby(["vol", "horizonte"])["factor"].apply(
        cuartiles).unstack().reset_index()
    todas["idx_franja"] = "todas"
    salida = pd.concat([por_franja, todas], ignore_index=True)
    salida["idx_franja"] = salida["idx_franja"].astype(str)
    salida["eventos"] = salida["eventos"].astype(int)
    return salida[["vol", "horizonte", "idx_franja", "eventos", "q25", "mediana", "q75"]]


def costos_en_unidades(factores_resumidos, costos):
    """
    Un costo de ida y vuelta, en pips, expresado en unidades de retorno
    normalizado: costo / factor. Con la mediana del factor sale el valor
    tipico; con los cuartiles, el rango (el cuartil ALTO del factor da el costo
    BAJO en unidades, y viceversa).
    """
    todas = factores_resumidos[factores_resumidos["idx_franja"] == "todas"]
    filas = []
    for _, fila in todas.iterrows():
        for costo in costos:
            filas.append({"vol": fila["vol"], "horizonte": fila["horizonte"],
                          "costo_pips": costo,
                          "unidades_mediana": costo / fila["mediana"],
                          "unidades_rango": f"[{costo / fila['q75']:.3f}, "
                                            f"{costo / fila['q25']:.3f}]"})
    return pd.DataFrame(filas)


# =============================================================================
#  La curva (diseno D)
# =============================================================================
def rejilla_de_deltas(cfg):
    """
    Todos los delta en que se evalua la curva: TAMANOS_EFECTO mas la grilla
    fina, sin repetidos. Se redondean para que el 0,05 de una lista y el de la
    otra sean el mismo numero.
    """
    return sorted({round(float(d), 6) for d in list(cfg.TAMANOS_EFECTO)
                   + list(cfg.GRILLA_POTENCIA)})


def corrida_curva(semilla, anios, cambios, repeticiones):
    """
    Un mercado limpio, todos los tamanos de efecto.

    Lo caro se hace una sola vez: eventos, candidatos, sorteo de la nula y
    remuestreos de Romano-Wolf. Todos los delta comparten esos sorteos
    (numeros aleatorios comunes: las diferencias entre delta no se ensucian con
    ruido de sorteo).
    """
    cfg = config.copia(**cambios)
    datos, noticias = mercado.generar(anios, semilla, cfg)
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
    del datos
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    materiales = nula.sortear_nula(barras, cal, eventos, cfg, semilla,
                                   repeticiones=repeticiones, candidatos=candidatos)
    del candidatos, barras, cal
    celdas, dias = inferencia.construir_celdas(eventos, cfg)
    beta, error, w = inferencia.romano_wolf_remuestreos(
        celdas, cfg.FAMILIA_PRINCIPAL, dias, repeticiones, semilla)
    return curva_de_un_mercado(materiales, beta, error, w, cfg, semilla, anios)


def _tarea_curva(argumentos):
    return corrida_curva(*argumentos)


def curva_de_un_mercado(materiales, beta_rw, error_rw, w, cfg, semilla, anios):
    """
    Una fila por delta, tipo de la familia principal y horizonte (tambien el
    descriptivo de 120).

    Para cada delta: a cada evento se le suma signo * delta en su retorno
    normalizado (+ en sostenidas, - en reingresos), se recalculan lo observado
    y su p contra la MISMA distribucion nula, Holm sobre las pruebas
    confirmatorias, y Romano-Wolf con los t observados movidos y los mismos
    remuestreos.
    """
    signo = inyeccion.signos(cfg)
    familia = cfg.FAMILIA_PRINCIPAL
    s_familia = np.array([signo[t] for t, _, _, _ in familia])
    posicion = {(t, str(h)): i for i, (t, h, _, _) in enumerate(familia)}
    tamanos = {round(float(d), 6) for d in cfg.TAMANOS_EFECTO}

    filas = []
    for delta in rejilla_de_deltas(cfg):
        tabla, _ = nula.resumir_nula(materiales, cfg,
                                     {t: s * delta for t, s in signo.items()})
        p = inferencia.p_brutos_desde_nula(tabla, cfg)
        p_holm = inferencia.holm([p.get((t, h, c), np.nan) for t, h, c, _ in familia])
        estimacion = beta_rw + s_familia * delta
        t_rw = inferencia.t_de(estimacion, error_rw)
        p_rw = inferencia.romano_wolf_stepdown(t_rw, w)
        for nulo in tabla[tabla["tipo"].isin(list(signo))].itertuples(index=False):
            i = posicion.get((nulo.tipo, str(nulo.horizonte)))
            filas.append({
                "mercado": semilla, "anios": anios, "delta": delta,
                "en_tamanos": delta in tamanos,
                "tipo": nulo.tipo, "horizonte": str(nulo.horizonte),
                "confirmatoria": i is not None,
                "n_eventos": nulo.n_eventos,
                "media_observada": nulo.media_observada,
                "media_nula": nulo.media_nula,
                "t_observado": nulo.t_observado,
                "p_bruto": nulo.p_una_cola,
                "estimacion": estimacion[i] if i is not None else np.nan,
                "t_regresion": t_rw[i] if i is not None else np.nan,
                "p_holm": p_holm[i] if i is not None else np.nan,
                "p_romano_wolf": p_rw[i] if i is not None else np.nan,
            })
    return pd.DataFrame(filas)


# =============================================================================
#  Control B: inyeccion de precio autoconsistente (descriptivo)
# =============================================================================
def _firma(eventos, tipos):
    """Lo que identifica a los eventos que reciben efecto: instante, tipo y direccion."""
    sub = eventos[eventos["tipo"].isin(tipos)]
    return sub[["t_evento_ns", "tipo", "direccion"]].reset_index(drop=True)


def inyeccion_autoconsistente(limpio, noticias, eventos_limpios, delta, cfg, tipos=None):
    """
    Inyecta en precios hasta que los eventos que reciben el efecto son
    exactamente los que el motor detecta en el mercado inyectado.

    `tipos` son los tipos que reciben el efecto (por defecto, los dos de la
    familia principal); los demas eventos se detectan pero no se inyectan.

    Se empieza por los eventos del mercado limpio; en cada vuelta se inyecta
    sobre el mercado LIMPIO con los eventos detectados en la vuelta anterior.
    Converge porque el motor es causal: la deriva de un evento solo puede
    cambiar lo que se detecta despues de el.

    La amplitud de cada deriva usa el sigma_ref del evento en la vuelta
    anterior; al converger, los eventos son los mismos pero su sigma_ref puede
    diferir en la cuarta cifra (la deriva entra en los dias siguientes de
    sigma_ref). Queda declarado; no se itera sobre sigma_ref.

    Devuelve (barras, cal, eventos, iteraciones, convergio).
    """
    tipos = _tipos(cfg) if tipos is None else list(tipos)
    usados = eventos_limpios
    for iteracion in range(1, cfg.ITERACIONES_MAX_CONTROL_B + 1):
        inyectado = inyeccion.inyectar(limpio, usados[usados["tipo"].isin(tipos)], delta, cfg)
        barras, cal, detectados = motor.preparar(inyectado, cfg, noticias=noticias)
        del inyectado
        if _firma(detectados, tipos).equals(_firma(usados, tipos)):
            return barras, cal, detectados, iteracion, True
        usados = detectados
    return barras, cal, detectados, iteracion, False


def filas_control_b(eventos, eventos_limpios, barras_limpias, cal_limpio, delta, cfg,
                    inyectados=None):
    """
    Por tipo y horizonte, cuanto del efecto de precio llego al retorno. Se
    mide en los dos tipos aunque solo uno se haya inyectado (`inyectados`): en
    el otro, lo que llega es contagio por la superposicion.

      realizado_por_evento  con los MISMOS eventos (los del mercado inyectado),
                            retorno en el mercado inyectado menos retorno en el
                            limpio, en la direccion de la hipotesis. Incluye la
                            superposicion con el otro tipo y el corte de la
                            deriva al fin de la franja.
      realizado_celda       lo que se movio el promedio de la celda contra el
                            mercado limpio, con sus propios eventos (incluye
                            ademas el cambio de eventos).
    """
    signo = inyeccion.signos(cfg)
    filas = []
    for tipo in _tipos(cfg):
        s = signo[tipo]
        del_tipo = eventos[eventos["tipo"] == tipo]
        limpios = eventos_limpios[eventos_limpios["tipo"] == tipo]
        en_limpio = resultados.calcular_retornos(
            barras_limpias, cal_limpio, cfg,
            t_ns=del_tipo["t_evento_ns"].to_numpy(np.int64),
            direccion=del_tipo["direccion"].to_numpy(float),
            sigma=del_tipo["sigma_ref"].to_numpy(float),
            pos_franja=del_tipo["pos_franja"].to_numpy(int))
        coinciden = np.isin(del_tipo["t_evento_ns"].to_numpy(np.int64),
                            limpios["t_evento_ns"].to_numpy(np.int64))
        for h in cfg.HORIZONTES:
            con = del_tipo[f"ret_{h}"].to_numpy(float)
            sin = en_limpio[f"ret_{h}"]
            ambos = np.isfinite(con) & np.isfinite(sin)
            por_evento = s * (con[ambos] - sin[ambos])
            ret_limpio = limpios[f"ret_{h}"].to_numpy(float)
            filas.append({
                "tipo": tipo, "horizonte": str(h),
                "inyectado": inyectados is None or tipo in inyectados,
                "confirmatoria": h in cfg.HORIZONTES_CONFIRMATORIOS,
                "n_eventos": int(ambos.sum()),
                "realizado_por_evento": float(por_evento.mean()) if ambos.any() else np.nan,
                "realizado_celda": s * (np.nanmean(con) - np.nanmean(ret_limpio)),
                "frac_coinciden": float(coinciden.mean()) if len(coinciden) else np.nan,
                "cambio_eventos": len(del_tipo) / len(limpios) - 1 if len(limpios) else np.nan,
                "cambio_sigma_ref": float(del_tipo["sigma_ref"].mean()
                                          / limpios["sigma_ref"].mean() - 1),
            })
    return filas


def corrida_control_b(semilla, anios, cambios):
    """
    Un mercado del control B: cada escenario de ESCENARIOS_CONTROL_B y cada
    delta de DELTAS_CONTROL_B, autoconsistente, sobre el MISMO mercado limpio.
    """
    cfg = config.copia(**cambios)
    limpio, noticias = mercado.generar(anios, semilla, cfg)
    barras_l, cal_l, eventos_l = motor.preparar(limpio, cfg, noticias=noticias)
    filas = []
    for escenario, tipos in cfg.ESCENARIOS_CONTROL_B.items():
        for delta in cfg.DELTAS_CONTROL_B:
            comienzo = time.perf_counter()
            _, _, eventos, iteraciones, convergio = inyeccion_autoconsistente(
                limpio, noticias, eventos_l, delta, cfg, tipos=tipos)
            segundos = time.perf_counter() - comienzo
            for fila in filas_control_b(eventos, eventos_l, barras_l, cal_l, delta, cfg,
                                        inyectados=tipos):
                filas.append({"mercado": semilla, "anios": anios, "escenario": escenario,
                              "delta": delta, "iteraciones": iteraciones,
                              "convergio": convergio, "segundos_delta": segundos, **fila})
    return pd.DataFrame(filas)


def _tarea_control_b(argumentos):
    return corrida_control_b(*argumentos)


def resumen_control_b(control):
    """
    Promedio entre mercados, con su error de Monte Carlo, y la razon realizado /
    nominal, por escenario. En la celda no inyectada la razon es el contagio.
    """
    if "escenario" not in control.columns:           # piloto anterior a los escenarios
        control = control.assign(escenario="ambos", inyectado=True)
    agrupado = control.groupby(["escenario", "anios", "delta", "tipo", "horizonte",
                                "inyectado"], sort=False)
    salida = agrupado[["realizado_por_evento", "realizado_celda", "frac_coinciden",
                       "cambio_eventos", "cambio_sigma_ref"]].mean()
    salida["error_mc_por_evento"] = (agrupado["realizado_por_evento"].std()
                                     / np.sqrt(agrupado.size()))
    salida["mercados"] = agrupado.size()
    salida = salida.reset_index()
    salida["razon_por_evento"] = salida["realizado_por_evento"] / salida["delta"]
    salida["razon_celda"] = salida["realizado_celda"] / salida["delta"]
    return salida


def potencia_aproximada_b(resumen, celda, columna, anios):
    """
    APROXIMACION: la potencia de cada celda de B es la de D, en la misma celda y
    duracion, evaluada en el delta REALIZADO por evento de B (interpolando en la
    grilla fina).

    Supone que lo que decide la deteccion es cuanto se mueve el promedio de la
    celda, no como se reparte entre eventos. Si el realizado es negativo (el
    contagio va contra la hipotesis de la celda) la curva de D no lo cubre y
    queda NaN: la potencia es, a lo sumo, el tamano.
    """
    filas = []
    confirmatorias = resumen[resumen["horizonte"].isin(
        celda["horizonte"].unique())]
    for _, fila in confirmatorias.iterrows():
        bloque = celda[(celda["anios"] == anios) & (celda["tipo"] == fila["tipo"])
                       & (celda["horizonte"] == fila["horizonte"])].sort_values("delta")
        realizado = fila["realizado_por_evento"]
        potencia = (float(np.interp(realizado, bloque["delta"], bloque[columna]))
                    if len(bloque) and realizado >= 0 else np.nan)
        filas.append({"escenario": fila["escenario"], "delta": fila["delta"],
                      "tipo": fila["tipo"], "horizonte": fila["horizonte"],
                      "inyectado": fila["inyectado"], "realizado": realizado,
                      "potencia_aprox": potencia})
    return pd.DataFrame(filas)


# =============================================================================
#  Resumenes de la curva
# =============================================================================
def marcar_rechazos(curva, cfg):
    """
    Agrega una columna booleana por combinacion (correccion, alfa): la prueba
    rechaza Y lo hace con el signo que predice su hipotesis.

    El signo se lee de la estimacion que usa cada prueba: para Holm, el efecto
    observado menos el nulo; para Romano-Wolf, el promedio de la regresion.
    Solo las pruebas confirmatorias tienen p corregido; las demas quedan False.
    """
    signo = curva["tipo"].map(inyeccion.signos(cfg)).to_numpy(float)
    estimacion = {
        "holm": (curva["media_observada"] - curva["media_nula"]).to_numpy(float),
        "romano_wolf": curva["estimacion"].to_numpy(float),
    }
    salida = curva.copy()
    for nombre, columna in COMBINACIONES:
        p = curva[columna].to_numpy(float)
        bien = np.sign(estimacion[nombre]) == signo
        for alfa in cfg.ALFAS_POTENCIA:
            salida[f"rechaza_{nombre}_{alfa}"] = np.isfinite(p) & (p <= alfa) & bien
    return salida


def columnas_de_rechazo(cfg):
    return [f"rechaza_{nombre}_{alfa}" for nombre, _ in COMBINACIONES
            for alfa in cfg.ALFAS_POTENCIA]


def columna_principal(cfg):
    """La lectura principal: Holm con ALFA_PRINCIPAL."""
    return f"rechaza_holm_{cfg.ALFA_PRINCIPAL}"


def potencia_por_celda(marcada, cfg):
    """Proporcion de mercados que rechazan, por duracion, delta y prueba."""
    confirmatorias = marcada[marcada["confirmatoria"]]
    tabla = confirmatorias.groupby(["anios", "delta", "tipo", "horizonte"])[
        columnas_de_rechazo(cfg)].mean()
    tabla["mercados"] = confirmatorias.groupby(["anios", "delta", "tipo", "horizonte"]).size()
    return tabla.reset_index()


def rechazos_familia_por_mercado(marcada, cfg):
    """Por mercado y delta: si hubo AL MENOS un rechazo correcto en la familia principal."""
    confirmatorias = marcada[marcada["confirmatoria"]]
    return confirmatorias.groupby(["anios", "delta", "mercado"])[
        columnas_de_rechazo(cfg)].any().reset_index()


def potencia_por_familia(marcada, cfg):
    """Proporcion de mercados con AL MENOS un rechazo correcto en la familia principal."""
    por_mercado = rechazos_familia_por_mercado(marcada, cfg)
    agrupado = por_mercado.groupby(["anios", "delta"])
    tabla = agrupado[columnas_de_rechazo(cfg)].mean()
    tabla["mercados"] = agrupado.size()
    return tabla.reset_index()


def _cruces(deltas, potencias, objetivo):
    """
    Efecto minimo detectable de cada fila de `potencias` (filas = curvas,
    columnas = `deltas` ordenados): primer delta en que la curva llega a
    `objetivo`, interpolando en linea recta con el punto anterior. NaN si no
    llega.
    """
    potencias = np.atleast_2d(np.asarray(potencias, dtype=float))
    llega = potencias >= objetivo
    alguna = llega.any(axis=1)
    i = np.argmax(llega, axis=1)
    salida = np.full(len(potencias), np.nan)
    filas = np.flatnonzero(alguna)
    en_cero = filas[i[filas] == 0]
    salida[en_cero] = deltas[0]
    medio = filas[i[filas] > 0]
    d1, d0 = deltas[i[medio]], deltas[i[medio] - 1]
    p1 = potencias[medio, i[medio]]
    p0 = potencias[medio, i[medio] - 1]
    salida[medio] = d0 + (objetivo - p0) * (d1 - d0) / (p1 - p0)
    return salida


def efecto_minimo_detectable(deltas, potencias, objetivo):
    """
    El delta con el que la potencia llega a `objetivo`, interpolando en linea
    recta entre los dos puntos de la curva que lo rodean. NaN si la curva no
    llega.
    """
    deltas = np.asarray(deltas, dtype=float)
    potencias = np.asarray(potencias, dtype=float)
    orden = np.argsort(deltas)
    return float(_cruces(deltas[orden], potencias[orden], objetivo)[0])


def efecto_minimo_con_ic(rechazos, objetivo, remuestreos, semilla):
    """
    Efecto minimo detectable con su intervalo al 95%, remuestreando MERCADOS.

    `rechazos` es una tabla mercado x delta de ceros y unos. En cada remuestreo
    se sortean mercados con reposicion, se promedia la curva y se busca donde
    cruza el objetivo. Un remuestreo cuya curva no llega cuenta como "mas alla
    de la grilla": si son mas del 2,5%, el borde alto queda infinito.

    Devuelve (efecto, bajo, alto).
    """
    deltas = np.asarray(rechazos.columns, dtype=float)
    orden = np.argsort(deltas)
    deltas = deltas[orden]
    matriz = rechazos.to_numpy(float)[:, orden]
    efecto = _cruces(deltas, matriz.mean(axis=0), objetivo)[0]
    rng = np.random.default_rng(semilla)
    sorteo = rng.integers(0, len(matriz), size=(remuestreos, len(matriz)))
    curvas = matriz[sorteo].mean(axis=1)
    # Percentiles por posicion en la lista ordenada (sin interpolar, que con
    # infinitos no tiene sentido), tomando el lado conservador.
    cruces = np.sort(np.nan_to_num(_cruces(deltas, curvas, objetivo), nan=np.inf))
    ultimo = len(cruces) - 1
    bajo = cruces[int(np.floor(0.025 * ultimo))]
    alto = cruces[int(np.ceil(0.975 * ultimo))]
    return float(efecto), float(bajo), float(alto)


def delta_realizado(curva, cfg):
    """
    Cuanto se movio de verdad el retorno de cada celda, en la direccion de la
    hipotesis: promedio entre mercados de (media con delta - media sin delta).
    En el diseno D es delta por construccion; se reporta igual como control.
    """
    signo = curva["tipo"].map(inyeccion.signos(cfg))
    base = curva[curva["delta"] == 0].set_index(
        ["anios", "mercado", "tipo", "horizonte"])["media_observada"]
    llave = pd.MultiIndex.from_frame(curva[["anios", "mercado", "tipo", "horizonte"]])
    tabla = curva.assign(
        realizado=signo * (curva["media_observada"].to_numpy(float)
                           - base.reindex(llave).to_numpy(float)))
    return tabla.groupby(["anios", "delta", "tipo", "horizonte"])["realizado"] \
        .mean().reset_index()


def sesgo_del_estimador(curva, cfg):
    """
    Sesgo, por celda, del efecto que va a reportar el informe: lo observado
    menos lo nulo, en la direccion de la hipotesis, menos el delta verdadero.

    En el diseno D ese sesgo no depende de delta (lo observado se mueve
    exactamente delta y lo nulo no se mueve), asi que se da uno por celda,
    medido en delta = 0, y `variacion_max` dice cuanto se aparta en el peor
    delta y mercado. Se agrega el sesgo de la media cruda (la que prueba
    Romano-Wolf), que no descuenta la nula.
    """
    signo = curva["tipo"].map(inyeccion.signos(cfg))
    tabla = curva.assign(
        sesgo=signo * (curva["media_observada"] - curva["media_nula"]) - curva["delta"],
        sesgo_media_cruda=signo * curva["media_observada"] - curva["delta"])
    base = tabla[tabla["delta"] == 0].set_index(
        ["anios", "mercado", "tipo", "horizonte"])["sesgo"]
    llave = pd.MultiIndex.from_frame(tabla[["anios", "mercado", "tipo", "horizonte"]])
    tabla["aparte"] = np.abs(tabla["sesgo"].to_numpy(float)
                             - base.reindex(llave).to_numpy(float))
    cero = tabla[tabla["delta"] == 0].groupby(["anios", "tipo", "horizonte"])
    salida = cero[["sesgo", "sesgo_media_cruda"]].mean()
    salida["error_mc"] = cero["sesgo"].std() / np.sqrt(cero.size())
    salida["error_mc_media_cruda"] = cero["sesgo_media_cruda"].std() / np.sqrt(cero.size())
    salida["mercados"] = cero.size()
    salida["variacion_max"] = tabla.groupby(["anios", "tipo", "horizonte"])["aparte"].max()
    return salida.reset_index()


def tamano_en_cero(curva, cfg, remuestreos, semilla, alfa=None):
    """
    En delta = 0 no hay efecto: la tasa de rechazo es otra medicion del tamano
    de la familia principal (Holm, ALFA_PRINCIPAL), con mercados distintos de
    los del punto D. Por duracion; se informa aparte y no se mezcla con la del
    punto D.

    Por familia: mercados con al menos un rechazo (sin exigir el signo, como en
    el punto D), con Wilson. Por prueba: p bruto y p de Holm <= alfa, con el
    intervalo que remuestrea mercados.
    """
    alfa = cfg.ALFA_PRINCIPAL if alfa is None else alfa
    filas = []
    for anios, bloque in curva[(curva["delta"] == 0) & curva["confirmatoria"]].groupby("anios"):
        por_mercado = bloque.groupby("mercado")["p_holm"].min() <= alfa
        bajo, alto = intervalo_binomial(int(por_mercado.sum()), len(por_mercado))
        fila = {"anios": anios, "alfa": alfa, "mercados": len(por_mercado),
                "familia": float(por_mercado.mean()), "familia_ic95": f"[{bajo:.3f}, {alto:.3f}]"}
        for columna, nombre in (("p_bruto", "por_prueba_bruto"), ("p_holm", "por_prueba_holm")):
            tasa, bajo, alto = tasa_por_prueba_ic(bloque, alfa, remuestreos, semilla,
                                                  columna=columna)
            fila[nombre] = tasa
            fila[f"{nombre}_ic95"] = f"[{bajo:.3f}, {alto:.3f}]"
        filas.append(fila)
    return pd.DataFrame(filas)


def potencia_contra_costo(celda, columna, costos, deltas_lectura):
    """
    APROXIMACION: potencia de un test NETO de un costo c, leida de la curva
    bruta como potencia_bruta(delta - c).

    Vale porque el error estandar casi no depende de delta; no es una
    medicion. `celda` trae la potencia por celda en la grilla fina; `costos`,
    el costo en unidades normalizadas por horizonte. Si delta - c < 0 el efecto
    neto no es positivo y no hay potencia que leer (NaN).
    """
    filas = []
    for (anios, tipo, h), bloque in celda.groupby(["anios", "tipo", "horizonte"]):
        bloque = bloque.sort_values("delta")
        for _, c in costos[costos["horizonte"] == str(h)].iterrows():
            fila = {"anios": anios, "tipo": tipo, "horizonte": h,
                    "costo_pips": c["costo_pips"], "costo_unidades": c["unidades_mediana"]}
            for delta in deltas_lectura:
                neto = delta - c["unidades_mediana"]
                fila[delta] = (float(np.interp(neto, bloque["delta"], bloque[columna]))
                               if neto >= 0 else np.nan)
            filas.append(fila)
    return pd.DataFrame(filas)


def regla_alfa_principal(ic_alfa, ic_estricto, alfa, alfa_estricto):
    """
    La regla que fija ALFA_PRINCIPAL en la segunda parte del punto E, escrita
    ANTES de la corrida larga. Reemplaza a la del punto D (ver la bitacora).

    Objetivo explicito: que el tamano real POR PRUEBA de la familia principal
    no pase de `alfa` (5%). `ic_alfa` e `ic_estricto` son (tasa, bajo, alto):
    la tasa por prueba con p bruto <= alfa y <= alfa_estricto, con su IC95
    remuestreando mercados.

      - IC con alfa entero SOBRE alfa (exceso demostrado) y borde inferior del
        IC con alfa_estricto que no pasa de alfa   -> alfa_estricto.
      - IC con alfa que CONTIENE a alfa            -> alfa.
      - IC con alfa entero sobre alfa y borde inferior con alfa_estricto que
        tambien pasa de alfa                        -> el control FALLA.
      - IC con alfa entero BAJO alfa: el grupo no lo listo. El objetivo (que el
        tamano no pase de alfa) se cumple, asi que se queda alfa; queda
        declarado como interpretacion, escrita antes de correr.

    Devuelve (alfa elegido o None si el control falla, motivo).
    """
    _, bajo, alto = ic_alfa
    _, bajo_estricto, _ = ic_estricto
    if bajo > alfa:
        if bajo_estricto <= alfa:
            return alfa_estricto, (f"con {alfa} el IC queda entero sobre {alfa} (exceso "
                                   f"demostrado) y con {alfa_estricto} su borde inferior "
                                   f"no pasa de {alfa}")
        return None, (f"con {alfa} el IC queda entero sobre {alfa} y con {alfa_estricto} "
                      f"su borde inferior TAMBIEN pasa de {alfa}: el control falla")
    if alto >= alfa:
        return alfa, f"con {alfa} el IC contiene a {alfa}: no hay exceso demostrado"
    return alfa, (f"con {alfa} el IC queda entero BAJO {alfa}: el objetivo se cumple "
                  f"(caso no listado por el grupo; interpretacion declarada)")


def aplicar_regla_alfa(curva, cfg):
    """
    La regla sobre el punto delta = 0 de la duracion ANIOS_REGLA_ALFA: las
    pruebas confirmatorias de la familia principal, p bruto de la nula.
    """
    base = curva[(curva["delta"] == 0) & curva["confirmatoria"]
                 & (curva["anios"] == cfg.ANIOS_REGLA_ALFA)]
    ic = {alfa: tasa_por_prueba_ic(base, alfa, cfg.REMUESTREOS_IC_MERCADOS, cfg.SEMILLA)
          for alfa in (cfg.ALFA, cfg.ALFA_ESTRICTO)}
    decision, motivo = regla_alfa_principal(ic[cfg.ALFA], ic[cfg.ALFA_ESTRICTO],
                                            cfg.ALFA, cfg.ALFA_ESTRICTO)
    return {"ic": ic, "decision": decision, "motivo": motivo,
            "mercados": int(base["mercado"].nunique()), "pruebas": len(base)}


def _markdown_regla(regla, cfg):
    filas = [{"alfa": alfa, "tasa_por_prueba": tasa, "ic95_bajo": bajo, "ic95_alto": alto}
             for alfa, (tasa, bajo, alto) in regla["ic"].items()]
    resultado = (f"**ALFA_PRINCIPAL = {regla['decision']}**" if regla["decision"] is not None
                 else "**EL CONTROL FALLA**")
    return "\n".join([
        "## 0. Regla de ALFA_PRINCIPAL (escrita antes de la corrida)\n",
        f"Tasa por prueba de la familia principal (p bruto de la nula <= alfa) en "
        f"delta = 0, bloque de {cfg.ANIOS_REGLA_ALFA} anos: {regla['mercados']} mercados, "
        f"{regla['pruebas']} pruebas. IC95 remuestreando mercados "
        f"({cfg.REMUESTREOS_IC_MERCADOS} remuestreos). Objetivo: que el tamano real por "
        f"prueba no pase de {cfg.ALFA}. Reemplaza la medicion del punto D (mismo test, mas "
        f"mercados, y la duracion que confirma).\n",
        _tabla(pd.DataFrame(filas).round(4)),
        f"\n{resultado}: {regla['motivo']}.\n"])


# =============================================================================
#  Etapa 1: piso y unidades
# =============================================================================
def etapa_piso(procesos=None):
    cfg = config.copia()
    os.makedirs(CARPETA, exist_ok=True)
    print(recursos.describir())
    comienzo = time.perf_counter()

    # La memoria por proceso se mide con el primer mercado, no se supone.
    print("Midiendo un mercado del piso...")
    primero, pico, segundos = recursos.medir_pico(
        lambda: corrida_piso(cfg.SEMILLA, cfg.ANIOS_PISO, {}, True))
    procesos = procesos or recursos.procesos_que_caben(pico)
    print(f"  {segundos:.1f} s y ~{pico:.2f} GB por mercado -> {procesos} procesos")

    trabajos = [(cfg.SEMILLA + k, cfg.ANIOS_PISO, {}, k < cfg.MERCADOS_UNIDADES)
                for k in range(1, cfg.MERCADOS_PISO)]
    for vol in cfg.VOLS_TRADUCCION:
        if vol == cfg.VOL_ANUAL_SIMULACION:
            continue                     # ya salen de los mercados del piso
        trabajos += [(cfg.SEMILLA + k, cfg.ANIOS_PISO, {"VOL_ANUAL_SIMULACION": vol}, True)
                     for k in range(cfg.MERCADOS_UNIDADES)]
    print(f"Piso: {cfg.MERCADOS_PISO} mercados de {cfg.ANIOS_PISO} anos; unidades: "
          f"{cfg.MERCADOS_UNIDADES} mercados por volatilidad")
    resultados = [primero] + _en_paralelo(_tarea_piso, trabajos, procesos)

    medias = pd.concat([r[0] for r in resultados], ignore_index=True)
    factores = pd.concat([r[1] for r in resultados if r[1] is not None], ignore_index=True)
    minutos = (time.perf_counter() - comienzo) / 60

    piso = medias[medias["vol"] == cfg.VOL_ANUAL_SIMULACION]
    piso.to_csv(os.path.join(CARPETA, "control_positivo_piso.csv"), index=False,
                float_format="%.6g")
    resumidos = resumen_factores(factores)
    resumidos.to_csv(os.path.join(CARPETA, "control_positivo_factores.csv"), index=False,
                     float_format="%.6g")
    texto = _markdown_piso(piso, resumidos, cfg, minutos, procesos)
    with open(os.path.join(CARPETA, "control_positivo_piso.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


def _markdown_piso(piso, resumidos, cfg, minutos, procesos):
    partes = ["# Control positivo, etapa 1: el piso y las unidades\n",
              f"- {cfg.MERCADOS_PISO} mercados sin ningun patron de {cfg.ANIOS_PISO} anos, "
              f"volatilidad anual {cfg.VOL_ANUAL_SIMULACION}. Sin la nula.",
              f"- {minutos:.1f} minutos con {procesos} procesos. Equipo: {recursos.describir()}.\n",
              "## 1. El piso: sesgo propio de los eventos\n",
              "Promedio entre mercados del retorno normalizado de los eventos, en mercados "
              "donde por construccion no hay nada que encontrar. Es la cantidad de la tabla "
              "del punto D (`media_observada`), con una diferencia menor: aqui entran todos "
              "los eventos con retorno, alla solo los que tenian pareja en la nula.\n"]
    tabla = resumen_piso(piso)
    partes.append(_tabla(tabla[["tipo", "horizonte", "piso", "error_mc", "mercados"]].round(5)))

    comparables = piso[piso["mercado"] < cfg.SEMILLA + cfg.MERCADOS_CONTROL_NEGATIVO]
    if len(comparables):
        partes += ["\nLos primeros mercados son los MISMOS del punto D (mismas semillas); "
                   "sobre ellos solos:\n",
                   _tabla(resumen_piso(comparables)[["tipo", "horizonte", "piso",
                                                     "error_mc", "mercados"]].round(5))]

    partes += ["\n## 2. Cuantos pips vale una unidad de retorno normalizado\n",
               "**Es un orden de magnitud.** El retorno normalizado es "
               "direccion * dlnP / (sigma_ref * raiz(h)), asi que una unidad vale "
               "precio * sigma_ref * raiz(h) en precio, y sigma_ref sale aqui de "
               "VOL_ANUAL_SIMULACION, que es un parametro de simulacion. La traduccion "
               "definitiva se hara evento por evento con el sigma_ref de los datos reales.\n",
               f"Mediana y cuartiles sobre los eventos (sostenidas y reingresos), "
               f"{cfg.MERCADOS_UNIDADES} mercados por volatilidad. Franjas en hora de "
               f"Londres: 0 = [0,6), 1 = [6,12), 2 = [12,18), 3 = [18,24).\n"]
    partes.append(_tabla(resumidos.round(2)))

    costos = costos_en_unidades(resumidos, cfg.COSTOS_IDA_VUELTA_PIPS)
    partes += ["\n## 3. Costos de ida y vuelta en unidades normalizadas\n",
               "costo / factor, con la mediana del factor (todas las franjas) y, entre "
               "corchetes, el rango que dan sus cuartiles.\n",
               _tabla(costos.round(4))]
    maximo = max(cfg.TAMANOS_EFECTO)
    encima = costos[costos["unidades_mediana"] > maximo]
    if len(encima):
        partes.append(f"\n**Aviso**: {len(encima)} combinaciones de costo, horizonte y "
                      f"volatilidad quedan por encima del mayor tamano de efecto de la "
                      f"curva ({maximo}). La curva mide deteccion del efecto BRUTO; para "
                      f"leerla contra un costo c se usa la aproximacion de la etapa 3.")
    return "\n".join(partes) + "\n"


# =============================================================================
#  Etapa 2: piloto
# =============================================================================
def _en_proceso_nuevo(tarea, argumentos):
    """
    Corre una tarea en un proceso recien creado y espera el resultado.

    Asi la memoria que mide el piloto es la de un proceso entero, interprete
    incluido, y no la que queda despues de que el proceso principal ya reservo
    memoria para los mercados anteriores.
    """
    with ProcessPoolExecutor(max_workers=1) as pozo:
        return pozo.submit(tarea, argumentos).result()


def _medir(tarea, argumentos, texto):
    print(texto, flush=True)
    resultado, pico, segundos = recursos.medir_pico(
        lambda: _en_proceso_nuevo(tarea, argumentos))
    print(f"  {segundos:.1f} s, ~{pico:.2f} GB de pico", flush=True)
    return resultado, pico, segundos


def piloto(repeticiones):
    """
    Mide tiempo y memoria de MERCADOS_PILOTO mercados de cada duracion del
    diseno D y otros tantos del control B, de a uno y cada uno en un proceso
    nuevo, y estima la corrida completa con los procesos que caben en el 70%
    de la memoria disponible.
    """
    cfg = config.copia()
    print(recursos.describir())
    medidas, curvas, controles = [], [], []
    for anios in cfg.ANIOS_POTENCIA:
        for k in range(cfg.MERCADOS_PILOTO):
            semilla = cfg.SEMILLA + DESPLAZAMIENTO_PILOTO + 1000 * anios + k
            curva, pico, segundos = _medir(
                _tarea_curva, (semilla, anios, {}, repeticiones),
                f"Piloto D: mercado {k + 1} de {cfg.MERCADOS_PILOTO}, {anios} anos, "
                f"{len(rejilla_de_deltas(cfg))} delta...")
            medidas.append({"etapa": "D", "anios": anios, "mercado": semilla,
                            "segundos": segundos, "pico_gb": pico, "escenarios_b": 0})
            curvas.append(curva)
    for k in range(cfg.MERCADOS_PILOTO):
        semilla = cfg.SEMILLA + DESPLAZAMIENTO_PILOTO + 1000 * cfg.ANIOS_CONTROL_B + 500 + k
        control, pico, segundos = _medir(
            _tarea_control_b, (semilla, cfg.ANIOS_CONTROL_B, {}),
            f"Piloto B: mercado {k + 1} de {cfg.MERCADOS_PILOTO}, "
            f"{cfg.ANIOS_CONTROL_B} anos, delta {cfg.DELTAS_CONTROL_B}...")
        medidas.append({"etapa": "B", "anios": cfg.ANIOS_CONTROL_B, "mercado": semilla,
                        "segundos": segundos, "pico_gb": pico,
                        "escenarios_b": len(cfg.ESCENARIOS_CONTROL_B)})
        controles.append(control)

    medidas = pd.DataFrame(medidas)
    curva = pd.concat(curvas, ignore_index=True)
    control = pd.concat(controles, ignore_index=True)
    os.makedirs(CARPETA, exist_ok=True)
    medidas.to_csv(os.path.join(CARPETA, "control_positivo_piloto.csv"), index=False)
    curva.to_csv(os.path.join(CARPETA, "control_positivo_piloto_curva.csv"), index=False,
                 float_format="%.6g")
    control.to_csv(os.path.join(CARPETA, "control_positivo_piloto_b.csv"), index=False,
                   float_format="%.6g")
    texto = _markdown_piloto(medidas, curva, control, cfg, repeticiones)
    with open(os.path.join(CARPETA, "control_positivo_piloto.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


def bloques_de_la_corrida(cfg):
    """(etapa, anios, mercados) de la corrida larga, en el orden en que se corren."""
    bloques = [("D", anios, cfg.MERCADOS_POR_DURACION[anios]) for anios in cfg.ANIOS_POTENCIA]
    bloques.append(("B", cfg.ANIOS_CONTROL_B, cfg.MERCADOS_CONTROL_B))
    return bloques


def factores_de_tiempo(medidas, cfg):
    """
    Cuanto mas larga es la corrida de B que la del piloto: el piloto de la
    primera version midio B con un solo escenario ("ambos"); cada escenario
    repite la iteracion completa, asi que el tiempo se escala por escenarios.
    """
    b = medidas[medidas["etapa"] == "B"]
    medidos = (b["escenarios_b"].max() if "escenarios_b" in b.columns
               and b["escenarios_b"].notna().any() else 1)
    return {"B": len(cfg.ESCENARIOS_CONTROL_B) / max(float(medidos), 1.0)}


def estimar_corrida(medidas, bloques, factores=None, fraccion=0.70):
    """
    Tiempo estimado de la corrida larga, por bloque. Cada bloque corre con los
    procesos que caben segun el PEOR pico de memoria medido en el, y los
    bloques van uno detras de otro.

    Si una duracion no se midio en el piloto, segundos y pico se interpolan en
    linea recta entre las duraciones medidas de la misma etapa (`origen`
    "interpolado"); fuera del rango medido no se extrapola. `factores` (etapa ->
    numero) escala el tiempo medido.
    """
    factores = factores or {}
    if "etapa" not in medidas.columns:
        medidas = medidas.assign(etapa="D")
    medias = medidas.groupby(["etapa", "anios"]).agg(
        segundos=("segundos", "mean"), pico_gb=("pico_gb", "max")).reset_index()
    filas = []
    for etapa, anios, cuantos in bloques:
        propias = medias[medias["etapa"] == etapa].sort_values("anios")
        if anios in set(propias["anios"]):
            fila = propias[propias["anios"] == anios].iloc[0]
            segundos, pico, origen = float(fila["segundos"]), float(fila["pico_gb"]), "medido"
        elif len(propias) >= 2 and propias["anios"].min() < anios < propias["anios"].max():
            segundos = float(np.interp(anios, propias["anios"], propias["segundos"]))
            pico = float(np.interp(anios, propias["anios"], propias["pico_gb"]))
            origen = "interpolado"
        else:
            raise ValueError(f"el piloto no cubre {etapa} de {anios} anos y no se extrapola")
        segundos *= factores.get(etapa, 1.0)
        procesos = recursos.procesos_que_caben(pico, fraccion=fraccion)
        filas.append({"etapa": etapa, "anios": anios, "origen": origen,
                      "segundos_por_mercado": segundos, "pico_gb": pico,
                      "procesos": procesos, "mercados": cuantos,
                      "minutos_estimados": cuantos * segundos / procesos / 60})
    return pd.DataFrame(filas)


def recortar_por_tiempo(estimacion, limite):
    """
    Si el total estimado pasa de `limite` minutos, recorta los mercados del
    bloque D de la duracion MAS LARGA hasta que entre (lo pedido por el grupo).
    Devuelve (estimacion, nota); nota es None si no hizo falta recortar.
    """
    total = float(estimacion["minutos_estimados"].sum())
    if total <= limite:
        return estimacion, None
    salida = estimacion.copy()
    d = salida[salida["etapa"] == "D"]
    i = d["anios"].idxmax()
    fila = salida.loc[i]
    resto = total - fila["minutos_estimados"]
    cabe = int(max(0.0, limite - resto) * 60 * fila["procesos"] // fila["segundos_por_mercado"])
    salida.loc[i, "mercados"] = cabe
    salida.loc[i, "minutos_estimados"] = cabe * fila["segundos_por_mercado"] / fila["procesos"] / 60
    return salida, (f"La estimacion daba {total:.0f} minutos, mas que el tope de {limite}: "
                    f"el bloque D de {int(fila['anios'])} anos baja de {int(fila['mercados'])} a "
                    f"{cabe} mercados.")


def _markdown_piloto(medidas, curva, control, cfg, repeticiones):
    estimacion = estimar_corrida(medidas, bloques_de_la_corrida(cfg),
                                 factores_de_tiempo(medidas, cfg))
    total = float(estimacion["minutos_estimados"].sum())
    realizado = delta_realizado(curva, cfg)
    desvio = float(np.abs(realizado["realizado"] - realizado["delta"]).max())
    sesgo = sesgo_del_estimador(curva, cfg)
    marcada = marcar_rechazos(curva, cfg)
    familia = potencia_por_familia(marcada, cfg)
    en_tamanos = familia[familia["delta"].isin(curva.loc[curva["en_tamanos"], "delta"])]
    unicos = control.drop_duplicates([c for c in ("mercado", "escenario", "delta")
                                      if c in control.columns])

    partes = ["# Control positivo, etapa 2: piloto (diseno D y control B)\n",
              f"- D: {cfg.MERCADOS_PILOTO} mercados por duracion, cada uno con "
              f"{len(rejilla_de_deltas(cfg))} delta (TAMANOS_EFECTO mas la grilla fina).",
              f"- B: {cfg.MERCADOS_PILOTO} mercados de {cfg.ANIOS_CONTROL_B} anos, delta "
              f"{cfg.DELTAS_CONTROL_B}, sin la nula.",
              f"- Repeticiones de la nula y de Romano-Wolf: {repeticiones}.",
              f"- Equipo: {recursos.describir()}.\n",
              "## Medido\n", _tabla(medidas.round(2)),
              "\n## Estimacion de la corrida completa\n",
              f"Mercados por bloque segun config; procesos limitados al 70% de la memoria "
              f"disponible AHORA:\n",
              _tabla(estimacion.round(2)),
              f"\n**Total estimado: {total:.0f} minutos.**\n",
              "## Primera mirada (solo para revisar que la maquina funciona)\n",
              "Con tan pocos mercados esto NO es la curva.\n",
              f"- Delta realizado en D: el mayor desvio contra el nominal, en todas las "
              f"celdas y delta, es {desvio:.2e} (tiene que ser cero salvo redondeo).",
              f"- Sesgo del estimador: el mayor cambio entre delta, en todas las celdas, es "
              f"{float(sesgo['variacion_max'].max()):.2e} (idem).\n",
              "Potencia por familia en TAMANOS_EFECTO (Holm y Romano-Wolf, cada alfa):\n",
              _tabla(en_tamanos.round(3)),
              "\nMediana del p de Holm (familia principal) por duracion y delta:\n",
              _tabla(curva[curva["confirmatoria"] & curva["en_tamanos"]]
                     .groupby(["anios", "delta"])["p_holm"].median()
                     .unstack().reset_index().round(3)),
              "\nControl B: delta realizado / nominal por celda:\n",
              _tabla(resumen_control_b(control)[
                  ["escenario", "delta", "tipo", "horizonte", "inyectado", "razon_por_evento",
                   "razon_celda", "frac_coinciden", "mercados"]].round(3)),
              f"\nIteraciones: {sorted(unicos['iteraciones'].tolist())}; convergieron "
              f"{int(unicos['convergio'].sum())} de {len(unicos)}."]
    return "\n".join(partes) + "\n"


# =============================================================================
#  Etapa 3: la curva (D) y el control B
# =============================================================================
def main_curva(procesos=None, repeticiones=None):
    cfg = config.copia()
    repeticiones = repeticiones or cfg.NULA_REPETICIONES_POTENCIA
    ruta_piloto = os.path.join(CARPETA, "control_positivo_piloto.csv")
    if not os.path.exists(ruta_piloto):
        raise SystemExit("Falta el piloto: corre primero --piloto (mide la memoria por proceso).")
    medidas = pd.read_csv(ruta_piloto)
    if "etapa" not in medidas.columns:
        raise SystemExit("El piloto guardado es del diseno anterior: corre --piloto otra vez.")
    print(recursos.describir())
    estimacion = estimar_corrida(medidas, bloques_de_la_corrida(cfg),
                                 factores_de_tiempo(medidas, cfg))
    estimacion, nota = recortar_por_tiempo(estimacion, cfg.MINUTOS_MAX_CORRIDA)
    print(_tabla(estimacion.round(2)))
    print(f"Total estimado: {estimacion['minutos_estimados'].sum():.0f} minutos")
    if nota:
        print(nota)
    os.makedirs(CARPETA, exist_ok=True)
    estimacion.to_csv(os.path.join(CARPETA, "control_positivo_plan.csv"), index=False)

    comienzo = time.perf_counter()
    curvas, controles, minutos_bloque = [], [], []
    for _, fila in estimacion.iterrows():
        anios, cuantos = int(fila["anios"]), int(fila["mercados"])
        n_procesos = procesos or int(fila["procesos"])
        inicio_bloque = time.perf_counter()
        if fila["etapa"] == "D":
            trabajos = [(cfg.SEMILLA + DESPLAZAMIENTO_CURVA + 1000 * anios + k, anios, {},
                         repeticiones) for k in range(cuantos)]
            print(f"D, {anios} anos: {len(trabajos)} mercados, {n_procesos} procesos",
                  flush=True)
            curvas += _en_paralelo(_tarea_curva, trabajos, n_procesos)
        else:
            trabajos = [(cfg.SEMILLA + DESPLAZAMIENTO_CONTROL_B + k, anios, {})
                        for k in range(cuantos)]
            print(f"B, {anios} anos: {len(trabajos)} mercados, {n_procesos} procesos",
                  flush=True)
            controles += _en_paralelo(_tarea_control_b, trabajos, n_procesos)
        minutos_bloque.append((time.perf_counter() - inicio_bloque) / 60)
    estimacion["minutos_reales"] = minutos_bloque
    estimacion.to_csv(os.path.join(CARPETA, "control_positivo_plan.csv"), index=False)
    curva = pd.concat(curvas, ignore_index=True)
    control = pd.concat(controles, ignore_index=True)
    minutos = (time.perf_counter() - comienzo) / 60
    curva.to_csv(os.path.join(CARPETA, "control_positivo.csv"), index=False,
                 float_format="%.6g")
    control.to_csv(os.path.join(CARPETA, "control_positivo_b.csv"), index=False,
                   float_format="%.6g")
    pd.DataFrame([{"minutos": minutos, "repeticiones": repeticiones, "nota": nota or ""}]) \
        .to_csv(os.path.join(CARPETA, "control_positivo_meta.csv"), index=False)
    _reporte_curva(curva, control, cfg, minutos, repeticiones, estimacion, nota)
    print(f"\nListo en {minutos:.1f} minutos. Reportes en resultados/")


def _reporte_curva(curva, control, cfg, minutos, repeticiones, plan, nota):
    """
    Aplica la regla del alfa y escribe el markdown y el grafico. Si la regla
    dice que el control falla, escribe solo la regla y se detiene.
    """
    regla = aplicar_regla_alfa(curva, cfg)
    ruta = os.path.join(CARPETA, "control_positivo.md")
    if regla["decision"] is None:
        texto = ("# Control positivo: EL CONTROL FALLA\n\n" + _markdown_regla(regla, cfg)
                 + "\nNo se escribe el resto del reporte: la regla manda detenerse.\n")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
        print(texto)
        raise SystemExit(1)
    cfg_reporte = SimpleNamespace(**{**vars(cfg), "ALFA_PRINCIPAL": regla["decision"]})
    texto = _markdown_curva(curva, control, cfg_reporte, minutos, repeticiones, regla,
                            plan, nota)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    grafico_potencia(potencia_por_familia(marcar_rechazos(curva, cfg_reporte), cfg_reporte),
                     cfg_reporte, os.path.join(CARPETA, "control_positivo_potencia.png"))


def _con_error(potencia, mercados):
    """Una potencia con su error de Monte Carlo entre parentesis."""
    return f"{potencia:.3f} ({error_monte_carlo(potencia, mercados):.3f})"


def _markdown_curva(curva, control, cfg, minutos, repeticiones, regla, plan, nota):
    marcada = marcar_rechazos(curva, cfg)
    familia = potencia_por_familia(marcada, cfg)
    celda = potencia_por_celda(marcada, cfg)
    principal = columna_principal(cfg)
    holm = [f"rechaza_holm_{alfa}" for alfa in cfg.ALFAS_POTENCIA]
    tamanos = sorted(curva.loc[curva["en_tamanos"], "delta"].unique())
    objetivo = cfg.POTENCIA_OBJETIVO
    remuestreos, semilla = cfg.REMUESTREOS_IC_MERCADOS, cfg.SEMILLA
    por_duracion = curva.groupby("anios")["mercado"].nunique()

    def etiqueta(columna):
        alfa = float(columna.rsplit("_", 1)[-1])
        return f"holm_{alfa}" + (" (principal)" if alfa == cfg.ALFA_PRINCIPAL else "")

    partes = ["# Control positivo: curva de potencia (diseno D)\n",
              "- Mercados por duracion: " + ", ".join(
                  f"{a} anos = {n}" for a, n in por_duracion.items()) + ".",
              "- Diseno D: el mercado queda limpio y a cada evento se le suma signo * delta "
              "en su retorno normalizado, en los cuatro horizontes (+ sostenidas, "
              "- reingresos). El delta que llega a cada celda es exactamente el nominal. La "
              "nula y los remuestreos de Romano-Wolf se sortean una vez por mercado y se "
              "comparten entre todos los delta.",
              f"- Repeticiones de la nula y de Romano-Wolf: {repeticiones}.",
              f"- Tiempo: {minutos:.1f} minutos. Equipo: {recursos.describir()}.",
              f"- Lectura principal: Holm sobre la nula emparejada, con el alfa que fijo la "
              f"regla de la seccion 0 ({cfg.ALFA_PRINCIPAL}). Las otras combinaciones son "
              f"solo descripcion; {inferencia.ETIQUETA_ROMANO_WOLF}.",
              "- Entre parentesis, el error de Monte Carlo de cada potencia, "
              "raiz(p(1-p)/n) con n los mercados de su duracion; en p = 0,5 vale " +
              ", ".join(f"{error_monte_carlo(0.5, n):.3f} ({a} anos)"
                        for a, n in por_duracion.items()) + "."]
    if nota:
        partes.append(f"- **Recorte por tiempo**: {nota}")
    partes += ["\nPlan (estimado con el piloto) y tiempo real por bloque:\n",
               _tabla(plan.round(2)), ""]

    # 0. Regla del alfa
    partes.append(_markdown_regla(regla, cfg))

    # 1. Por familia
    en_tamanos = familia[familia["delta"].isin(tamanos)]
    partes += ["## 1. Potencia por familia (al menos un rechazo correcto)\n"]
    for columna in holm:
        tabla = en_tamanos[["anios", "delta"]].copy()
        tabla["p"] = [_con_error(p, m) for p, m in zip(en_tamanos[columna],
                                                      en_tamanos["mercados"])]
        partes += [f"Holm, alfa {columna.rsplit('_', 1)[-1]}"
                   + (" (**principal**)" if columna == principal else "") + ":\n",
                   _tabla(tabla.pivot(index="anios", columns="delta",
                                      values="p").reset_index()), ""]
    partes += ["Las cuatro combinaciones (descripcion):\n", _tabla(en_tamanos.round(3))]

    # 2. Efecto minimo detectable
    por_mercado = rechazos_familia_por_mercado(marcada, cfg)
    filas = []
    for anios, bloque in por_mercado.groupby("anios"):
        fila = {"anios": anios}
        for columna in holm:
            matriz = bloque.pivot(index="mercado", columns="delta", values=columna)
            mde, bajo, alto = efecto_minimo_con_ic(matriz, objetivo, remuestreos, semilla)
            fila[etiqueta(columna)] = mde
            fila[f"ic95 {etiqueta(columna)}"] = f"[{bajo:.4f}, {alto:.4f}]"
        for columna in columnas_de_rechazo(cfg):
            if columna.startswith("rechaza_romano_wolf"):
                fila[columna.replace("rechaza_", "")] = efecto_minimo_detectable(
                    familia.loc[familia["anios"] == anios, "delta"],
                    familia.loc[familia["anios"] == anios, columna], objetivo)
        filas.append(fila)
    confirmatorias = marcada[marcada["confirmatoria"]]
    mde_celda = []
    for (anios, tipo, h), bloque in confirmatorias.groupby(["anios", "tipo", "horizonte"]):
        fila = {"anios": anios, "tipo": tipo, "horizonte": h}
        for columna in holm:
            matriz = bloque.pivot(index="mercado", columns="delta", values=columna)
            mde, bajo, alto = efecto_minimo_con_ic(matriz, objetivo, remuestreos, semilla)
            fila[etiqueta(columna)] = mde
            fila[f"ic95 {etiqueta(columna)}"] = f"[{bajo:.4f}, {alto:.4f}]"
            if columna == principal:
                fila["mde"] = mde
        mde_celda.append(fila)
    mde_celda = pd.DataFrame(mde_celda)
    paso = np.diff(rejilla_de_deltas(cfg)).max()
    partes += [f"\n## 2. Efecto minimo detectable al {objetivo:.0%}\n",
               f"Sobre la grilla fina (paso maximo {paso:.3f}), interpolando entre los dos "
               f"puntos que rodean el objetivo. Intervalo al 95% remuestreando mercados "
               f"({remuestreos} remuestreos); `inf` = mas del 2,5% de los remuestreos no "
               f"llega dentro de la grilla. `-` = la curva no llega.\n",
               "Por familia (Holm con los dos alfas, con intervalo; Romano-Wolf, "
               "descripcion):\n",
               _tabla(pd.DataFrame(filas).round(4)),
               "\nPor celda (Holm):\n", _tabla(mde_celda.drop(columns="mde").round(4))]

    # 2b. El titular del pre-registro: por celda, en unidades y en pips
    ruta_factores = os.path.join(CARPETA, "control_positivo_factores.csv")
    if os.path.exists(ruta_factores):
        tabla = pd.read_csv(ruta_factores, dtype={"idx_franja": str})
        mediana = tabla[(tabla["vol"] == cfg.VOL_ANUAL_SIMULACION)
                        & (tabla["idx_franja"] == "todas")].set_index("horizonte")["mediana"]
        en_pips = mde_celda[["anios", "tipo", "horizonte", "mde"]].copy()
        en_pips["pips_por_unidad"] = en_pips["horizonte"].astype(str).map(mediana)
        en_pips["mde_pips"] = en_pips["mde"] * en_pips["pips_por_unidad"]
        partes += [f"\n**Efecto minimo detectable POR CELDA (el que va al pre-registro)**, "
                   f"Holm con alfa {cfg.ALFA_PRINCIPAL}, en unidades normalizadas y en pips. "
                   f"Los pips usan el factor mediano pips / unidad con volatilidad "
                   f"{cfg.VOL_ANUAL_SIMULACION} (etapa 1): **es un orden de magnitud**; la "
                   f"traduccion definitiva sera evento por evento con el sigma_ref de los "
                   f"datos reales. El de familia (arriba) se reporta pero no es el titular: "
                   f"supone que las 6 celdas tienen el efecto y cuenta cualquier rechazo.\n",
                   _tabla(en_pips.round(4))]

    # 3. Por celda
    en_tamanos = celda[celda["delta"].isin(tamanos)].copy()
    partes += ["\n## 3. Potencia por celda\n"]
    for columna in holm:
        en_tamanos["p"] = [_con_error(p, m) for p, m in zip(en_tamanos[columna],
                                                           en_tamanos["mercados"])]
        partes += [f"Holm, alfa {columna.rsplit('_', 1)[-1]}"
                   + (" (**principal**)" if columna == principal else "") + ":\n",
                   _tabla(en_tamanos.pivot_table(index=["anios", "tipo", "horizonte"],
                                                 columns="delta", values="p",
                                                 aggfunc="first").reset_index()), ""]

    # 4. Sesgo
    realizado = delta_realizado(curva, cfg)
    desvio = float(np.abs(realizado["realizado"] - realizado["delta"]).max())
    sesgo = sesgo_del_estimador(curva, cfg)
    partes += ["\n## 4. Sesgo del estimador, por celda\n",
               "El efecto que reporta el informe es lo observado menos lo nulo, en la "
               "direccion de la hipotesis. `sesgo` = su promedio entre mercados menos el "
               "delta verdadero; en el diseno D no depende de delta (`variacion_max` es el "
               "mayor cambio entre delta, en cualquier mercado). `sesgo_media_cruda` es el de "
               "la media sin descontar la nula (la que prueba Romano-Wolf). Incluye el "
               "horizonte descriptivo de 120.\n",
               _tabla(sesgo.round(5)),
               f"\nDelta realizado: el mayor desvio contra el nominal es {desvio:.2e} "
               f"(cero por construccion, salvo redondeo; con --solo-reporte, del orden de "
               f"1e-7, porque el CSV guarda 6 cifras).\n"]

    # 5. Tamano en delta = 0
    partes += ["\n## 5. En delta = 0: tasas de rechazo, por duracion\n",
               f"Cada duracion por separado; no se suman entre si ni con el punto D. La "
               f"tasa por prueba (p bruto) de {cfg.ANIOS_REGLA_ALFA} anos es la que usa la "
               f"regla de la seccion 0; las de las otras duraciones y las tasas familiares "
               f"con Holm se informan aparte. Familia: mercados con algun rechazo de Holm "
               f"(Wilson). Por prueba: intervalo remuestreando mercados.\n"]
    for alfa in cfg.ALFAS_POTENCIA:
        partes += [f"Alfa {alfa}" + (" (principal)" if alfa == cfg.ALFA_PRINCIPAL else "")
                   + ":\n",
                   _tabla(tamano_en_cero(curva, cfg, remuestreos, semilla, alfa=alfa)
                          .round(4)), ""]

    # 6. Costos
    partes += ["\n## 6. Lectura contra un costo (APROXIMACION)\n",
               "La curva mide deteccion del efecto BRUTO. Para un costo c en unidades "
               "normalizadas, la potencia de un test NETO en delta se aproxima por la "
               "potencia bruta en delta - c (Holm principal, grilla fina), porque el error "
               "estandar casi no depende de delta. **Es una aproximacion, no una "
               "medicion.** c sale de la mediana del factor pips / unidad de la etapa 1 "
               f"(volatilidad {cfg.VOL_ANUAL_SIMULACION}). `-` = delta <= c: el efecto neto "
               "no es positivo. Por la misma razon, el efecto minimo detectable neto es "
               "aproximadamente el bruto mas c.\n"]
    factores = os.path.join(CARPETA, "control_positivo_factores.csv")
    if os.path.exists(factores):
        costos = costos_en_unidades(pd.read_csv(factores, dtype={"idx_franja": str}),
                                    cfg.COSTOS_IDA_VUELTA_PIPS)
        costos = costos[costos["vol"] == cfg.VOL_ANUAL_SIMULACION]
        partes.append(_tabla(potencia_contra_costo(
            celda, principal, costos, [d for d in tamanos if d > 0]).round(3)))
        filas = []
        for _, m in mde_celda.iterrows():
            for _, c in costos[costos["horizonte"] == str(m["horizonte"])].iterrows():
                filas.append({"anios": m["anios"], "tipo": m["tipo"],
                              "horizonte": m["horizonte"], "costo_pips": c["costo_pips"],
                              "costo_unidades": c["unidades_mediana"], "mde_bruto": m["mde"],
                              "mde_neto_aprox": m["mde"] + c["unidades_mediana"]})
        partes += ["\nEfecto minimo detectable neto (aproximado):\n",
                   _tabla(pd.DataFrame(filas).round(4))]
    else:
        partes.append("_(falta `control_positivo_factores.csv`: corre --piso)_")

    # 7. Control B
    resumen_b = resumen_control_b(control)
    partes += ["\n## 7. Control B (descriptivo, no decide nada)\n",
               f"Inyeccion en PRECIOS, autoconsistente, {control['mercado'].nunique()} "
               f"mercados de {cfg.ANIOS_CONTROL_B} anos, los mismos en los tres escenarios: "
               f"{', '.join(f'{k} = {v}' for k, v in cfg.ESCENARIOS_CONTROL_B.items())}. "
               "`razon_por_evento`: con los mismos eventos, que fraccion del delta nominal "
               "llego al retorno de la celda, en la direccion de SU hipotesis (incluye la "
               "superposicion y el corte de la deriva al fin de la franja). En la celda NO "
               "inyectada (`inyectado` = False) es el contagio desde la otra. "
               "`razon_celda`: cuanto se movio el promedio de la celda contra el mercado "
               "limpio (incluye ademas el cambio de eventos).\n",
               _tabla(resumen_b.round(4))]
    unicos = control.drop_duplicates(["mercado", "escenario", "delta"])
    partes.append(f"\nIteraciones hasta converger: mediana "
                  f"{unicos['iteraciones'].median():.0f}, maximo "
                  f"{unicos['iteraciones'].max()}; convergieron "
                  f"{int(unicos['convergio'].sum())} de {len(unicos)}.\n")
    aproximada = potencia_aproximada_b(resumen_b, celda, principal, cfg.ANIOS_CONTROL_B)
    partes += ["\n**Lectura aproximada de la potencia de B**: la potencia de cada celda es "
               f"la de D (Holm principal, {cfg.ANIOS_CONTROL_B} anos, misma celda) en el delta "
               "realizado por evento. Es una aproximacion: supone que lo que decide la "
               "deteccion es cuanto se mueve el promedio de la celda. `-` = el realizado va "
               "contra la hipotesis de la celda; la potencia es, a lo sumo, el tamano.\n",
               _tabla(aproximada.round(4))]
    return "\n".join(partes) + "\n"


def grafico_potencia(familia, cfg, ruta):
    """
    Potencia por familia contra el delta nominal (grilla fina), un panel por
    duracion.

    Enfasis y no cuatro colores: la lectura principal (Holm, ALFA_PRINCIPAL)
    va en azul y gruesa; las otras tres combinaciones son descripcion y van en
    gris, distinguidas por el trazo (Holm lleno, Romano-Wolf cortado) y el
    grosor segun el alfa. La tabla del reporte tiene todos los valores.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    azul, gris, tinta, grilla, eje_color, fondo = (
        "#2a78d6", "#898781", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb")
    trazo = {"holm": "-", "romano_wolf": (0, (4, 2))}
    grosor = dict(zip(cfg.ALFAS_POTENCIA, [1.2, 0.7, 0.5, 0.4]))

    duraciones = sorted(familia["anios"].unique())
    figura, ejes = plt.subplots(1, len(duraciones), figsize=(5.0 * len(duraciones), 4.3),
                                sharey=True, facecolor=fondo)
    ejes = np.atleast_1d(ejes)
    for eje, anios in zip(ejes, duraciones):
        eje.set_facecolor(fondo)
        bloque = familia[familia["anios"] == anios].sort_values("delta")
        for nombre, _ in COMBINACIONES:
            for alfa in cfg.ALFAS_POTENCIA:
                principal = nombre == "holm" and alfa == cfg.ALFA_PRINCIPAL
                eje.plot(bloque["delta"], bloque[f"rechaza_{nombre}_{alfa}"],
                         linestyle=trazo[nombre],
                         linewidth=2.2 if principal else grosor[alfa],
                         color=azul if principal else gris,
                         zorder=3 if principal else 2,
                         label=f"{'Holm' if nombre == 'holm' else 'Romano-Wolf'}, "
                               f"alfa {alfa}" + (" (principal)" if principal else ""))
        eje.axhline(cfg.POTENCIA_OBJETIVO, color=eje_color, linewidth=0.8, zorder=1)
        eje.text(bloque["delta"].max(), cfg.POTENCIA_OBJETIVO + 0.015,
                 f"{cfg.POTENCIA_OBJETIVO:.0%}", color=tinta, fontsize=8, ha="right")
        mercados = int(bloque["mercados"].max())
        eje.set_title(f"{anios} anos ({mercados} mercados)", color=tinta, fontsize=10)
        eje.set_xlabel("delta (unidades de retorno normalizado)", color=tinta)
        eje.set_ylim(0, 1.03)
        eje.grid(color=grilla, linewidth=0.6)
        eje.tick_params(colors=tinta, labelsize=8)
        for lado in ("top", "right"):
            eje.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            eje.spines[lado].set_color(eje_color)
    ejes[0].set_ylabel("potencia por familia", color=tinta)
    ejes[-1].legend(fontsize=7, loc="lower right", frameon=False, labelcolor=tinta)
    figura.suptitle("Control positivo (diseno D): potencia de la familia principal",
                    color=tinta)
    figura.tight_layout()
    figura.savefig(ruta, dpi=130, facecolor=fondo)
    plt.close(figura)


# =============================================================================
#  Programa principal
# =============================================================================
def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--piso", action="store_true",
                            help="etapa 1: piso sin la nula y traduccion a pips")
    analizador.add_argument("--piloto", action="store_true",
                            help="etapa 2: tiempo y memoria de D y de B")
    analizador.add_argument("--solo-reporte", action="store_true",
                            help="rehace el reporte de la curva desde los CSV guardados")
    analizador.add_argument("--procesos", type=int, default=None)
    analizador.add_argument("--repeticiones", type=int, default=None)
    opciones = analizador.parse_args()

    repeticiones = opciones.repeticiones or config.NULA_REPETICIONES_POTENCIA
    if opciones.piso:
        etapa_piso(opciones.procesos)
    elif opciones.piloto:
        piloto(repeticiones)
    elif opciones.solo_reporte:
        curva = pd.read_csv(os.path.join(CARPETA, "control_positivo.csv"),
                            dtype={"horizonte": str})
        control = pd.read_csv(os.path.join(CARPETA, "control_positivo_b.csv"),
                              dtype={"horizonte": str})
        meta = pd.read_csv(os.path.join(CARPETA, "control_positivo_meta.csv"),
                           keep_default_na=False).iloc[0]
        plan = pd.read_csv(os.path.join(CARPETA, "control_positivo_plan.csv"))
        _reporte_curva(curva, control, config.copia(), float(meta["minutos"]),
                       int(meta["repeticiones"]), plan, meta["nota"] or None)
    else:
        main_curva(opciones.procesos, opciones.repeticiones)


if __name__ == "__main__":
    main()
