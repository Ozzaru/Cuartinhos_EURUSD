# -*- coding: utf-8 -*-
"""
EVENTOS — deteccion de ruptura, ruptura sostenida y reingreso.

Para cada franja k se miran los extremos de la franja anterior, la k-1:
H = maximo de mid_high y L = minimo de mid_low. Esos dos numeros son 100%
pasado durante toda la franja k, porque la franja k-1 ya cerro.

Los tres tipos de evento, todos con su instante conocido en el momento:

  ruptura    primera barra de la franja k cuyo mid_high supera H + umbral
             (alcista) o cuyo mid_low baja de L - umbral (bajista). El evento
             ocurre en el CIERRE de esa barra.

  sostenida  la ruptura aguanta M minutos. El evento ocurre en t_ruptura + M,
             y en ese instante ya se sabe todo lo necesario para declararlo.
             Esto es distinto de "una ruptura que nunca se devolvio", que
             exigiria conocer el futuro hasta el fin de la muestra.
             Exige la barra EXACTA que cierra en t_ruptura + M: si falta, no
             hay evento.

  reingreso  primera barra posterior a la ruptura cuyo mid_close vuelve a
             cruzar el extremo hacia adentro. El evento ocurre en el cierre de
             esa barra.

Cada franja produce como maximo un evento de cada tipo. La direccion (+1
alcista, -1 bajista) la fija la ruptura y la heredan los otros dos.

Que descarta una franja, y por que:
  - la franja k-1 no llega a COBERTURA_MIN_REFERENCIA: sus extremos no son
    confiables;
  - entre la franja k-1 y la k hubo un cierre de mercado, o la propia franja
    k-1 empezo con el mercado cerrado, y REFERENCIA_CRUZA_CIERRE es False: el
    precio de referencia quedo del otro lado del fin de semana;
  - no hay sigma_ref: sin la vara para normalizar, el resultado no es
    comparable con los demas;
  - la primera barra que rompe, rompe los dos lados a la vez y
    EXCLUIR_BARRA_AMBIGUA es True: no hay forma honesta de asignarle direccion.

A la franja EN CURSO nunca se le exige cobertura. En el instante t no se sabe
si mas adelante habra huecos de datos, asi que exigirlo seria mirar el futuro.
"""
import numpy as np
import pandas as pd

from . import resultados, rupturas, tiempo

COLUMNAS = ["id_franja", "fecha_londres", "idx_franja", "tipo", "direccion",
            "t_evento_utc", "t_ruptura_utc", "extremo_roto", "precio_evento",
            "dia_semana", "pos_franja", "t_evento_ns", "t_ruptura_ns", "sigma_ref"]


def franjas_utilizables(cal, sigma, cfg):
    """
    Mascara sobre las filas del calendario: que franjas pueden generar eventos.

    Es la misma condicion que usa la hipotesis nula para decidir de que minutos
    se puede sortear. Vive en una sola funcion justamente para que las dos
    cosas no se separen nunca.

    Desde el punto G se arma en dos partes: la referencia valida
    (`rupturas.franjas_con_referencia`, que tambien usa el control de calidad)
    y la sigma_ref finita, que es lo unico que depende de `resultados`.
    """
    return rupturas.franjas_con_referencia(cal, cfg) & np.isfinite(sigma)


