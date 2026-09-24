# -*- coding: utf-8 -*-
"""
AUDITORIA CAUSAL — corre la prueba de truncamiento sobre el motor real.

Deja el veredicto y la tabla de cortes en resultados/auditoria_causal.md, y el
detalle por corte y variante en resultados/auditoria_causal.csv.

La auditoria se corre sobre un mercado simulado de ANIOS_AUDITORIA anos. El
futuro "reemplazado" sale de otro mercado simulado con el mismo indice de
minutos. Que se compara y por que, en motor/auditoria.py.

La prueba de que la auditoria sirve (que atrapa una fuga de un minuto metida a
proposito, con el MISMO generador de cortes) esta en tests/test_auditoria.py.

Uso:
    python -m experimentos.auditoria_causal
"""
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                              # noqa: E402
from experimentos.control_negativo import CARPETA, _tabla  # noqa: E402
from motor import auditoria                                # noqa: E402
from simulacion import mercado                             # noqa: E402


def main():
    cfg = config.copia()
    comienzo = time.perf_counter()
    datos, noticias = mercado.generar(cfg.ANIOS_AUDITORIA, cfg.SEMILLA, cfg)
    alternativo, _ = mercado.generar(cfg.ANIOS_AUDITORIA, cfg.SEMILLA + 1, cfg)
    cortes, detalle = auditoria.auditar(datos, cfg, alternativo, cfg.SEMILLA,
                                        noticias=noticias)
    segundos = time.perf_counter() - comienzo

    os.makedirs(CARPETA, exist_ok=True)
    detalle.to_csv(os.path.join(CARPETA, "auditoria_causal.csv"), index=False)
    texto = _markdown(cortes, detalle, cfg, segundos)
    with open(os.path.join(CARPETA, "auditoria_causal.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto)


def _markdown(cortes, detalle, cfg, segundos):
    pasa = bool(cortes["pasa"].all())
    partes = [
        "# Auditoria causal (prueba de truncamiento)\n",
        f"Mercado simulado de {cfg.ANIOS_AUDITORIA} ano(s), semilla {cfg.SEMILLA}; "
        f"futuro reemplazado con el mercado de semilla {cfg.SEMILLA + 1}. "
        f"{len(cortes)} cortes, {segundos:.0f} segundos.\n",
        f"**Veredicto: {'PASA' if pasa else 'NO PASA'}.** "
        + ("En todos los cortes, los eventos anteriores o iguales al corte salen "
           "identicos, sin tolerancia, con la muestra truncada y con el futuro "
           "reemplazado." if pasa else
           "Hay cortes donde el pasado cambio al tocar el futuro: hay una fuga."),
        "",
        "## Cortes por clase\n",
    ]
    resumen = cortes.groupby("clase").agg(cortes=("pasa", "size"), pasan=("pasa", "sum"))
    partes.append(_tabla(resumen.reset_index()))

    ancho = detalle.pivot(index="t_corte_ns", columns="variante",
                          values="filas_distintas").add_prefix("filas_distintas_")
    comparados = detalle[detalle["variante"] == "truncada"].set_index(
        "t_corte_ns")["eventos_completa"].rename("eventos_comparados")
    tabla = (cortes.drop_duplicates("t_corte_ns").set_index("t_corte_ns")
             .join(comparados).join(ancho).reset_index())
    tabla["t_corte_utc"] = tabla["t_corte_utc"].dt.strftime("%Y-%m-%d %H:%M")
    columnas = ["t_corte_utc", "clase", "tipo_evento", "eventos_comparados"] + \
        [c for c in tabla.columns if c.startswith("filas_distintas_")] + ["pasa"]
    partes += ["\n## Detalle por corte\n", _tabla(tabla[columnas])]

    partes += [
        "\n## Que se compara y que no\n",
        "- Se compara todo lo que el motor declara de un evento en su instante: "
        "tipo, direccion, instantes, extremo roto, precio del evento, sigma_ref, "
        "los moderadores y la volatilidad reciente en la barra del evento.",
        "- No se comparan los resultados (`ret_*`, `h_fin_franja`), que miran el "
        "futuro a proposito.",
        "- No se comparan los grupos de emparejamiento de la nula (deciles de "
        "sigma_ref, tercios de volatilidad reciente, tercio de la franja): se "
        "calculan con la muestra completa por diseno. El tercio usa el fin real "
        "de la franja, que depende de hasta donde llegan los datos. Sus insumos "
        "que si existen en t si se comparan.",
        "- El calendario de anuncios se entrega completo: tiene fecha publicada de "
        "antemano.",
        "",
        "## La auditoria atrapa una fuga\n",
        "`tests/test_auditoria.py` corre esta misma auditoria, con el mismo "
        "generador de cortes y semilla fija, sobre un motor con una fuga de un "
        "minuto metida a proposito (el precio de la sostenida se lee de la barra "
        "que cierra en t + 1). La auditoria la detecta en los cortes anclados a "
        "sostenidas; ningun corte al azar ni de mitad de franja la ve, que es "
        "justamente por que la mitad de los cortes se ancla en eventos.",
        "",
    ]
    return "\n".join(partes)


if __name__ == "__main__":
    main()
