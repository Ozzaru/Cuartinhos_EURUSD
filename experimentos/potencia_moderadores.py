# -*- coding: utf-8 -*-
"""
POTENCIA DE H3 Y H4 — cuanto efecto hace falta para que las pruebas de
moderadores y de anuncios lo detecten, en la duracion que confirma (4 anos,
como el tramo de validacion).

El punto E midio solo la familia principal (H1 y H2). Aqui se mide lo que
faltaba, con el mismo principio del diseno D: el mercado queda limpio y el
efecto se suma al retorno normalizado de los eventos, pero solo a los del
SUBGRUPO que senala la hipotesis:

  H3  a los eventos con el moderador encendido se les suma signo * delta
      (+ en sostenidas, - en reingresos: el moderador intensifica el efecto de
      su tipo) en los cuatro horizontes. Un escenario por moderador y tipo; las
      otras 20 pruebas de la familia quedan sin efecto.
  H4  a los eventos "con anuncio" se les suma +delta (mas continuacion con
      anuncio, que es la cola de la prueba), en los dos tipos a la vez.

Por que sale casi gratis:
  - H3: el estadistico es el t de un coeficiente de minimos cuadrados. Si a y
    se le suma delta * x_j, con x_j una columna de X, el coeficiente j sube
    exactamente delta y los residuos no cambian, asi que el error agrupado
    tampoco: t(delta) = (beta + delta) / error, sin reajustar nada.
  - H4: pasa lo mismo con la diferencia agrupada, que es una regresion sobre
    la constante y la marca de tratamiento; y la nula sale solo de los minutos
    sorteados, asi que no cambia.
Los tests comprueban las dos cosas contra el calculo directo.

Los mercados usan el calendario de la lista cerrada de anuncios
(ANUNCIOS_SIMULADOS_LISTA_CERRADA). De paso se cuentan los dias tratados por
ano, que dicen si la prueba de H4 llega al minimo de dias, y la prevalencia de
cada moderador.

Uso:
    python -m experimentos.potencia_moderadores --piloto
    python -m experimentos.potencia_moderadores
    python -m experimentos.potencia_moderadores --solo-reporte
"""
import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                              # noqa: E402
import motor                                               # noqa: E402
from experimentos import recursos                          # noqa: E402
from experimentos.control_negativo import (                # noqa: E402
    CARPETA, _en_paralelo, _tabla, intervalo_binomial)
from experimentos.control_positivo import _cruces, _medir  # noqa: E402
from motor import inferencia, moderadores, nula            # noqa: E402
from simulacion import inyeccion, mercado                  # noqa: E402

DESPLAZAMIENTO = 60000
DESPLAZAMIENTO_PILOTO = 95000
PREFIJO = "potencia_moderadores"


def cambios_lista_cerrada(cfg):
    """El unico cambio respecto del mercado de D y E: el calendario de anuncios."""
    return {"ANUNCIOS_SIMULADOS": tuple(cfg.ANUNCIOS_SIMULADOS_LISTA_CERRADA)}


# =============================================================================
#  Un mercado
# =============================================================================
def estadisticos_h3(eventos, cfg):
    """
    Por prueba de FAMILIA_MODERADORES: coeficiente, error agrupado, grupos,
    eventos, eventos con el moderador encendido y desvio del retorno.
    """
    celdas, _ = inferencia.construir_celdas(eventos, cfg)
    filas = []
    for tipo, h, coeficiente, _ in cfg.FAMILIA_MODERADORES:
        fila = {"tipo": tipo, "horizonte": str(h), "coeficiente": coeficiente,
                "beta": np.nan, "error": np.nan, "grupos": 0, "n": 0,
                "n_encendido": 0, "sd_y": np.nan}
        celda = celdas.get((tipo, h, "moderadores"))
        if celda is not None and coeficiente in celda.nombres:
            beta, error, grupos = celda.estimar()
            j = celda.nombres.index(coeficiente)
            fila.update(beta=float(beta[j]), error=float(error[j]), grupos=int(grupos),
                        n=len(celda.y), n_encendido=int(celda.X[:, j].sum()),
                        sd_y=float(np.std(celda.y, ddof=1)))
        filas.append(fila)
    return pd.DataFrame(filas)


