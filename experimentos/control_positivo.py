# -*- coding: utf-8 -*-
"""
CONTROL POSITIVO — cuanta potencia tiene el motor.

Se inyecta un efecto de tamano conocido (simulacion/inyeccion.py) en mercados
simulados sin ningun patron, se corre el pipeline completo sobre el mercado
inyectado y se cuenta con que frecuencia la familia principal lo detecta.

Definiciones, acordadas en el punto E antes de ver la curva:

  - Efecto: +delta en las sostenidas y -delta en los reingresos, en la
    direccion de la ruptura, IGUAL en todos los horizontes dentro de la franja.
  - Potencia por celda: proporcion de mercados en que esa prueba rechaza con
    el signo que predice su hipotesis.
  - Potencia por familia: proporcion de mercados con AL MENOS un rechazo
    correcto entre las pruebas de la familia principal.
  - La lectura principal es Holm sobre la nula emparejada con ALFA_PRINCIPAL.
    Las cuatro combinaciones (Holm y Romano-Wolf, con cada alfa de
    ALFAS_POTENCIA) se reportan solo como descripcion: Romano-Wolf es otra
    prueba (t de la regresion contra cero, dos colas, sin la nula).
  - Eje de la curva: el delta NOMINAL, con el delta realizado al lado.

PENDIENTE (segunda parte del punto E): el grupo decidio medir la curva con el
diseno D (sumar delta al retorno normalizado de cada evento, sobre el mercado
limpio) y dejar la inyeccion en precios como control descriptivo, hecha
autoconsistente. `corrida_curva` todavia es la inyeccion en precios en dos
pasadas, que se descarto: no correr la curva completa hasta reemplazarla (ver
la bitacora).

Etapas, en el orden acordado:

    python -m experimentos.control_positivo --piso        piso sin la nula y traduccion a pips
    python -m experimentos.control_positivo --piloto      tiempo y memoria de la curva
    python -m experimentos.control_positivo               la curva completa
    python -m experimentos.control_positivo --solo-reporte
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                              # noqa: E402
import motor                                               # noqa: E402
from experimentos import recursos                          # noqa: E402
from experimentos.control_negativo import (                # noqa: E402
    CARPETA, _en_paralelo, _tabla, error_monte_carlo)
from motor import inferencia, nula                         # noqa: E402
from simulacion import inyeccion, mercado                  # noqa: E402

# Bloques de semillas. El piso reusa a proposito las del control negativo
# (SEMILLA + k): sus primeros 50 mercados son los mismos del punto D, asi que
# el piso tiene que reproducir aquella tabla.
DESPLAZAMIENTO_CURVA = 20000
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
#  La curva
# =============================================================================
def _analizar_mercado(datos, noticias, cfg, semilla, repeticiones):
    """El pipeline completo sobre un mercado: eventos, nula y familia principal."""
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    tabla_nula, _ = nula.correr(barras, cal, eventos, cfg, semilla,
                                repeticiones=repeticiones, candidatos=candidatos)
    del candidatos, barras, cal
    principal = inferencia.analizar(
        eventos, cfg, cfg.FAMILIA_PRINCIPAL, semilla,
        p_brutos=inferencia.p_brutos_desde_nula(tabla_nula, cfg),
        con_romano_wolf=True, repeticiones_rw=repeticiones, alfa=cfg.ALFA_PRINCIPAL)
    return eventos, tabla_nula, principal


def _filas_de_la_curva(eventos, tabla_nula, principal, cfg, eventos_limpios):
    """
    Una fila por tipo de la familia principal y horizonte (tambien los
    descriptivos).

    `frac_inyectados` es la proporcion de eventos de ese tipo que coinciden
    (mismo instante) con un evento del mercado limpio, o sea los que
    recibieron el efecto. Los demas aparecieron por la retroalimentacion: la
    deriva movio los extremos de alguna franja y el motor detecto otra cosa.
    """
    confirmatorias = principal.assign(horizonte=principal["horizonte"].astype(str)) \
        .set_index(["tipo", "horizonte"])
    filas = []
    for tipo in _tipos(cfg):
        del_tipo = eventos[eventos["tipo"] == tipo]
        limpios = eventos_limpios.loc[eventos_limpios["tipo"] == tipo, "t_evento_ns"]
        coinciden = np.isin(del_tipo["t_evento_ns"].to_numpy(np.int64),
                            limpios.to_numpy(np.int64))
        for h in cfg.HORIZONTES:
            nulo = tabla_nula[(tabla_nula["tipo"] == tipo)
                              & (tabla_nula["horizonte"].astype(str) == str(h))].iloc[0]
            fila = {"tipo": tipo, "horizonte": str(h),
                    "confirmatoria": h in cfg.HORIZONTES_CONFIRMATORIOS,
                    "n_tipo": len(del_tipo),
                    "frac_inyectados": float(coinciden.mean()) if len(del_tipo) else np.nan,
                    "sigma_ref_medio": float(del_tipo["sigma_ref"].mean()),
                    "n_eventos": int(nulo["n_eventos"]),
                    "media_observada": nulo["media_observada"],
                    "media_nula": nulo["media_nula"],
                    "t_observado": nulo["t_observado"],
                    "p_bruto": nulo["p_una_cola"],
                    "estimacion": np.nan, "t_regresion": np.nan,
                    "p_holm": np.nan, "p_romano_wolf": np.nan}
            if (tipo, str(h)) in confirmatorias.index:
                c = confirmatorias.loc[(tipo, str(h))]
                fila.update(estimacion=c["estimacion"], t_regresion=c["t"],
                            p_holm=c["p_holm"], p_romano_wolf=c["p_romano_wolf"])
            filas.append(fila)
    return filas


def corrida_curva(semilla, anios, cambios, repeticiones):
    """
    Un mercado, todos los tamanos de efecto.

    El mercado limpio se genera una sola vez; sus eventos definen donde se
    inyecta. Cada delta se inyecta sobre ese mismo mercado limpio y se corre
    el pipeline completo sobre el resultado, con la MISMA semilla de la nula
    para todos los delta (numeros aleatorios comunes: las diferencias entre
    delta no se ensucian con ruido de sorteo).
    """
    cfg = config.copia(**cambios)
    limpio, noticias = mercado.generar(anios, semilla, cfg)
    filas = []
    eventos_limpios = None
    for delta in cfg.TAMANOS_EFECTO:
        comienzo = time.perf_counter()
        if delta == 0:
            datos = limpio
        else:
            if eventos_limpios is None:
                _, _, eventos_limpios = motor.preparar(limpio, cfg, noticias=noticias)
            datos = inyeccion.inyectar(limpio, eventos_limpios, delta, cfg)
        eventos, tabla_nula, principal = _analizar_mercado(datos, noticias, cfg, semilla,
                                                           repeticiones)
        if delta == 0:
            eventos_limpios = eventos
        segundos = time.perf_counter() - comienzo
        for fila in _filas_de_la_curva(eventos, tabla_nula, principal, cfg, eventos_limpios):
            filas.append({"mercado": semilla, "anios": anios, "delta": delta,
                          "segundos_delta": segundos, **fila})
        del datos
    return pd.DataFrame(filas)


def _tarea_curva(argumentos):
    return corrida_curva(*argumentos)


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


def potencia_por_celda(marcada, cfg):
    """Proporcion de mercados que rechazan, por duracion, delta y prueba."""
    confirmatorias = marcada[marcada["confirmatoria"]]
    tabla = confirmatorias.groupby(["anios", "delta", "tipo", "horizonte"])[
        columnas_de_rechazo(cfg)].mean()
    tabla["mercados"] = confirmatorias.groupby(["anios", "delta", "tipo", "horizonte"]).size()
    return tabla.reset_index()


def potencia_por_familia(marcada, cfg):
    """Proporcion de mercados con AL MENOS un rechazo correcto en la familia principal."""
    confirmatorias = marcada[marcada["confirmatoria"]]
    por_mercado = confirmatorias.groupby(["anios", "delta", "mercado"])[
        columnas_de_rechazo(cfg)].any()
    tabla = por_mercado.groupby(["anios", "delta"]).mean()
    tabla["mercados"] = por_mercado.groupby(["anios", "delta"]).size()
    return tabla.reset_index()


def efecto_minimo_detectable(deltas, potencias, objetivo):
    """
    El delta con el que la potencia llega a `objetivo`, interpolando en linea
    recta entre los dos puntos de la curva que lo rodean. NaN si la curva no
    llega.
    """
    deltas = np.asarray(deltas, dtype=float)
    potencias = np.asarray(potencias, dtype=float)
    orden = np.argsort(deltas)
    deltas, potencias = deltas[orden], potencias[orden]
    llega = np.flatnonzero(potencias >= objetivo)
    if len(llega) == 0:
        return np.nan
    i = int(llega[0])
    if i == 0:
        return float(deltas[0])
    d0, d1, p0, p1 = deltas[i - 1], deltas[i], potencias[i - 1], potencias[i]
    return float(d0 + (objetivo - p0) * (d1 - d0) / (p1 - p0))


def delta_realizado(curva, cfg):
    """
    Cuanto se movio de verdad el retorno de cada celda, en la direccion de la
    hipotesis: promedio entre mercados de (media con delta - media sin delta).
    Incluye todo lo que hace la retroalimentacion (eventos que aparecen o
    desaparecen, derivas que se superponen, horizontes que cruzan el fin de la
    franja).

    Tambien el efecto ESTIMADO (observado menos nulo, en la direccion de la
    hipotesis) y su sesgo contra el delta nominal.
    """
    signo = curva["tipo"].map(inyeccion.signos(cfg))
    base = curva[curva["delta"] == 0].set_index(
        ["anios", "mercado", "tipo", "horizonte"])["media_observada"]
    llave = pd.MultiIndex.from_frame(curva[["anios", "mercado", "tipo", "horizonte"]])
    tabla = curva.assign(
        realizado=signo * (curva["media_observada"].to_numpy(float)
                           - base.reindex(llave).to_numpy(float)),
        estimado=signo * (curva["media_observada"] - curva["media_nula"]))
    tabla["sesgo"] = tabla["estimado"] - tabla["delta"]
    agrupado = tabla.groupby(["anios", "delta", "tipo", "horizonte"])
    salida = agrupado[["realizado", "estimado", "sesgo"]].mean()
    salida["error_mc_estimado"] = agrupado["estimado"].std() / np.sqrt(agrupado.size())
    return salida.reset_index()


def piso_no_absorbido(curva):
    """
    En delta = 0: media observada menos media nula, por celda. Es la parte del
    sesgo propio de los eventos que la nula emparejada NO absorbe.
    """
    cero = curva[curva["delta"] == 0].assign(
        diferencia=lambda t: t["media_observada"] - t["media_nula"])
    agrupado = cero.groupby(["anios", "tipo", "horizonte"])
    salida = agrupado[["media_observada", "media_nula", "diferencia"]].mean()
    salida["error_mc"] = agrupado["diferencia"].std() / np.sqrt(agrupado.size())
    salida["mercados"] = agrupado.size()
    return salida.reset_index()


def efecto_de_la_retroalimentacion(curva):
    """
    Cuanto cambian, contra el mercado limpio, la cantidad de eventos y su
    sigma_ref promedio. Si la deriva inyectada casi no toca sigma_ref, estos
    numeros quedan cerca de cero.
    """
    por_tipo = curva.drop_duplicates(["anios", "delta", "mercado", "tipo"])
    base = por_tipo[por_tipo["delta"] == 0].set_index(["anios", "mercado", "tipo"])
    llave = pd.MultiIndex.from_frame(por_tipo[["anios", "mercado", "tipo"]])
    tabla = por_tipo.assign(
        cambio_eventos=por_tipo["n_tipo"].to_numpy(float)
        / base["n_tipo"].reindex(llave).to_numpy(float) - 1,
        cambio_sigma_ref=por_tipo["sigma_ref_medio"].to_numpy(float)
        / base["sigma_ref_medio"].reindex(llave).to_numpy(float) - 1)
    return tabla.groupby(["anios", "delta", "tipo"])[
        ["frac_inyectados", "cambio_eventos", "cambio_sigma_ref"]].mean().reset_index()


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


def piloto(repeticiones):
    """
    Mide tiempo y memoria de MERCADOS_PILOTO mercados de cada duracion, de a
    uno y cada uno en un proceso nuevo, y estima la corrida completa con los
    procesos que caben en el 70% de la memoria disponible.
    """
    cfg = config.copia()
    print(recursos.describir())
    medidas, curvas = [], []
    for anios in cfg.ANIOS_POTENCIA:
        for k in range(cfg.MERCADOS_PILOTO):
            semilla = cfg.SEMILLA + DESPLAZAMIENTO_PILOTO + 1000 * anios + k
            print(f"Piloto: mercado {k + 1} de {cfg.MERCADOS_PILOTO}, {anios} anos, "
                  f"{len(cfg.TAMANOS_EFECTO)} tamanos de efecto...", flush=True)
            curva, pico, segundos = recursos.medir_pico(
                lambda: _en_proceso_nuevo(_tarea_curva, (semilla, anios, {}, repeticiones)))
            print(f"  {segundos:.1f} s, ~{pico:.2f} GB de pico", flush=True)
            medidas.append({"anios": anios, "mercado": semilla, "segundos": segundos,
                            "pico_gb": pico})
            curvas.append(curva)
    medidas = pd.DataFrame(medidas)
    curva = pd.concat(curvas, ignore_index=True)
    os.makedirs(CARPETA, exist_ok=True)
    medidas.to_csv(os.path.join(CARPETA, "control_positivo_piloto.csv"), index=False)
    curva.to_csv(os.path.join(CARPETA, "control_positivo_piloto_curva.csv"), index=False,
                 float_format="%.6g")
    texto = _markdown_piloto(medidas, curva, cfg, repeticiones)
    with open(os.path.join(CARPETA, "control_positivo_piloto.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


def estimar_corrida(medidas, repeticiones_potencia, fraccion=0.70):
    """
    Tiempo estimado de la corrida completa, por duracion: cada duracion corre
    con los procesos que caben segun el PEOR pico de memoria que se midio.
    """
    filas = []
    for anios, bloque in medidas.groupby("anios"):
        pico = float(bloque["pico_gb"].max())
        procesos = recursos.procesos_que_caben(pico, fraccion=fraccion)
        segundos = float(bloque["segundos"].mean())
        filas.append({"anios": anios, "segundos_por_mercado": segundos, "pico_gb": pico,
                      "procesos": procesos, "mercados": repeticiones_potencia,
                      "minutos_estimados": repeticiones_potencia * segundos
                      / procesos / 60})
    return pd.DataFrame(filas)


def _markdown_piloto(medidas, curva, cfg, repeticiones):
    estimacion = estimar_corrida(medidas, cfg.REPETICIONES_POTENCIA)
    total = float(estimacion["minutos_estimados"].sum())
    partes = ["# Control positivo, etapa 2: piloto\n",
              f"- {cfg.MERCADOS_PILOTO} mercados por duracion, cada uno con los "
              f"{len(cfg.TAMANOS_EFECTO)} tamanos de efecto {cfg.TAMANOS_EFECTO}.",
              f"- Repeticiones de la nula y de Romano-Wolf: {repeticiones}.",
              f"- Equipo: {recursos.describir()}.\n",
              "## Medido\n", _tabla(medidas.round(2)),
              "\n## Estimacion de la corrida completa\n",
              f"{cfg.REPETICIONES_POTENCIA} mercados por duracion, procesos limitados al "
              f"70% de la memoria disponible AHORA:\n",
              _tabla(estimacion.round(2)),
              f"\n**Total estimado: {total:.0f} minutos.**\n",
              "## Primera mirada (solo para revisar que la maquina funciona)\n",
              "Con tan pocos mercados esto NO es la curva: sirve para ver que el delta "
              "realizado sigue al nominal y que los p-valores bajan cuando delta sube.\n"]
    realizado = delta_realizado(curva, cfg)
    partes.append(_tabla(realizado.pivot_table(
        index=["anios", "tipo", "horizonte"], columns="delta",
        values="realizado").reset_index().round(3)))
    p_medio = curva[curva["confirmatoria"]].groupby(["anios", "delta"])["p_holm"].median()
    partes += ["\nMediana del p de Holm (familia principal) por duracion y delta:\n",
               _tabla(p_medio.unstack().reset_index().round(3)),
               "\nRetroalimentacion (eventos que recibieron el efecto, cambio en la cantidad "
               "de eventos y en su sigma_ref):\n",
               _tabla(efecto_de_la_retroalimentacion(curva).round(4))]
    return "\n".join(partes) + "\n"


# =============================================================================
#  Etapa 3: la curva
# =============================================================================
def main_curva(procesos=None, repeticiones=None):
    cfg = config.copia()
    repeticiones = repeticiones or cfg.NULA_REPETICIONES_POTENCIA
    ruta_piloto = os.path.join(CARPETA, "control_positivo_piloto.csv")
    if not os.path.exists(ruta_piloto):
        raise SystemExit("Falta el piloto: corre primero --piloto (mide la memoria por proceso).")
    medidas = pd.read_csv(ruta_piloto)
    estimacion = estimar_corrida(medidas, cfg.REPETICIONES_POTENCIA)
    print(recursos.describir())
    comienzo = time.perf_counter()
    partes = []
    for _, fila in estimacion.iterrows():
        anios = int(fila["anios"])
        n_procesos = procesos or int(fila["procesos"])
        trabajos = [(cfg.SEMILLA + DESPLAZAMIENTO_CURVA + 1000 * anios + k, anios, {},
                     repeticiones) for k in range(cfg.REPETICIONES_POTENCIA)]
        print(f"{anios} anos: {len(trabajos)} mercados, {n_procesos} procesos", flush=True)
        partes += _en_paralelo(_tarea_curva, trabajos, n_procesos)
    curva = pd.concat(partes, ignore_index=True)
    minutos = (time.perf_counter() - comienzo) / 60
    curva.to_csv(os.path.join(CARPETA, "control_positivo.csv"), index=False,
                 float_format="%.6g")
    pd.DataFrame([{"minutos": minutos, "repeticiones": repeticiones}]).to_csv(
        os.path.join(CARPETA, "control_positivo_meta.csv"), index=False)
    _reporte_curva(curva, cfg, minutos, repeticiones)
    print(f"\nListo en {minutos:.1f} minutos. Reportes en resultados/")


def _reporte_curva(curva, cfg, minutos, repeticiones):
    """Escribe el markdown y el grafico de la curva."""
    texto = _markdown_curva(curva, cfg, minutos, repeticiones)
    with open(os.path.join(CARPETA, "control_positivo.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    grafico_potencia(potencia_por_familia(marcar_rechazos(curva, cfg), cfg), cfg,
                     os.path.join(CARPETA, "control_positivo_potencia.png"))


def _markdown_curva(curva, cfg, minutos, repeticiones):
    marcada = marcar_rechazos(curva, cfg)
    familia = potencia_por_familia(marcada, cfg)
    celda = potencia_por_celda(marcada, cfg)
    principal = f"rechaza_holm_{cfg.ALFA_PRINCIPAL}"
    n = int(familia["mercados"].min())

    partes = ["# Control positivo: curva de potencia\n",
              f"- {n} mercados por duracion y tamano; duraciones {cfg.ANIOS_POTENCIA} anos.",
              f"- Repeticiones de la nula y de Romano-Wolf: {repeticiones}.",
              f"- Tiempo: {minutos:.1f} minutos. Equipo: {recursos.describir()}.",
              f"- Lectura principal: Holm sobre la nula emparejada, alfa = "
              f"{cfg.ALFA_PRINCIPAL}. Las otras combinaciones son solo descripcion; "
              f"{inferencia.ETIQUETA_ROMANO_WOLF}.",
              f"- Error de Monte Carlo de una potencia p con {n} mercados: "
              f"raiz(p(1-p)/{n}); en p = 0,5 vale {error_monte_carlo(0.5, n):.3f}.\n"]

    partes += ["## 1. Potencia por familia (al menos un rechazo correcto)\n",
               _tabla(familia.round(3))]

    objetivo = cfg.POTENCIA_OBJETIVO
    filas = []
    for anios, bloque in familia.groupby("anios"):
        fila = {"anios": anios}
        for columna in columnas_de_rechazo(cfg):
            fila[columna.replace("rechaza_", "")] = efecto_minimo_detectable(
                bloque["delta"], bloque[columna], objetivo)
        filas.append(fila)
    partes += [f"\n## 2. Efecto minimo detectable al {objetivo:.0%} (por familia)\n",
               "Interpolacion lineal entre los dos tamanos que rodean la potencia objetivo; "
               "`-` si la curva no llega.\n", _tabla(pd.DataFrame(filas).round(4))]

    filas = []
    for (anios, tipo, h), bloque in celda.groupby(["anios", "tipo", "horizonte"]):
        filas.append({"anios": anios, "tipo": tipo, "horizonte": h,
                      "mde_holm_principal": efecto_minimo_detectable(
                          bloque["delta"], bloque[principal], objetivo)})
    mde_celda = pd.DataFrame(filas)
    partes += ["\n## 3. Potencia por celda (Holm, alfa principal)\n",
               _tabla(celda.pivot_table(index=["anios", "tipo", "horizonte"], columns="delta",
                                        values=principal).reset_index().round(3)),
               f"\nEfecto minimo detectable al {objetivo:.0%} por celda:\n",
               _tabla(mde_celda.round(4))]

    realizado = delta_realizado(curva, cfg)
    partes += ["\n## 4. Delta nominal, delta realizado y sesgo del estimador\n",
               "En la direccion de la hipotesis. `realizado`: cuanto se movio de verdad el "
               "retorno de la celda contra el mismo mercado sin efecto (incluye la "
               "retroalimentacion). `estimado`: observado menos nulo. `sesgo`: estimado "
               "menos nominal. En los horizontes que cruzan el fin de la franja (el de 120 "
               "y los eventos tardios) el realizado es menor POR CONSTRUCCION: la deriva "
               "queda fija al terminar la franja.\n",
               _tabla(realizado.round(4))]

    partes += ["\n## 5. En delta = 0: la parte del piso que la nula no absorbe\n",
               _tabla(piso_no_absorbido(curva).round(5))]

    partes += ["\n## 6. Retroalimentacion: eventos y sigma_ref contra el mercado limpio\n",
               "`frac_inyectados`: proporcion de eventos del mercado inyectado que coinciden "
               "con un evento del limpio (los que recibieron el efecto); el resto aparecio "
               "porque la deriva movio los extremos de alguna franja. `cambio_eventos` y "
               "`cambio_sigma_ref`: cambio relativo de la cantidad de eventos y de su "
               "sigma_ref promedio.\n",
               _tabla(efecto_de_la_retroalimentacion(curva).round(4))]

    partes += ["\n## 7. Como leer la curva contra un costo\n",
               "La curva mide deteccion del efecto BRUTO. Para un costo c (en unidades "
               "normalizadas, ver la etapa 1): la potencia de un test NETO en delta se "
               "aproxima por la potencia bruta en delta - c, porque el error estandar casi "
               "no depende de delta. Es una aproximacion. Por la misma razon, el efecto "
               "minimo detectable neto es aproximadamente el bruto mas c.\n"]
    factores = os.path.join(CARPETA, "control_positivo_factores.csv")
    if os.path.exists(factores):
        costos = costos_en_unidades(pd.read_csv(factores, dtype={"idx_franja": str}),
                                    cfg.COSTOS_IDA_VUELTA_PIPS)
        costos = costos[costos["vol"] == cfg.VOL_ANUAL_SIMULACION]
        filas = []
        for _, m in mde_celda.iterrows():
            for _, c in costos[costos["horizonte"] == str(m["horizonte"])].iterrows():
                filas.append({"anios": m["anios"], "tipo": m["tipo"],
                              "horizonte": m["horizonte"], "costo_pips": c["costo_pips"],
                              "costo_unidades": c["unidades_mediana"],
                              "mde_bruto": m["mde_holm_principal"],
                              "mde_neto_aprox": m["mde_holm_principal"]
                              + c["unidades_mediana"]})
        partes.append(_tabla(pd.DataFrame(filas).round(4)))
    return "\n".join(partes) + "\n"


def grafico_potencia(familia, cfg, ruta):
    """
    Potencia por familia contra el delta nominal, un panel por duracion.

    Enfasis y no cuatro colores: la lectura principal (Holm, ALFA_PRINCIPAL)
    va en azul y gruesa; las otras tres combinaciones son descripcion y van en
    gris, distinguidas por el trazo (Holm lleno, Romano-Wolf cortado) y por el
    marcador (circulo o cuadrado segun el alfa). La tabla del reporte tiene
    todos los valores.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    azul, gris, tinta, grilla, eje_color, fondo = (
        "#2a78d6", "#898781", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb")
    trazo = {"holm": "-", "romano_wolf": (0, (4, 2))}
    marcador = dict(zip(cfg.ALFAS_POTENCIA, ["o", "s", "^", "D"]))

    duraciones = sorted(familia["anios"].unique())
    figura, ejes = plt.subplots(1, len(duraciones), figsize=(5.6 * len(duraciones), 4.3),
                                sharey=True, facecolor=fondo)
    ejes = np.atleast_1d(ejes)
    for eje, anios in zip(ejes, duraciones):
        eje.set_facecolor(fondo)
        bloque = familia[familia["anios"] == anios].sort_values("delta")
        for nombre, _ in COMBINACIONES:
            for alfa in cfg.ALFAS_POTENCIA:
                principal = nombre == "holm" and alfa == cfg.ALFA_PRINCIPAL
                eje.plot(bloque["delta"], bloque[f"rechaza_{nombre}_{alfa}"],
                         linestyle=trazo[nombre], marker=marcador[alfa], markersize=5,
                         linewidth=2.0 if principal else 1.0,
                         color=azul if principal else gris,
                         zorder=3 if principal else 2,
                         label=f"{'Holm' if nombre == 'holm' else 'Romano-Wolf'}, "
                               f"alfa {alfa}" + (" (principal)" if principal else ""))
        eje.axhline(cfg.POTENCIA_OBJETIVO, color=eje_color, linewidth=0.8, zorder=1)
        eje.text(bloque["delta"].max(), cfg.POTENCIA_OBJETIVO + 0.015,
                 f"{cfg.POTENCIA_OBJETIVO:.0%}", color=tinta, fontsize=8, ha="right")
        eje.set_title(f"{anios} anos", color=tinta, fontsize=10)
        eje.set_xlabel("delta nominal (unidades de retorno normalizado)", color=tinta)
        eje.set_ylim(0, 1.03)
        eje.grid(color=grilla, linewidth=0.6)
        eje.tick_params(colors=tinta, labelsize=8)
        for lado in ("top", "right"):
            eje.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            eje.spines[lado].set_color(eje_color)
    ejes[0].set_ylabel("potencia por familia", color=tinta)
    ejes[-1].legend(fontsize=7, loc="lower right", frameon=False, labelcolor=tinta)
    figura.suptitle("Control positivo: potencia de la familia principal", color=tinta)
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
                            help="etapa 2: tiempo y memoria de la curva")
    analizador.add_argument("--solo-reporte", action="store_true",
                            help="rehace el reporte de la curva desde el CSV guardado")
    analizador.add_argument("--procesos", type=int, default=None)
    analizador.add_argument("--repeticiones", type=int, default=None)
    opciones = analizador.parse_args()

    repeticiones = opciones.repeticiones or config.NULA_REPETICIONES_POTENCIA
    if opciones.piso:
        etapa_piso(opciones.procesos)
    elif opciones.piloto:
        piloto(repeticiones)
    elif opciones.solo_reporte:
        curva = pd.read_csv(os.path.join(CARPETA, "control_positivo.csv"))
        meta = pd.read_csv(os.path.join(CARPETA, "control_positivo_meta.csv")).iloc[0]
        _reporte_curva(curva, config.copia(), float(meta["minutos"]),
                       int(meta["repeticiones"]))
    else:
        main_curva(opciones.procesos, opciones.repeticiones)


if __name__ == "__main__":
    main()
