# -*- coding: utf-8 -*-
"""
RUPTURAS — que franjas pueden romper y donde rompen.

Es la primera mitad de la deteccion de eventos, separada de `eventos.py` en el
punto G para que el control de calidad de los datos reales pueda detectar
rupturas sin importar `resultados` (ni, a traves de el, nada que mida retornos
posteriores). `eventos.detectar` usa estas mismas funciones, asi que la ruptura
que ve el control de calidad es por construccion la misma que ve el analisis.

Aqui no hay sigma_ref: `franjas_con_referencia` es la mascara de
`eventos.franjas_utilizables` sin la condicion de sigma_ref, que vive en
`resultados`. El umbral en modo "vol" si necesita sigma_ref, y lo recibe como
argumento.

Las reglas (ver `eventos.py`):
  - la referencia de la franja k es la k-1: H = maximo de mid_high y L = minimo
    de mid_low;
  - la ruptura es la primera barra de k cuyo mid_high supera H + umbral
    (alcista) o cuyo mid_low baja de L - umbral (bajista);
  - si esa primera barra rompe los dos lados, la franja es ambigua y, con
    EXCLUIR_BARRA_AMBIGUA, no genera eventos.
"""
import numpy as np
import pandas as pd

from . import tiempo

COLUMNAS = ["pos_franja", "fecha_londres", "idx_franja", "direccion", "ambigua",
            "t_ruptura_utc", "t_ruptura_ns"]


def umbrales(cfg, sigma_k, H, L):
    """
    Cuanto hay que penetrar el extremo para que cuente como ruptura.

    En modo "pips" es una distancia fija. En modo "vol" es proporcional a la
    volatilidad de referencia y al propio extremo:
        umbral = UMBRAL_VOL * sigma_ref * extremo
    El extremo (H o L) es 100% pasado, asi que el umbral tambien lo es.
    """
    if cfg.UMBRAL_MODO == "pips":
        u = cfg.UMBRAL_PIPS * cfg.PIP
        return u, u
    if cfg.UMBRAL_MODO == "vol":
        return cfg.UMBRAL_VOL * sigma_k * H, cfg.UMBRAL_VOL * sigma_k * L
    raise ValueError(f"UMBRAL_MODO desconocido: {cfg.UMBRAL_MODO}")


def primera(mascara):
    """Posicion del primer True, o -1 si no hay ninguno."""
    return int(np.argmax(mascara)) if mascara.any() else -1


def primera_ruptura(mid_h, mid_l, H, L, u_alc, u_baj, cfg):
    """
    La ruptura de una franja: (posicion, direccion, ambigua).

    Devuelve (-1, 0, False) si no rompe. Si la primera barra que rompe, rompe
    los dos lados, devuelve (posicion, 0, True) cuando EXCLUIR_BARRA_AMBIGUA es
    True; si no, desempata por el lado que penetro mas, medido en veces el
    umbral de ese lado.
    """
    i_alc = primera(mid_h > H + u_alc)
    i_baj = primera(mid_l < L - u_baj)
    if i_alc < 0 and i_baj < 0:
        return -1, 0, False

    if i_alc >= 0 and i_alc == i_baj:
        # La misma barra rompe los dos lados.
        if cfg.EXCLUIR_BARRA_AMBIGUA:
            return i_alc, 0, True
        # Desempate declarado: gana el lado que penetro mas, medido en
        # veces el umbral de ese lado. Solo se usa si el grupo decide
        # apagar EXCLUIR_BARRA_AMBIGUA.
        penetra_alc = (mid_h[i_alc] - H) / u_alc if u_alc > 0 else np.inf
        penetra_baj = (L - mid_l[i_baj]) / u_baj if u_baj > 0 else np.inf
        direccion = 1 if penetra_alc >= penetra_baj else -1
    elif i_baj < 0 or (0 <= i_alc < i_baj):
        direccion = 1
    else:
        direccion = -1
    return (i_alc if direccion == 1 else i_baj), direccion, False