def h4_en_grilla(tabla_h4, distribuciones, grilla):
    """
    El p de H4 (estudentizado, una cola "mayor") de cada celda si a los
    eventos con anuncio se les suma delta, para cada delta de la grilla:

        t(delta) = (diferencia + delta) / error,  contra los MISMOS t nulos.

    Se calcula igual que `nula._p_una_cola` (Phipson y Smyth), pero para toda
    la grilla de una vez.
    """
    grilla = np.asarray(grilla, dtype=float)
    filas = []
    for fila in tabla_h4.itertuples(index=False):
        nulas = np.sort(np.asarray(distribuciones.get((fila.tipo, fila.horizonte), []),
                                   dtype=float))
        estimacion = fila.diferencia + grilla
        if len(nulas) and np.isfinite(fila.error) and fila.error > 0:
            t = estimacion / fila.error
            extremas = len(nulas) - np.searchsorted(nulas, t, side="left")
            p = (1.0 + extremas) / (1.0 + len(nulas))
        else:
            p = np.full(len(grilla), np.nan)
        for k, delta in enumerate(grilla):
            filas.append({"tipo": fila.tipo, "horizonte": str(fila.horizonte),
                          "delta": round(float(delta), 6), "p": p[k],
                          "estimacion": estimacion[k], "error": fila.error,
                          "dias_tratados": fila.dias_tratados, "n_con": fila.n_con,
                          "n_sin": fila.n_sin})
    return pd.DataFrame(filas)


def _dias_distintos(fecha, marca):
    """Cuantos dias de Londres distintos tienen al menos un evento marcado."""
    return int(pd.Series(fecha[np.asarray(marca) == 1.0]).nunique())


def conteos_del_mercado(eventos, cal, noticias, cfg, anios):
    """
    Por tipo: eventos por ano, prevalencia de cada moderador y dias tratados
    por ano (distintos dias de Londres con al menos un evento "con anuncio").

    Los dias tratados se dan con la definicion principal ("ventana"), con la
    de robustez ("franja"), por tipo de anuncio y sin los anuncios del BCE (o
    sea con la frecuencia del calendario de los puntos D y E, sobre el mismo
    mercado).
    """
    cfg_franja = config.copia(**{**vars(cfg), "NOTICIA_MODO": "franja"})
    filas = []
    for tipo in ("sostenida", "reingreso"):
        sub = eventos[eventos["tipo"] == tipo]
        t_ns = sub["t_evento_ns"].to_numpy(np.int64)
        pos = sub["pos_franja"].to_numpy(int)
        fecha = pd.DatetimeIndex(sub["fecha_londres"])

        fila = {"tipo": tipo, "eventos_por_anio": len(sub) / anios,
                "tratados_por_anio": float((sub["noticia"] == 1.0).sum()) / anios,
                "dias_tratados": _dias_distintos(fecha, sub["noticia"].to_numpy(float))}
        fila["dias_tratados_por_anio"] = fila["dias_tratados"] / anios
        fila["dias_franja_por_anio"] = _dias_distintos(fecha, moderadores.marcar_noticia(
            t_ns, pos, cal, noticias, cfg_franja)) / anios
        sin_bce = noticias[noticias["tipo"] != "bce"]
        fila["dias_sin_bce_por_anio"] = _dias_distintos(fecha, moderadores.marcar_noticia(
            t_ns, pos, cal, sin_bce, cfg)) / anios
        for anuncio in sorted(noticias["tipo"].unique()):
            fila[f"dias_{anuncio}_por_anio"] = _dias_distintos(fecha, moderadores.marcar_noticia(
                t_ns, pos, cal, noticias[noticias["tipo"] == anuncio], cfg)) / anios
        for nombre in cfg.MODERADORES_PROBADOS:
            valores = sub[nombre].to_numpy(float)
            validos = np.isfinite(valores)
            fila[f"prev_{nombre}"] = float(valores[validos].mean()) if validos.any() else np.nan
        fila["anuncios_por_anio"] = len(noticias) / anios
        filas.append(fila)
    return pd.DataFrame(filas)


