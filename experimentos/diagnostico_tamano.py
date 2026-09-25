# -*- coding: utf-8 -*-
"""
DIAGNOSTICO DEL TAMANO — de donde sale el exceso de rechazos bajo la nula.

Solo lee CSV ya guardados; no corre ningun mercado:

  - punto D: `control_negativo.csv`, familia principal, 50 mercados de 3 anos;
  - punto E: `control_positivo.csv`, delta = 0, bloques de 4, 6 y 13 anos.

Solo se usan las pruebas confirmatorias (sin el horizonte de 120). Es para
DECLARAR: no cambia ALFA_PRINCIPAL, que ya fijo la regla escrita antes de la
corrida larga.

Dos preguntas:

  1. El exceso, es simetrico o favorece a H1 y H2? Se compara la tasa de
     rechazo en la cola de la hipotesis con la tasa en la cola OPUESTA. Bajo la
     nula las dos valen alfa y el p de una cola promedia 1/2.
  2. La diferencia entre la tasa por prueba de 4 y de 6 anos, es mayor que el
     azar? IC95 remuestreando mercados, cada bloque por su lado.

El p de la cola opuesta sale del mismo CSV. El p guardado es el de Phipson y
Smyth en la cola de la hipotesis, p = k / (R + 1), con k - 1 nulas al menos tan
extremas. Como el estadistico es continuo (no hay empates con las nulas), las
otras R - k + 1 nulas quedan del otro lado, y

    p_opuesto = (R + 2 - k) / (R + 1) = (R + 2) / (R + 1) - p.

Se verifica que todos los p caigan en la grilla k / (R + 1).

    python -m experimentos.diagnostico_tamano
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                              # noqa: E402
from experimentos.control_negativo import CARPETA, _tabla   # noqa: E402


def p_cola_opuesta(p, repeticiones):
    """El p de Phipson y Smyth en la cola contraria (ver el docstring del modulo)."""
    p = np.asarray(p, dtype=float)
    k = p * (repeticiones + 1)
    if not np.allclose(k, np.round(k), atol=1e-3):
        raise ValueError("hay p fuera de la grilla k / (R + 1): no se puede dar vuelta la cola")
    return (repeticiones + 2 - np.round(k)) / (repeticiones + 1)


def cargar_pruebas(cfg):
    """Las pruebas confirmatorias bajo la nula, de los dos CSV, con el p de las dos colas."""
    confirmatorios = {str(h) for h in cfg.HORIZONTES_CONFIRMATORIOS}
    partes = []

    negativo = pd.read_csv(os.path.join(CARPETA, "control_negativo.csv"))
    r_negativo = int(pd.read_csv(os.path.join(CARPETA, "control_negativo_meta.csv"))
                     .iloc[0]["repeticiones"])
    negativo = negativo[(negativo["familia"] == "principal")
                        & negativo["horizonte"].astype(str).isin(confirmatorios)]
    partes.append(negativo.assign(bloque="D", horizonte=negativo["horizonte"].astype(str),
                                  repeticiones=r_negativo))

    positivo = pd.read_csv(os.path.join(CARPETA, "control_positivo.csv"),
                           dtype={"horizonte": str})
    r_positivo = int(pd.read_csv(os.path.join(CARPETA, "control_positivo_meta.csv"))
                     .iloc[0]["repeticiones"])
    positivo = positivo[(positivo["delta"] == 0) & positivo["confirmatoria"]]
    partes.append(positivo.assign(bloque="E", repeticiones=r_positivo))

    columnas = ["bloque", "anios", "mercado", "tipo", "horizonte", "p_bruto", "repeticiones"]
    pruebas = pd.concat([p[columnas] for p in partes], ignore_index=True)
    pruebas["p_opuesto"] = np.nan
    for r, filas in pruebas.groupby("repeticiones").groups.items():
        pruebas.loc[filas, "p_opuesto"] = p_cola_opuesta(pruebas.loc[filas, "p_bruto"], r)
    pruebas["duracion"] = pruebas["bloque"] + ", " + pruebas["anios"].astype(str) + " anos"
    return pruebas


def por_celda(pruebas, alfas):
    """Tasa en la cola de la hipotesis, en la opuesta y p medio, por duracion y celda."""
    filas = []
    for (duracion, tipo, h), g in pruebas.groupby(["duracion", "tipo", "horizonte"],
                                                   sort=False):
        fila = {"duracion": duracion, "tipo": tipo, "horizonte": h, "mercados": len(g),
                "p_medio": g["p_bruto"].mean(),
                "error_mc_p_medio": g["p_bruto"].std() / np.sqrt(len(g))}
        for alfa in alfas:
            fila[f"hipotesis_{alfa}"] = float((g["p_bruto"] <= alfa).mean())
            fila[f"opuesta_{alfa}"] = float((g["p_opuesto"] <= alfa).mean())
        filas.append(fila)
    return pd.DataFrame(filas)


def _por_mercado(pruebas, columna, alfa):
    """Por mercado: rechazos y pruebas. Las pruebas de un mercado no son independientes."""
    g = pruebas.assign(r=(pruebas[columna] <= alfa).astype(float)).groupby("mercado")["r"]
    return g.sum().to_numpy(float), g.count().to_numpy(float)


def asimetria(pruebas, alfa, remuestreos, semilla):
    """
    Tasa por prueba en la cola de la hipotesis menos la de la cola opuesta, con
    IC95 remuestreando mercados (el mismo sorteo para las dos colas: son las
    mismas pruebas).
    """
    hip, n = _por_mercado(pruebas, "p_bruto", alfa)
    opu, _ = _por_mercado(pruebas, "p_opuesto", alfa)
    rng = np.random.default_rng(semilla)
    sorteo = rng.integers(0, len(n), size=(remuestreos, len(n)))
    total = n[sorteo].sum(axis=1)
    dif = (hip[sorteo].sum(axis=1) - opu[sorteo].sum(axis=1)) / total
    bajo, alto = np.percentile(dif, [2.5, 97.5])
    return hip.sum() / n.sum(), opu.sum() / n.sum(), (hip.sum() - opu.sum()) / n.sum(), bajo, alto


def diferencia_entre_bloques(a, b, columna, alfa, remuestreos, semilla):
    """
    Tasa por prueba de `a` menos la de `b`, con IC95 remuestreando los mercados
    de cada bloque por separado (son mercados distintos).
    """
    ra, na = _por_mercado(a, columna, alfa)
    rb, nb = _por_mercado(b, columna, alfa)
    rng = np.random.default_rng(semilla)
    sa = rng.integers(0, len(na), size=(remuestreos, len(na)))
    sb = rng.integers(0, len(nb), size=(remuestreos, len(nb)))
    dif = ra[sa].sum(axis=1) / na[sa].sum(axis=1) - rb[sb].sum(axis=1) / nb[sb].sum(axis=1)
    bajo, alto = np.percentile(dif, [2.5, 97.5])
    return ra.sum() / na.sum(), rb.sum() / nb.sum(), ra.sum() / na.sum() - rb.sum() / nb.sum(), \
        bajo, alto


def main():
    cfg = config.copia()
    alfas = sorted({cfg.ALFA, cfg.ALFA_ESTRICTO}, reverse=True)
    remuestreos, semilla = cfg.REMUESTREOS_IC_MERCADOS, cfg.SEMILLA
    pruebas = cargar_pruebas(cfg)

    filas = []
    for duracion, g in pruebas.groupby("duracion", sort=False):
        for alfa in alfas:
            hip, opu, dif, bajo, alto = asimetria(g, alfa, remuestreos, semilla)
            filas.append({"duracion": duracion, "alfa": alfa,
                          "mercados": g["mercado"].nunique(), "pruebas": len(g),
                          "cola_hipotesis": hip, "cola_opuesta": opu,
                          "hipotesis_menos_opuesta": dif, "ic95": f"[{bajo:.4f}, {alto:.4f}]",
                          "p_medio": g["p_bruto"].mean()})
    simetria = pd.DataFrame(filas)

    cuatro = pruebas[(pruebas["bloque"] == "E") & (pruebas["anios"] == 4)]
    seis = pruebas[(pruebas["bloque"] == "E") & (pruebas["anios"] == 6)]
    filas = []
    for columna, cola in (("p_bruto", "hipotesis"), ("p_opuesto", "opuesta")):
        for alfa in alfas:
            t4, t6, dif, bajo, alto = diferencia_entre_bloques(cuatro, seis, columna, alfa,
                                                               remuestreos, semilla)
            filas.append({"cola": cola, "alfa": alfa, "tasa_4": t4, "tasa_6": t6,
                          "4_menos_6": dif, "ic95": f"[{bajo:.4f}, {alto:.4f}]",
                          "fuera_del_azar": not (bajo <= 0 <= alto)})
    entre = pd.DataFrame(filas)
    celdas = por_celda(pruebas, alfas)

    texto = "\n".join([
        "# Diagnostico del tamano bajo la nula (solo declarativo)\n",
        "Solo lee CSV guardados: punto D (familia principal, 3 anos) y punto E (delta = 0, "
        "4, 6 y 13 anos). Pruebas confirmatorias. `cola_hipotesis`: p bruto <= alfa en la "
        "cola de H1/H2. `cola_opuesta`: lo mismo en la cola contraria (p opuesto = "
        "(R + 2)/(R + 1) - p, exacto sin empates). Bajo la nula las dos valen alfa y el p "
        "medio vale 1/2. IC95 remuestreando mercados "
        f"({remuestreos} remuestreos). **No cambia ALFA_PRINCIPAL**: la regla ya se aplico.\n",
        "## 1. Simetria del exceso, por duracion\n",
        _tabla(simetria.round(4)),
        "\n## 2. Tasa por prueba: 4 anos contra 6 anos\n",
        "Bloques de mercados distintos, remuestreados por separado.\n",
        _tabla(entre.round(4)),
        "\n## 3. Por celda\n",
        "`p_medio` con su error de Monte Carlo entre mercados.\n",
        _tabla(celdas.round(4)),
    ]) + "\n"
    with open(os.path.join(CARPETA, "diagnostico_tamano.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


if __name__ == "__main__":
    main()
