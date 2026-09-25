# -*- coding: utf-8 -*-
"""
ANEXO DE SENSIBILIDAD — cuantas franjas rompen, aguantan y reingresan con
otros umbrales y otros M (pendiente del punto B para el pre-registro).

Solo detecta eventos: no mide retornos ni corre la nula, asi que no dice nada
sobre las hipotesis. Sirve para que el grupo fije UMBRAL_PIPS, UMBRAL_VOL y
M_SOSTENIDA_MIN con numeros a la vista y ANTES de mirar datos reales. Son
numeros de un paseo aleatorio con VOL_ANUAL_SIMULACION de volatilidad, no del
EUR/USD.

Por variante (modo y valor del umbral, M):
  - % de franjas utilizables con ruptura, con sostenida y con reingreso;
  - % de rupturas que aguantan M minutos;
  - % de sostenidas cuya franja tiene despues un reingreso (la superposicion
    que el punto E midio en 71-73% con la configuracion actual);
  - umbral medio en pips (en el modo "vol" depende de sigma_ref y del extremo).

Uso:
    python -m experimentos.anexo_sensibilidad
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                              # noqa: E402
from experimentos import recursos                          # noqa: E402
from experimentos.control_negativo import CARPETA, _en_paralelo, _tabla  # noqa: E402
from motor import eventos, franjas, resultados             # noqa: E402
from simulacion import mercado                             # noqa: E402

DESPLAZAMIENTO = 70000
PREFIJO = "anexo_sensibilidad"


def variantes(cfg):
    """(modo, nombre del parametro, valor, M) de cada variante del anexo."""
    salida = []
    for modo, nombre, valores in (("pips", "UMBRAL_PIPS", cfg.SENSIBILIDAD_UMBRAL_PIPS),
                                  ("vol", "UMBRAL_VOL", cfg.SENSIBILIDAD_UMBRAL_VOL)):
        for valor in valores:
            for m in cfg.SENSIBILIDAD_M:
                salida.append((modo, nombre, float(valor), int(m)))
    return salida


def resumen_de_variante(tabla, n_utilizables, anios):
    """Los porcentajes de una variante a partir de su tabla de eventos."""
    por_tipo = tabla["tipo"].value_counts()
    rupturas = int(por_tipo.get("ruptura", 0))
    sostenidas = tabla[tabla["tipo"] == "sostenida"]
    con_reingreso = set(tabla.loc[tabla["tipo"] == "reingreso", "id_franja"])
    # El reingreso es el PRIMERO despues de la ruptura, y la sostenida exige que
    # no haya ninguno hasta t + M: si la franja tiene reingreso, es posterior.
    reingresa = sostenidas["id_franja"].isin(con_reingreso)
    return {
        "franjas_utilizables": n_utilizables,
        "pct_ruptura": rupturas / n_utilizables,
        "pct_sostenida": len(sostenidas) / n_utilizables,
        "pct_reingreso": int(por_tipo.get("reingreso", 0)) / n_utilizables,
        "pct_rupturas_que_aguantan": len(sostenidas) / rupturas if rupturas else np.nan,
        "pct_sostenidas_que_reingresan": float(reingresa.mean()) if len(sostenidas) else np.nan,
        "sostenidas_por_anio": len(sostenidas) / anios,
        "reingresos_por_anio": int(por_tipo.get("reingreso", 0)) / anios,
    }


def corrida(semilla, anios, cambios):
    """Un mercado: la deteccion de cada variante sobre las mismas barras."""
    cfg = config.copia(**cambios)
    datos, _ = mercado.generar(anios, semilla, cfg)
    barras = franjas.Barras.desde(datos, cfg)
    del datos
    cal = franjas.calendario(barras, cfg)
    sigma = resultados.sigma_por_franja(barras, cal, cfg)
    H = cal["H"].to_numpy(float)
    L = cal["L"].to_numpy(float)

    filas = []
    for modo, nombre, valor, m in variantes(cfg):
        variante = config.copia(**{**cambios, "UMBRAL_MODO": modo, nombre: valor,
                                   "M_SOSTENIDA_MIN": m})
        utilizables = np.flatnonzero(eventos.franjas_utilizables(cal, sigma, variante))
        tabla = eventos.detectar(barras, cal, variante, sigma=sigma)
        if modo == "pips":
            umbral_pips = valor
        else:
            ref = utilizables - 1
            umbral_pips = float(np.mean(valor * sigma[utilizables] * (H[ref] + L[ref]) / 2.0)
                                / cfg.PIP)
        fila = {"mercado": semilla, "modo": modo, "valor": valor, "M": m,
                "umbral_medio_pips": umbral_pips}
        fila.update(resumen_de_variante(tabla, len(utilizables), anios))
        filas.append(fila)
    return pd.DataFrame(filas)


def _tarea(argumentos):
    return corrida(*argumentos)


def markdown(tabla, cfg, minutos):
    columnas = ["umbral_medio_pips", "pct_ruptura", "pct_sostenida", "pct_reingreso",
                "pct_rupturas_que_aguantan", "pct_sostenidas_que_reingresan",
                "sostenidas_por_anio", "reingresos_por_anio"]
    medias = tabla.groupby(["modo", "valor", "M"], sort=False)[columnas].mean().reset_index()
    for c in columnas:
        if c.startswith("pct_"):
            medias[c] = (100 * medias[c]).round(1)
        else:
            medias[c] = medias[c].round(1)
    medias.columns = ["modo", "valor", "M", "umbral medio (pips)", "% franjas con ruptura",
                      "% con sostenida", "% con reingreso", "% de rupturas que aguantan M",
                      "% de sostenidas que reingresan", "sostenidas/ano", "reingresos/ano"]
    actual = (f"UMBRAL_MODO = \"{cfg.UMBRAL_MODO}\", UMBRAL_PIPS = {cfg.UMBRAL_PIPS}, "
              f"UMBRAL_VOL = {cfg.UMBRAL_VOL}, M_SOSTENIDA_MIN = {cfg.M_SOSTENIDA_MIN}, "
              f"REGLA_SOSTENIDA = \"{cfg.REGLA_SOSTENIDA}\"")
    return "\n".join([
        "# Anexo de sensibilidad de la deteccion (solo mercados simulados)\n",
        f"- {tabla['mercado'].nunique()} mercados de {cfg.ANIOS_SENSIBILIDAD} anos, "
        f"volatilidad anual {cfg.VOL_ANUAL_SIMULACION:.0%}; {minutos:.1f} minutos.",
        f"- Configuracion actual: {actual}.",
        "- Porcentajes sobre las franjas utilizables (las que pueden generar eventos). "
        "Promedio entre mercados.",
        "- Solo deteccion: no hay retornos ni nula, asi que nada de esto dice si las "
        "hipotesis se cumplen. Es un paseo aleatorio, no el EUR/USD.\n",
        _tabla(medias), "",
    ]) + "\n"


def main():
    cfg = config.copia()
    trabajos = [(cfg.SEMILLA + DESPLAZAMIENTO + k, cfg.ANIOS_SENSIBILIDAD, {})
                for k in range(cfg.MERCADOS_SENSIBILIDAD)]
    procesos = recursos.procesos_que_caben(0.6, tope=len(trabajos))
    print(f"{len(trabajos)} mercados, {len(variantes(cfg))} variantes, {procesos} procesos "
          f"({recursos.describir()})", flush=True)
    comienzo = time.perf_counter()
    tabla = pd.concat(_en_paralelo(_tarea, trabajos, procesos), ignore_index=True)
    minutos = (time.perf_counter() - comienzo) / 60
    os.makedirs(CARPETA, exist_ok=True)
    tabla.to_csv(os.path.join(CARPETA, f"{PREFIJO}.csv"), index=False, float_format="%.6g")
    texto = markdown(tabla, cfg, minutos)
    with open(os.path.join(CARPETA, f"{PREFIJO}.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


if __name__ == "__main__":
    main()