def corrida(semilla, anios, cambios, repeticiones):
    """
    Un mercado limpio con el calendario de la lista cerrada. Devuelve
    (h3, h4, conteos): los estadisticos suficientes de H3, el p de H4 en toda
    la grilla y los conteos.
    """
    cfg = config.copia(**cambios)
    datos, noticias = mercado.generar(anios, semilla, cfg)
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
    del datos
    h3 = estadisticos_h3(eventos, cfg)
    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    tabla, distribuciones = nula.correr_h4(barras, cal, eventos, cfg, semilla,
                                           repeticiones=repeticiones, candidatos=candidatos,
                                           con_distribuciones=True)
    h4 = h4_en_grilla(tabla, distribuciones, cfg.GRILLA_POTENCIA_H4)
    conteos = conteos_del_mercado(eventos, cal, noticias, cfg, anios)
    for marco in (h3, h4, conteos):
        marco["mercado"] = semilla
        marco["anios"] = anios
    return h3, h4, conteos


def _tarea(argumentos):
    return corrida(*argumentos)


# =============================================================================
#  Cuentas de potencia
# =============================================================================
def p_dos_colas_t(t, grupos):
    """El p de dos colas de un t con grupos - 1 grados de libertad (como la regresion)."""
    t = np.asarray(t, dtype=float)
    gl = np.maximum(np.asarray(grupos, dtype=float) - 1.0, 1.0)
    salida = np.full(t.shape, np.nan)
    hay = np.isfinite(t)
    salida[hay] = 2.0 * stats.t.sf(np.abs(t[hay]), df=np.broadcast_to(gl, t.shape)[hay])
    return salida


def holm_por_filas(p):
    """
    `inferencia.holm` aplicado a cada fila de una matriz. Los NaN no ocupan
    lugar en la familia de su fila.
    """
    p = np.atleast_2d(np.asarray(p, dtype=float))
    finito = np.isfinite(p)
    m = finito.sum(axis=1, keepdims=True)
    orden = np.argsort(np.where(finito, p, np.inf), axis=1, kind="stable")
    ordenados = np.take_along_axis(np.where(finito, p, 0.0), orden, axis=1)
    paso = np.arange(p.shape[1])[None, :]
    factor = np.maximum(m - paso, 0)
    ajustados = np.maximum.accumulate(np.minimum(factor * ordenados, 1.0), axis=1)
    salida = np.full(p.shape, np.nan)
    np.put_along_axis(salida, orden, ajustados, axis=1)
    return np.where(finito, salida, np.nan)


def _matriz(tabla, llaves, columna, mercados):
    """Tabla larga -> matriz mercado x prueba, en el orden de `llaves`."""
    indice = pd.MultiIndex.from_tuples([(m,) + tuple(llave) for m in mercados for llave in llaves])
    serie = tabla.set_index(["mercado", "tipo", "horizonte", "coeficiente"])[columna]
    return serie.reindex(indice).to_numpy(float).reshape(len(mercados), len(llaves))