def franjas_con_referencia(cal, cfg):
    """
    Mascara sobre las filas del calendario: franjas con una referencia valida.

    Es `eventos.franjas_utilizables` sin la condicion de sigma_ref: hay franja
    anterior, esa referencia cumple COBERTURA_MIN_REFERENCIA, la franja tiene
    barras y, si REFERENCIA_CRUZA_CIERRE es False, no hay un cierre de mercado
    entre la referencia y la franja ni la referencia empezo con el mercado
    cerrado.
    """
    n = len(cal)
    cobertura = cal["cobertura"].to_numpy(float)
    H_ref = cal["H"].to_numpy(float)
    L_ref = cal["L"].to_numpy(float)
    i0_col = cal["i0"].to_numpy()
    i1_col = cal["i1"].to_numpy()
    sesion_col = cal["sesion"].to_numpy()
    hueco_col = cal["hueco_inicial"].to_numpy(float)

    k = np.arange(n)
    hay_referencia = k >= 1
    ref = np.maximum(k - 1, 0)
    sirve = (
        hay_referencia
        & (cobertura[ref] >= cfg.COBERTURA_MIN_REFERENCIA)
        & (i1_col > i0_col)
        & np.isfinite(H_ref[ref]) & np.isfinite(L_ref[ref])
    )
    if not cfg.REFERENCIA_CRUZA_CIERRE:
        # Dos condiciones, y hacen falta las dos:
        #  - la referencia y la franja k comparten sesion. Como las sesiones van
        #    en aumento, eso descarta cualquier cierre ENTRE una y otra.
        #  - la referencia no empezo con el mercado cerrado. Es el caso del
        #    domingo por la tarde: la franja figura, pero sus datos parten
        #    recien cuando el mercado abre, ya avanzada la franja.
        sirve &= sesion_col[ref] == sesion_col
        sirve &= sesion_col >= 0
        sirve &= hueco_col[ref] <= cfg.HUECO_CIERRE_MIN
    return sirve


def detectar(barras, cal, cfg, mascara=None, sigma=None):
    """
    Solo la ruptura de cada franja: si hay, su direccion y su minuto.

    Una fila por franja de `mascara` (por defecto, `franjas_con_referencia`).
    `direccion` vale +1, -1 o 0 (sin ruptura o ambigua); `ambigua` marca la
    franja cuya primera barra que rompe, rompe los dos lados. `t_ruptura_ns` es
    el CIERRE de la barra que rompe (-1 si no hay ruptura).

    `sigma` (una por fila del calendario) solo hace falta con UMBRAL_MODO "vol".
    """
    if mascara is None:
        mascara = franjas_con_referencia(cal, cfg)
    if cfg.UMBRAL_MODO != "pips" and sigma is None:
        raise ValueError("con UMBRAL_MODO distinto de 'pips' hace falta sigma")

    H_ref = cal["H"].to_numpy(float)
    L_ref = cal["L"].to_numpy(float)
    i0_col = cal["i0"].to_numpy()
    i1_col = cal["i1"].to_numpy()

    filas = []
    for k in np.flatnonzero(mascara):
        H, L = H_ref[k - 1], L_ref[k - 1]
        i0, i1 = i0_col[k], i1_col[k]
        sigma_k = np.nan if sigma is None else sigma[k]
        u_alc, u_baj = umbrales(cfg, sigma_k, H, L)
        i_rup, direccion, ambigua = primera_ruptura(
            barras.mid_h[i0:i1], barras.mid_l[i0:i1], H, L, u_alc, u_baj, cfg)
        t_rup = int(barras.cierre_ns[i0 + i_rup]) if (direccion != 0) else -1
        filas.append((int(k), direccion, ambigua, t_rup))

    tabla = pd.DataFrame(filas, columns=["pos_franja", "direccion", "ambigua", "t_ruptura_ns"])
    tabla["fecha_londres"] = cal["fecha_londres"].to_numpy()[tabla["pos_franja"].to_numpy(int)]
    tabla["idx_franja"] = cal["idx_franja"].to_numpy()[tabla["pos_franja"].to_numpy(int)]
    t_ns = tabla["t_ruptura_ns"].to_numpy(np.int64)
    # El entero mas chico de int64 es NaT: las franjas sin ruptura quedan sin hora.
    tabla["t_ruptura_utc"] = tiempo.de_ns(np.where(t_ns >= 0, t_ns, np.iinfo(np.int64).min))
    return tabla[COLUMNAS]