def detectar(barras, cal, cfg, sigma=None):
    """
    Devuelve el DataFrame de eventos, ordenado por instante del evento.

    `sigma` se puede pasar ya calculado para no repetir el trabajo; si no,
    se calcula aqui con `resultados.sigma_por_franja`.
    """
    if sigma is None:
        sigma = resultados.sigma_por_franja(barras, cal, cfg)

    H_ref = cal["H"].to_numpy(float)
    L_ref = cal["L"].to_numpy(float)
    i0_col = cal["i0"].to_numpy()
    i1_col = cal["i1"].to_numpy()
    fin_ns_col = cal["fin_ns"].to_numpy(np.int64)
    fecha_col = cal["fecha_londres"].to_numpy()
    idx_col = cal["idx_franja"].to_numpy()
    dia_col = cal["dia_semana"].to_numpy()

    filas = []
    for k in np.flatnonzero(franjas_utilizables(cal, sigma, cfg)):
        ref = k - 1
        H, L = H_ref[ref], L_ref[ref]
        i0, i1 = i0_col[k], i1_col[k]
        mid_h = barras.mid_h[i0:i1]
        mid_l = barras.mid_l[i0:i1]
        mid_c = barras.mid_c[i0:i1]
        cierre = barras.cierre_ns[i0:i1]

        u_alc, u_baj = rupturas.umbrales(cfg, sigma[k], H, L)
        i_rup, direccion, ambigua = rupturas.primera_ruptura(mid_h, mid_l, H, L,
                                                             u_alc, u_baj, cfg)
        if direccion == 0:
            continue                       # no rompe, o la barra es ambigua

        extremo = H if direccion == 1 else L
        t_rup = int(cierre[i_rup])

        base = {
            "id_franja": f"{pd.Timestamp(fecha_col[k]).date()}_{idx_col[k]}",
            "fecha_londres": fecha_col[k],
            "idx_franja": int(idx_col[k]),
            "direccion": int(direccion),
            "t_ruptura_utc": tiempo.de_ns(t_rup),
            "t_ruptura_ns": t_rup,
            "extremo_roto": float(extremo),
            "dia_semana": int(dia_col[k]),
            "pos_franja": int(k),
            "sigma_ref": float(sigma[k]),
        }

        # --- ruptura ---------------------------------------------------------
        filas.append({**base, "tipo": "ruptura", "t_evento_ns": t_rup,
                      "t_evento_utc": tiempo.de_ns(t_rup),
                      "precio_evento": float(mid_c[i_rup])})

        # "dentro" = el mid_close volvio al otro lado del extremo.
        dentro = mid_c < H if direccion == 1 else mid_c > L

        # --- reingreso -------------------------------------------------------
        limite = t_rup + cfg.VENTANA_REINGRESO_MIN * tiempo.NS_MIN \
            if cfg.VENTANA_REINGRESO_MIN is not None else cierre[-1]
        posterior = np.zeros(len(mid_c), dtype=bool)
        posterior[i_rup + 1:] = True
        candidatas = dentro & posterior & (cierre <= limite)
        i_re = rupturas.primera(candidatas)
        if i_re >= 0:
            filas.append({**base, "tipo": "reingreso", "t_evento_ns": int(cierre[i_re]),
                          "t_evento_utc": tiempo.de_ns(int(cierre[i_re])),
                          "precio_evento": float(mid_c[i_re])})

        # --- sostenida -------------------------------------------------------
        t_sost = t_rup + cfg.M_SOSTENIDA_MIN * tiempo.NS_MIN
        if t_sost > fin_ns_col[k]:
            continue                       # el plazo se pasa del fin de la franja
        # Se exige la barra EXACTA que cierra en t + M, sin tolerancia: declarar
        # que una ruptura aguanto es afirmar algo sobre ese instante preciso.
        # La tolerancia de TOLERANCIA_PRECIO_MIN es solo para medir resultados.
        precio_sost = float(resultados.precio_en(barras, np.array([t_sost]), cfg,
                                                 tolerancia_min=0)[0])
        if not np.isfinite(precio_sost):
            continue                       # no hay barra en t+M: no se puede declarar

        if cfg.REGLA_SOSTENIDA == "sin_reingreso":
            ventana = posterior & (cierre <= t_sost)
            aguanto = not bool((dentro & ventana).any())
        elif cfg.REGLA_SOSTENIDA == "fuera_en_t_mas_m":
            aguanto = precio_sost >= H if direccion == 1 else precio_sost <= L
        else:
            raise ValueError(f"REGLA_SOSTENIDA desconocida: {cfg.REGLA_SOSTENIDA}")

        if aguanto:
            filas.append({**base, "tipo": "sostenida", "t_evento_ns": t_sost,
                          "t_evento_utc": tiempo.de_ns(t_sost),
                          "precio_evento": precio_sost})

    if not filas:
        return pd.DataFrame(columns=COLUMNAS)

    eventos = pd.DataFrame(filas)[COLUMNAS]
    return eventos.sort_values(["t_evento_ns", "tipo"]).reset_index(drop=True)