def rechazos_h3(h3, cfg):
    """
    Rechazos de H3 por escenario. En cada escenario solo el moderador `mod` en
    el tipo `tipo` tiene efecto (en sus cuatro horizontes); se corrige con Holm
    sobre las 24 pruebas y cuenta el rechazo con el signo correcto.

    Devuelve (rechazos, tamano):
      rechazos  (moderador, tipo, horizonte) -> matriz mercado x delta (0/1)
      tamano    en delta = 0: tasa por prueba (p bruto <= ALFA) y por familia
                (algun rechazo de Holm), con el calculo de los mercados.
    """
    familia = [(t, str(h), c) for t, h, c, _ in cfg.FAMILIA_MODERADORES]
    mercados = sorted(h3["mercado"].unique())
    beta = _matriz(h3, familia, "beta", mercados)
    error = _matriz(h3, familia, "error", mercados)
    grupos = _matriz(h3, familia, "grupos", mercados)
    signo = inyeccion.signos(cfg)
    s = np.array([signo[t] for t, _, _ in familia], dtype=float)
    grilla = np.asarray(cfg.GRILLA_POTENCIA_H3, dtype=float)

    with np.errstate(invalid="ignore", divide="ignore"):
        p0 = p_dos_colas_t(beta / error, grupos)
    holm0 = holm_por_filas(p0)
    finitos = p0[np.isfinite(p0)]
    tamano = {"pruebas": len(finitos), "mercados": len(mercados),
              "por_prueba": float((finitos <= cfg.ALFA).mean()) if len(finitos) else np.nan,
              "familia": float(np.mean(np.nan_to_num(holm0, nan=1.0).min(axis=1) <= cfg.ALFA))}

    rechazos = {}
    for mod in cfg.MODERADORES_PROBADOS:
        for tipo in ("sostenida", "reingreso"):
            en = np.array([t == tipo and c == mod for t, _, c in familia])
            matriz = np.zeros((len(mercados), len(grilla), int(en.sum())))
            for k, delta in enumerate(grilla):
                estimacion = beta + delta * s * en
                with np.errstate(invalid="ignore", divide="ignore"):
                    p = p_dos_colas_t(estimacion / error, grupos)
                ph = holm_por_filas(p)
                bien = np.sign(estimacion) == s
                matriz[:, k, :] = (np.isfinite(ph) & (ph <= cfg.ALFA) & bien)[:, en]
            horizontes = [h for (t, h, c), e in zip(familia, en) if e]
            for j, h in enumerate(horizontes):
                rechazos[(mod, tipo, h)] = pd.DataFrame(matriz[:, :, j], index=mercados,
                                                        columns=grilla)
    return rechazos, tamano


def rechazos_h4(h4, cfg):
    """
    Rechazos de H4 con el efecto en los eventos con anuncio de los dos tipos.
    Entran a la familia solo las pruebas con MIN_DIAS_TRATADOS dias tratados o
    mas; Holm sobre las que entran, a ALFA, con el signo correcto.

    Devuelve (rechazos, entra, tamano): rechazos (tipo, horizonte) -> matriz
    mercado x delta; entra (tipo, horizonte) -> proporcion de mercados en que
    la prueba entra a la familia; tamano en delta = 0.
    """
    celdas = [(t, str(h)) for t, h, _, _ in cfg.FAMILIA_H4]
    mercados = sorted(h4["mercado"].unique())
    grilla = np.asarray(sorted(h4["delta"].unique()), dtype=float)
    tabla = h4.set_index(["mercado", "delta", "tipo", "horizonte"])
    indice = pd.MultiIndex.from_tuples([(m, d) + c for m in mercados for d in grilla
                                        for c in celdas])
    forma = (len(mercados), len(grilla), len(celdas))
    p = tabla["p"].reindex(indice).to_numpy(float).reshape(forma)
    estimacion = tabla["estimacion"].reindex(indice).to_numpy(float).reshape(forma)
    dias = tabla["dias_tratados"].reindex(indice).to_numpy(float).reshape(forma)

    entra = (dias >= cfg.MIN_DIAS_TRATADOS) & np.isfinite(p)
    p_familia = np.where(entra, p, np.nan)
    ph = holm_por_filas(p_familia.reshape(-1, len(celdas))).reshape(forma)
    rechaza = np.isfinite(ph) & (ph <= cfg.ALFA) & (estimacion > 0)

    rechazos = {c: pd.DataFrame(rechaza[:, :, j].astype(float), index=mercados, columns=grilla)
                for j, c in enumerate(celdas)}
    proporcion = {c: float(entra[:, 0, j].mean()) for j, c in enumerate(celdas)}
    cero = int(np.flatnonzero(np.isclose(grilla, 0.0))[0])
    en_familia = entra[:, cero, :]
    tamano = {"mercados": len(mercados), "pruebas": int(en_familia.sum()),
              "por_prueba": float((p[:, cero, :][en_familia] <= cfg.ALFA).mean())
              if en_familia.any() else np.nan,
              "familia": float((np.nan_to_num(ph[:, cero, :], nan=1.0).min(axis=1)
                                <= cfg.ALFA).mean())}
    return rechazos, proporcion, tamano


def efecto_minimo_con_ic(rechazos, objetivo, remuestreos, semilla):
    """
    Efecto minimo detectable con su intervalo al 95%, remuestreando MERCADOS.

    Hace lo mismo que `control_positivo.efecto_minimo_con_ic`, pero en vez de
    armar la matriz remuestreo x mercado x delta (que con grillas largas no
    cabe en memoria) sortea cuantas veces entra cada mercado y promedia con
    esos pesos. Un remuestreo cuya curva no llega cuenta como "mas alla de la
    grilla": si son mas del 2,5%, el borde alto queda infinito.

    Devuelve (efecto, bajo, alto).
    """
    deltas = np.asarray(rechazos.columns, dtype=float)
    orden = np.argsort(deltas)
    deltas = deltas[orden]
    matriz = rechazos.to_numpy(float)[:, orden]
    n = len(matriz)
    efecto = _cruces(deltas, matriz.mean(axis=0), objetivo)[0]
    rng = np.random.default_rng(semilla)
    pesos = rng.multinomial(n, np.full(n, 1.0 / n), size=remuestreos)
    curvas = pesos @ matriz / n
    cruces = np.sort(np.nan_to_num(_cruces(deltas, curvas, objetivo), nan=np.inf))
    ultimo = len(cruces) - 1
    return (float(efecto), float(cruces[int(np.floor(0.025 * ultimo))]),
            float(cruces[int(np.ceil(0.975 * ultimo))]))


def mde_aproximado(sd, n_con, n_sin, alfa, pruebas, colas, potencia):
    """
    Aproximacion normal del efecto minimo detectable de una DIFERENCIA entre
    subgrupos:

        (z(1 - alfa / (pruebas * colas)) + z(potencia)) * sd * raiz(1/n_con + 1/n_sin)

    Con `pruebas` = tamano de la familia es la cota de Bonferroni (el primer
    paso de Holm, lo mas exigente); con `pruebas` = 1, la prueba sin corregir.
    Supone eventos independientes dentro de cada subgrupo (en la muestra
    simulada hay algo mas de un evento por dia).
    """
    if not (n_con > 0 and n_sin > 0 and np.isfinite(sd)):
        return np.nan
    z = stats.norm.isf(alfa / (pruebas * colas)) + stats.norm.ppf(potencia)
    return float(z * sd * np.sqrt(1.0 / n_con + 1.0 / n_sin))


# =============================================================================
#  Etapas
# =============================================================================
def piloto(repeticiones):
    """Mide tiempo y memoria de MERCADOS_PILOTO mercados, cada uno en un proceso nuevo."""
    cfg = config.copia()
    print(recursos.describir())
    cambios = cambios_lista_cerrada(cfg)
    anios = cfg.ANIOS_POTENCIA_MODERADORES
    medidas = []
    for k in range(cfg.MERCADOS_PILOTO):
        semilla = cfg.SEMILLA + DESPLAZAMIENTO_PILOTO + k
        _, pico, segundos = _medir(_tarea, (semilla, anios, cambios, repeticiones),
                                   f"Piloto: mercado {k + 1} de {cfg.MERCADOS_PILOTO}, "
                                   f"{anios} anos...")
        medidas.append({"mercado": semilla, "anios": anios, "segundos": segundos,
                        "pico_gb": pico})
    medidas = pd.DataFrame(medidas)
    os.makedirs(CARPETA, exist_ok=True)
    medidas.to_csv(os.path.join(CARPETA, f"{PREFIJO}_piloto.csv"), index=False)
    estimacion = estimar(medidas, cfg)
    texto = "\n".join([
        "# Potencia de H3 y H4: piloto\n",
        f"- {cfg.MERCADOS_PILOTO} mercados de {anios} anos, calendario de la lista cerrada, "
        f"{repeticiones} repeticiones de la nula de H4.",
        f"- Equipo: {recursos.describir()}.\n",
        _tabla(medidas.round(2)), "",
        f"**Estimacion de la corrida completa**: {estimacion['mercados']} mercados, "
        f"{estimacion['procesos']} procesos, ~{estimacion['minutos']:.0f} minutos.",
    ])
    with open(os.path.join(CARPETA, f"{PREFIJO}_piloto.md"), "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(texto)
    return estimacion


def estimar(medidas, cfg, fraccion=0.70):
    """Minutos de la corrida completa con los procesos que caben en la memoria."""
    segundos = float(medidas["segundos"].mean())
    procesos = recursos.procesos_que_caben(float(medidas["pico_gb"].max()), fraccion=fraccion)
    mercados = cfg.MERCADOS_POTENCIA_MODERADORES
    return {"segundos_por_mercado": segundos, "procesos": procesos, "mercados": mercados,
            "minutos": mercados * segundos / procesos / 60}


def main_corrida(procesos, repeticiones):
    cfg = config.copia()
    cambios = cambios_lista_cerrada(cfg)
    anios = cfg.ANIOS_POTENCIA_MODERADORES
    trabajos = [(cfg.SEMILLA + DESPLAZAMIENTO + k, anios, cambios, repeticiones)
                for k in range(cfg.MERCADOS_POTENCIA_MODERADORES)]
    print(f"{len(trabajos)} mercados de {anios} anos con {procesos} procesos "
          f"({recursos.describir()})", flush=True)
    comienzo = time.perf_counter()
    salidas = _en_paralelo(_tarea, trabajos, procesos)
    minutos = (time.perf_counter() - comienzo) / 60
    h3 = pd.concat([s[0] for s in salidas], ignore_index=True)
    h4 = pd.concat([s[1] for s in salidas], ignore_index=True)
    conteos = pd.concat([s[2] for s in salidas], ignore_index=True)
    os.makedirs(CARPETA, exist_ok=True)
    h3.to_csv(os.path.join(CARPETA, f"{PREFIJO}_h3.csv"), index=False, float_format="%.6g")
    h4.to_csv(os.path.join(CARPETA, f"{PREFIJO}_h4.csv"), index=False, float_format="%.6g")
    conteos.to_csv(os.path.join(CARPETA, f"{PREFIJO}_conteos.csv"), index=False,
                   float_format="%.6g")
    pd.DataFrame([{"minutos": minutos, "repeticiones": repeticiones, "procesos": procesos}]) \
        .to_csv(os.path.join(CARPETA, f"{PREFIJO}_meta.csv"), index=False)
    reporte()


def _leer(nombre):
    return pd.read_csv(os.path.join(CARPETA, f"{PREFIJO}_{nombre}.csv"),
                       dtype={"horizonte": str})


def reporte():
    cfg = config.copia()
    texto = markdown(_leer("h3"), _leer("h4"), _leer("conteos"), _leer("meta"), cfg)
    with open(os.path.join(CARPETA, f"{PREFIJO}.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


# =============================================================================
#  Reporte
# =============================================================================
def _intervalo(efecto, bajo, alto):
    if not np.isfinite(efecto):
        return "no llega en la grilla"
    alto_txt = "fuera de la grilla" if not np.isfinite(alto) else f"{alto:.3f}"
    return f"{efecto:.3f} [{bajo:.3f}; {alto_txt}]"


def tabla_conteos(conteos, cfg):
    """Dias tratados y conteos por tipo, promedio entre mercados."""
    anios = int(conteos["anios"].iloc[0])
    filas = []
    for tipo, bloque in conteos.groupby("tipo", sort=False):
        dias = bloque["dias_tratados"]
        filas.append({
            "tipo": tipo,
            "eventos/ano": round(bloque["eventos_por_anio"].mean(), 1),
            "dias tratados/ano (ventana)": round(bloque["dias_tratados_por_anio"].mean(), 2),
            "sin BCE (calendario D/E)": round(bloque["dias_sin_bce_por_anio"].mean(), 2),
            f"en {anios} anos: media [min-max]": f"{dias.mean():.1f} [{dias.min():.0f}-{dias.max():.0f}]",
            f"mercados con >= {cfg.MIN_DIAS_TRATADOS}": f"{(dias >= cfg.MIN_DIAS_TRATADOS).mean():.0%}",
            "dias/ano modo franja": round(bloque["dias_franja_por_anio"].mean(), 1),
        })
    return pd.DataFrame(filas)


def markdown(h3, h4, conteos, meta, cfg):
    remuestreos, semilla = cfg.REMUESTREOS_IC_MERCADOS, cfg.SEMILLA
    anios = int(conteos["anios"].iloc[0])
    mercados = conteos["mercado"].nunique()
    partes = [
        "# Potencia de H3 y H4, dias tratados y prevalencias (punto F)\n",
        f"- {mercados} mercados de {anios} anos, sin ningun patron, con el calendario de la "
        f"lista cerrada ({conteos['anuncios_por_anio'].mean():.0f} anuncios por ano: "
        f"{', '.join(cfg.ANUNCIOS_SIMULADOS_LISTA_CERRADA)}).",
        f"- Nula de H4 con {int(meta['repeticiones'].iloc[0])} repeticiones; "
        f"{float(meta['minutos'].iloc[0]):.1f} minutos con {int(meta['procesos'].iloc[0])} procesos.",
        f"- Efecto minimo detectable al {cfg.POTENCIA_OBJETIVO:.0%} de potencia, en unidades de "
        f"retorno normalizado, con IC95 remuestreando mercados ({remuestreos} remuestreos).",
        "- Mismo principio que el diseno D: el efecto se suma al retorno normalizado del "
        "subgrupo, sobre el mercado limpio.\n",
        "## 1. Dias tratados por ano (factibilidad de H4)\n",
        _tabla(tabla_conteos(conteos, cfg)), "",
        "Por tipo de anuncio (dias por ano con un anuncio de ese tipo en la ventana; un dia "
        "puede contar en dos tipos):\n",
    ]
    columnas = [c for c in conteos.columns if c.startswith("dias_") and c.endswith("_por_anio")
                and c not in ("dias_tratados_por_anio", "dias_franja_por_anio",
                              "dias_sin_bce_por_anio")]
    por_anuncio = conteos.groupby("tipo", sort=False)[columnas].mean().round(2)
    por_anuncio.columns = [c[len("dias_"):-len("_por_anio")] for c in columnas]
    partes += [_tabla(por_anuncio.reset_index()), ""]

    prev = conteos.groupby("tipo", sort=False)[[f"prev_{m}" for m in cfg.MODERADORES_PROBADOS]] \
        .mean().round(3)
    prev.columns = list(cfg.MODERADORES_PROBADOS)
    partes += ["## 2. Prevalencia de los moderadores (proporcion de eventos con el moderador "
               "encendido)\n", _tabla(prev.reset_index()), ""]

    # --- H3 ---------------------------------------------------------------------
    rechazos, tamano = rechazos_h3(h3, cfg)
    filas = []
    for (mod, tipo, h), matriz in rechazos.items():
        efecto, bajo, alto = efecto_minimo_con_ic(matriz, cfg.POTENCIA_OBJETIVO, remuestreos,
                                                  semilla)
        celda = h3[(h3["coeficiente"] == mod) & (h3["tipo"] == tipo) & (h3["horizonte"] == h)]
        n1 = celda["n_encendido"].median()
        n0 = (celda["n"] - celda["n_encendido"]).median()
        sd = celda["sd_y"].median()
        m = len(cfg.FAMILIA_MODERADORES)
        filas.append({
            "moderador": mod, "tipo": tipo, "horizonte": h,
            "n encendido (mediana)": int(n1),
            "simulado [IC95]": _intervalo(efecto, bajo, alto),
            f"aprox. Bonferroni {m}": round(mde_aproximado(sd, n1, n0, cfg.ALFA, m, 2,
                                                           cfg.POTENCIA_OBJETIVO), 3),
            "aprox. sin corregir": round(mde_aproximado(sd, n1, n0, cfg.ALFA, 1, 2,
                                                        cfg.POTENCIA_OBJETIVO), 3),
        })
    partes += [
        "## 3. H3: efecto minimo detectable por celda\n",
        f"Escenario: solo el moderador y el tipo de la fila tienen efecto (en sus cuatro "
        f"horizontes); Holm sobre las {len(cfg.FAMILIA_MODERADORES)} pruebas, dos colas, "
        f"alfa {cfg.ALFA}; cuenta el rechazo con el signo correcto. La aproximacion usa "
        "los conteos y el desvio del retorno de la celda (medianas entre mercados).\n",
        _tabla(pd.DataFrame(filas)), "",
        f"Tamano en delta = 0 ({tamano['mercados']} mercados, {tamano['pruebas']} pruebas): "
        f"tasa por prueba {tamano['por_prueba']:.3f}; mercados con algun rechazo de Holm "
        f"{tamano['familia']:.3f} "
        f"(IC95 {_wilson(tamano['familia'], tamano['mercados'])}).\n",
    ]

    # --- H4 ---------------------------------------------------------------------
    rechazos4, entra, tamano4 = rechazos_h4(h4, cfg)
    cero = h4[np.isclose(h4["delta"], 0.0)]
    filas = []
    for (tipo, h), matriz in rechazos4.items():
        efecto, bajo, alto = efecto_minimo_con_ic(matriz, cfg.POTENCIA_OBJETIVO, remuestreos,
                                                  semilla)
        celda = cero[(cero["tipo"] == tipo) & (cero["horizonte"] == h)]
        sd = h3[(h3["tipo"] == tipo) & (h3["horizonte"] == h)]["sd_y"].median()
        pruebas = max(1, int(round(sum(entra.values()))))
        filas.append({
            "tipo": tipo, "horizonte": h,
            "dias tratados (mediana)": int(celda["dias_tratados"].median()),
            "entra a la familia": f"{entra[(tipo, h)]:.0%}",
            "simulado [IC95]": _intervalo(efecto, bajo, alto),
            f"aprox. Bonferroni {pruebas}": round(mde_aproximado(
                sd, celda["n_con"].median(), celda["n_sin"].median(), cfg.ALFA, pruebas, 1,
                cfg.POTENCIA_OBJETIVO), 3),
            "aprox. sin corregir": round(mde_aproximado(
                sd, celda["n_con"].median(), celda["n_sin"].median(), cfg.ALFA, 1, 1,
                cfg.POTENCIA_OBJETIVO), 3),
        })
    partes += [
        "## 4. H4: efecto minimo detectable por celda\n",
        f"Escenario: los eventos con anuncio de los dos tipos tienen +delta. Entran a la "
        f"familia solo las pruebas con {cfg.MIN_DIAS_TRATADOS} dias tratados o mas (en cada "
        f"mercado); Holm sobre las que entran, una cola, alfa {cfg.ALFA}. Una prueba que no "
        "entra no rechaza nunca, asi que su potencia tiene como techo la proporcion de "
        "mercados en que entra. La aproximacion usa como tamano de familia el numero medio "
        "de pruebas que entran.\n",
        _tabla(pd.DataFrame(filas)), "",
        f"Tamano en delta = 0 ({tamano4['mercados']} mercados, {tamano4['pruebas']} pruebas "
        f"en familia): tasa por prueba {tamano4['por_prueba']:.3f}; mercados con algun "
        f"rechazo de Holm {tamano4['familia']:.3f} "
        f"(IC95 {_wilson(tamano4['familia'], tamano4['mercados'])}).\n",
        "## Advertencias\n",
        "- Todo depende del simulador: volatilidad de 7%, anuncios que triplican la "
        "volatilidad durante 5 minutos sin empujar el precio y un regimen AR(1) diario. En "
        "datos reales los eventos cerca de anuncios seran mas volatiles y mas frecuentes, "
        "asi que los dias tratados de aqui son un orden de magnitud, no una prediccion.",
        "- El efecto es una constante sumada al subgrupo (diseno D); no reproduce lo que un "
        "mecanismo de precio le haria a las celdas.",
    ]
    return "\n".join(partes) + "\n"


def _wilson(tasa, n):
    bajo, alto = intervalo_binomial(int(round(tasa * n)), n)
    return f"[{bajo:.3f}, {alto:.3f}]"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--piloto", action="store_true")
    parser.add_argument("--solo-reporte", action="store_true")
    parser.add_argument("--procesos", type=int, default=None)
    args = parser.parse_args()
    repeticiones = config.NULA_REPETICIONES_POTENCIA
    if args.solo_reporte:
        reporte()
    elif args.piloto:
        piloto(repeticiones)
    else:
        # Los procesos salen del pico de memoria medido en el piloto, que se
        # corre antes; sin piloto hay que decirlo a mano con --procesos.
        procesos = args.procesos
        if procesos is None:
            medidas = _leer("piloto")
            procesos = estimar(medidas, config.copia())["procesos"]
        main_corrida(procesos, repeticiones)


if __name__ == "__main__":
    main()
