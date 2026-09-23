# -*- coding: utf-8 -*-
"""
CONTROL NEGATIVO — cuantos falsos positivos produce el motor.

Se corre el pipeline completo sobre mercados simulados donde, por
construccion, NO hay nada que descubrir. Todo lo que el motor encuentre aqui es
un falso positivo. Si el metodo esta bien calibrado:

  - el efecto medio de cada tipo y horizonte tiene que quedar cerca de cero;
  - la tasa de rechazos al 5% tiene que rondar el 5%;
  - la tasa de "al menos un rechazo" en una familia corregida tiene que quedar
    en el 5% o por debajo;
  - el histograma de p-valores tiene que verse aproximadamente plano.

Son dos bloques:

  CORTO  50 mercados de 3 anos. Mide las familias principal y de moderadores.
  LARGO  15 mercados de 13 anos, solo para H4. Hace falta porque los eventos
         "con anuncio" son escasos: con 3 anos casi ninguna prueba llega al
         minimo de dias tratados y la tabla saldria vacia. Con 13 anos se puede
         ver la tasa de falsos positivos POR TRAMO de dias tratados, que es lo
         que permite fijar MIN_DIAS_TRATADOS con evidencia en vez de a ojo.

Uso:
    python -m experimentos.control_negativo --piloto     mide tiempo y memoria
    python -m experimentos.control_negativo              corrida completa
    python -m experimentos.control_negativo --cortos 20 --largos 6
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
from motor import inferencia, moderadores, nula            # noqa: E402
from simulacion import mercado                             # noqa: E402

CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "resultados")
TRAMOS = [(0, 10, "<10"), (10, 30, "10-29"), (30, 100, "30-99"),
          (100, 10 ** 9, ">=100")]


# =============================================================================
#  Una corrida
# =============================================================================
def corrida_corta(semilla, anios, cambios, con_romano_wolf, repeticiones):
    """
    Un mercado del bloque corto: familias principal y de moderadores.

    Devuelve un DataFrame con una fila por prueba.
    """
    cfg = config.copia(**cambios)
    datos, noticias = mercado.generar(anios, semilla, cfg)
    barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)

    candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
    tabla_nula, _ = nula.correr(barras, cal, eventos, cfg, semilla,
                                repeticiones=repeticiones, candidatos=candidatos)
    celdas, dias = inferencia.construir_celdas(eventos, cfg)

    principal = inferencia.analizar(
        eventos, cfg, cfg.FAMILIA_PRINCIPAL, semilla,
        p_brutos=inferencia.p_brutos_desde_nula(tabla_nula, cfg),
        celdas=celdas, dias=dias, con_romano_wolf=con_romano_wolf,
        repeticiones_rw=repeticiones)
    principal["familia"] = "principal"

    mods = inferencia.analizar(
        eventos, cfg, cfg.FAMILIA_MODERADORES, semilla, celdas=celdas, dias=dias,
        con_romano_wolf=con_romano_wolf, repeticiones_rw=repeticiones)
    mods["familia"] = "moderadores"

    # El efecto medio observado sale de la nula, que ya lo calculo.
    efectos = tabla_nula.set_index(["tipo", "horizonte"])["media_observada"]
    salida = pd.concat([principal, mods], ignore_index=True)
    salida["efecto"] = [efectos.get((t, h), np.nan)
                        for t, h in zip(salida["tipo"], salida["horizonte"])]
    salida["mercado"] = semilla
    salida["anios"] = anios
    salida["n_eventos"] = len(eventos)

    descriptivo = tabla_nula[tabla_nula["tipo"] == "ruptura"].copy()
    descriptivo["mercado"] = semilla
    return salida, descriptivo


def corrida_larga(semilla, anios, cambios, repeticiones):
    """
    Un mercado del bloque largo: H4 con las dos definiciones de noticia.

    La tasa de falsos positivos se calcula SIN aplicar MIN_DIAS_TRATADOS: aqui
    el minimo se esta calibrando, no aplicando.
    """
    cfg_base = config.copia(**cambios)
    datos, noticias = mercado.generar(anios, semilla, cfg_base)

    filas, conteos = [], []
    for modo in ("ventana", "franja"):
        cfg = config.copia(**{**cambios, "NOTICIA_MODO": modo})
        barras, cal, eventos = motor.preparar(datos, cfg, noticias=noticias)
        candidatos = nula.preparar_candidatos(barras, cal, cfg, noticias=noticias)
        tabla = nula.correr_h4(barras, cal, eventos, cfg, semilla,
                               repeticiones=repeticiones, candidatos=candidatos)
        tabla["modo"] = modo
        tabla["mercado"] = semilla
        tabla["anios"] = anios
        filas.append(tabla)

        # Cuantos eventos y cuantos dias tratados por ano, por tipo.
        for tipo in ("sostenida", "reingreso"):
            sub = eventos[eventos["tipo"] == tipo]
            tratados = sub[sub["noticia"] == 1.0]
            conteos.append({
                "mercado": semilla, "modo": modo, "tipo": tipo, "anios": anios,
                "eventos_por_anio": len(sub) / anios,
                "tratados_por_anio": len(tratados) / anios,
                "dias_tratados_por_anio": tratados["fecha_londres"].nunique() / anios,
            })
    return pd.concat(filas, ignore_index=True), pd.DataFrame(conteos)


def _tarea_corta(argumentos):
    return corrida_corta(*argumentos)


def _tarea_larga(argumentos):
    return corrida_larga(*argumentos)


def _en_paralelo(tarea, trabajos, procesos):
    """Corre los trabajos en paralelo, avisando por pantalla como va."""
    if procesos <= 1:
        salida = []
        for k, trabajo in enumerate(trabajos, 1):
            salida.append(tarea(trabajo))
            print(f"  {k}/{len(trabajos)} listo", flush=True)
        return salida
    salida = []
    with ProcessPoolExecutor(max_workers=procesos) as pozo:
        for k, resultado in enumerate(pozo.map(tarea, trabajos), 1):
            salida.append(resultado)
            print(f"  {k}/{len(trabajos)} listo", flush=True)
    return salida


# =============================================================================
#  Resumenes
# =============================================================================
def intervalo_binomial(exitos, total):
    """
    Intervalo de Wilson al 95% para una proporcion.

    Se usa Wilson y no la formula clasica porque con proporciones chicas (una
    tasa de rechazo del 5%) la clasica da intervalos que se salen de [0,1] y
    cubre peor de lo que promete.
    """
    if total == 0:
        return (np.nan, np.nan)
    z = 1.959963985
    p = exitos / total
    centro = (p + z * z / (2 * total)) / (1 + z * z / total)
    mitad = (z / (1 + z * z / total)) * np.sqrt(
        p * (1 - p) / total + z * z / (4 * total * total))
    return (max(0.0, centro - mitad), min(1.0, centro + mitad))


def error_monte_carlo(p, n):
    """Error estandar de una tasa estimada con n corridas."""
    return np.sqrt(p * (1 - p) / n) if n > 0 else np.nan


def resumen_por_familia(tabla, cfg, columna="p_corregido"):
    """Tasa de rechazos por familia, por prueba y por familia completa."""
    filas = []
    for familia, bloque in tabla.groupby("familia"):
        por_prueba = bloque[np.isfinite(bloque["p_bruto"].to_numpy(float))]
        brutos = int((por_prueba["p_bruto"].to_numpy(float) <= cfg.ALFA).sum())
        total = len(por_prueba)
        corregidos = int((bloque[columna].to_numpy(float) <= cfg.ALFA).sum())
        mercados = bloque["mercado"].nunique()
        con_alguno = int(bloque.groupby("mercado")[columna].apply(
            lambda s: bool(np.nansum(s.to_numpy(float) <= cfg.ALFA) > 0)).sum())
        bajo, alto = intervalo_binomial(brutos, total)
        bajo_f, alto_f = intervalo_binomial(con_alguno, mercados)
        filas.append({
            "familia": familia, "pruebas": total,
            "tasa_bruta": brutos / total if total else np.nan,
            "ic95_bruta": f"[{bajo:.3f}, {alto:.3f}]",
            "rechazos_corregidos": corregidos,
            "mercados": mercados,
            "tasa_familia": con_alguno / mercados if mercados else np.nan,
            "ic95_familia": f"[{bajo_f:.3f}, {alto_f:.3f}]",
        })
    return pd.DataFrame(filas)


def resumen_h4(tabla, cfg):
    """Tasa de falsos positivos de H4 por tramo de dias tratados y por modo."""
    filas = []
    for modo, bloque_modo in tabla.groupby("modo"):
        for columna, etiqueta in [("p_estudentizado", "estudentizado"),
                                  ("p_sin_estudentizar", "sin estudentizar")]:
            for bajo, alto, nombre in TRAMOS:
                dentro = bloque_modo[
                    (bloque_modo["dias_tratados"] >= bajo)
                    & (bloque_modo["dias_tratados"] < alto)
                    & np.isfinite(bloque_modo[columna].to_numpy(float))]
                if len(dentro) == 0:
                    continue
                rechaza = int((dentro[columna].to_numpy(float) <= cfg.ALFA).sum())
                lo, hi = intervalo_binomial(rechaza, len(dentro))
                filas.append({
                    "modo": modo, "estadistico": etiqueta, "tramo": nombre,
                    "pruebas": len(dentro), "rechazos": rechaza,
                    "tasa": rechaza / len(dentro),
                    "ic95": f"[{lo:.3f}, {hi:.3f}]",
                })
    return pd.DataFrame(filas)


def grafico_p_valores(tabla, ruta):
    """Histograma de p-valores brutos: deberia verse aproximadamente plano."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    familias = sorted(tabla["familia"].unique())
    figura, ejes = plt.subplots(1, len(familias), figsize=(5 * len(familias), 4))
    ejes = np.atleast_1d(ejes)
    for eje, familia in zip(ejes, familias):
        p = tabla[tabla["familia"] == familia]["p_bruto"].to_numpy(float)
        p = p[np.isfinite(p)]
        eje.hist(p, bins=20, range=(0, 1), color="#4C72B0", edgecolor="white")
        eje.axhline(len(p) / 20, color="#C44E52", linestyle="--",
                    label="lo plano seria esto")
        eje.set_title(f"familia {familia}  (n = {len(p)})")
        eje.set_xlabel("p-valor bruto")
        eje.set_ylabel("pruebas")
        eje.legend(fontsize=8)
    figura.suptitle("Control negativo: p-valores en mercados sin ningun patron")
    figura.tight_layout()
    figura.savefig(ruta, dpi=130)
    plt.close(figura)


# =============================================================================
#  Piloto
# =============================================================================
def piloto(cambios, repeticiones, con_romano_wolf):
    """Mide tiempo y memoria de un mercado de cada bloque antes de la corrida."""
    print(recursos.describir())
    print()
    medidas = {}

    print("Piloto del bloque CORTO (1 mercado de 3 anos)...")
    _, pico, segundos = recursos.medir_pico(
        lambda: corrida_corta(1, config.ANIOS, cambios, con_romano_wolf, repeticiones))
    medidas["corto"] = (segundos, pico)
    print(f"  {segundos:.1f} s por mercado, ~{pico:.2f} GB de pico")

    print("Piloto del bloque LARGO (1 mercado de 13 anos, H4 con dos modos)...")
    anios_largo = max(config.ANIOS_POTENCIA)
    _, pico_l, segundos_l = recursos.medir_pico(
        lambda: corrida_larga(1, anios_largo, cambios, repeticiones))
    medidas["largo"] = (segundos_l, pico_l)
    print(f"  {segundos_l:.1f} s por mercado, ~{pico_l:.2f} GB de pico")
    return medidas


# =============================================================================
#  Programa principal
# =============================================================================
def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--piloto", action="store_true",
                            help="solo mide tiempo y memoria de un mercado de cada bloque")
    analizador.add_argument("--cortos", type=int, default=None)
    analizador.add_argument("--largos", type=int, default=15)
    analizador.add_argument("--anios-largos", type=int, default=None)
    analizador.add_argument("--repeticiones", type=int, default=None)
    analizador.add_argument("--sin-romano-wolf", action="store_true")
    analizador.add_argument("--procesos", type=int, default=None)
    analizador.add_argument("--solo-reporte", action="store_true",
                            help="rehace el markdown y el grafico desde los CSV ya guardados")
    opciones = analizador.parse_args()

    if opciones.solo_reporte:
        _rehacer_reporte()
        return

    cambios = {}
    repeticiones = opciones.repeticiones or config.NULA_REPETICIONES
    con_rw = not opciones.sin_romano_wolf
    n_cortos = opciones.cortos or config.MERCADOS_CONTROL_NEGATIVO
    anios_largos = opciones.anios_largos or max(config.ANIOS_POTENCIA)

    if opciones.piloto:
        piloto(cambios, repeticiones, con_rw)
        return

    os.makedirs(CARPETA, exist_ok=True)
    comienzo = time.perf_counter()

    print(f"Bloque CORTO: {n_cortos} mercados de {config.ANIOS} anos")
    trabajos = [(config.SEMILLA + k, config.ANIOS, cambios, con_rw, repeticiones)
                for k in range(n_cortos)]
    procesos = opciones.procesos or recursos.procesos_que_caben(0.8, tope=8)
    print(f"  {procesos} procesos en paralelo")
    resultados = _en_paralelo(_tarea_corta, trabajos, procesos)
    pruebas = pd.concat([r[0] for r in resultados], ignore_index=True)
    rupturas = pd.concat([r[1] for r in resultados], ignore_index=True)

    print(f"Bloque LARGO: {opciones.largos} mercados de {anios_largos} anos (solo H4)")
    trabajos_l = [(config.SEMILLA + 1000 + k, anios_largos, cambios, repeticiones)
                  for k in range(opciones.largos)]
    procesos_l = opciones.procesos or recursos.procesos_que_caben(2.5, tope=6)
    print(f"  {procesos_l} procesos en paralelo")
    resultados_l = _en_paralelo(_tarea_larga, trabajos_l, procesos_l)
    h4 = pd.concat([r[0] for r in resultados_l], ignore_index=True)
    conteos = pd.concat([r[1] for r in resultados_l], ignore_index=True)

    minutos = (time.perf_counter() - comienzo) / 60
    guardar(pruebas, rupturas, h4, conteos, minutos, n_cortos, opciones.largos,
            anios_largos, repeticiones, con_rw)
    print(f"\nListo en {minutos:.1f} minutos. Reportes en resultados/")


def _rehacer_reporte():
    """
    Vuelve a escribir el reporte a partir de los CSV ya guardados.

    Sirve para mejorar la presentacion sin repetir quince minutos de calculo.
    Los numeros no cambian: salen de los mismos archivos.
    """
    pruebas = pd.read_csv(os.path.join(CARPETA, "control_negativo.csv"))
    h4 = pd.read_csv(os.path.join(CARPETA, "control_negativo_h4.csv"))
    rupturas = pd.read_csv(os.path.join(CARPETA, "control_negativo_rupturas.csv"))
    conteos = pd.read_csv(os.path.join(CARPETA, "control_negativo_conteos.csv"))
    meta = pd.read_csv(os.path.join(CARPETA, "control_negativo_meta.csv")).iloc[0]
    cfg = config.copia()
    with open(os.path.join(CARPETA, "control_negativo.md"), "w", encoding="utf-8") as f:
        f.write(_markdown(pruebas, rupturas, h4, conteos, cfg,
                          float(meta["minutos"]), int(meta["n_cortos"]),
                          int(meta["n_largos"]), int(meta["anios_largos"]),
                          int(meta["repeticiones"]), bool(meta["con_rw"])))
    grafico_p_valores(pruebas, os.path.join(CARPETA, "control_negativo_pvalores.png"))
    print("Reporte rehecho desde los CSV guardados.")


def guardar(pruebas, rupturas, h4, conteos, minutos, n_cortos, n_largos,
            anios_largos, repeticiones, con_rw):
    """Escribe el CSV, el markdown y el grafico."""
    cfg = config.copia()
    columnas = ["mercado", "anios", "familia", "tipo", "horizonte", "coeficiente",
                "efecto", "estimacion", "t", "p_bruto", "p_holm", "p_romano_wolf",
                "p_corregido", "rechaza", "n", "n_eventos"]
    pruebas[columnas].to_csv(os.path.join(CARPETA, "control_negativo.csv"),
                             index=False, float_format="%.6g")
    h4.to_csv(os.path.join(CARPETA, "control_negativo_h4.csv"), index=False,
              float_format="%.6g")
    rupturas.to_csv(os.path.join(CARPETA, "control_negativo_rupturas.csv"),
                    index=False, float_format="%.6g")
    conteos.to_csv(os.path.join(CARPETA, "control_negativo_conteos.csv"),
                   index=False, float_format="%.6g")
    pd.DataFrame([{"minutos": minutos, "n_cortos": n_cortos, "n_largos": n_largos,
                   "anios_largos": anios_largos, "repeticiones": repeticiones,
                   "con_rw": con_rw}]).to_csv(
        os.path.join(CARPETA, "control_negativo_meta.csv"), index=False)
    grafico_p_valores(pruebas, os.path.join(CARPETA, "control_negativo_pvalores.png"))

    with open(os.path.join(CARPETA, "control_negativo.md"), "w", encoding="utf-8") as f:
        f.write(_markdown(pruebas, rupturas, h4, conteos, cfg, minutos, n_cortos,
                          n_largos, anios_largos, repeticiones, con_rw))


def _markdown(pruebas, rupturas, h4, conteos, cfg, minutos, n_cortos, n_largos,
              anios_largos, repeticiones, con_rw):
    """El reporte en espanol simple."""
    partes = []
    escribe = partes.append

    escribe("# Control negativo\n")
    escribe("Mercados simulados **sin ningun patron**: por construccion no hay "
            "nada que descubrir. Todo lo que el motor encuentre aqui es un "
            "falso positivo.\n")
    escribe(f"- Bloque corto: **{n_cortos} mercados de {cfg.ANIOS} anos**.")
    escribe(f"- Bloque largo (solo H4): **{n_largos} mercados de {anios_largos} anos**.")
    escribe(f"- Repeticiones de la nula: {repeticiones}. "
            f"Romano-Wolf: {'si' if con_rw else 'no'}.")
    escribe(f"- Tiempo total: {minutos:.1f} minutos. Equipo: {recursos.describir()}.")
    escribe(f"- Semilla base: {cfg.SEMILLA}.\n")

    escribe("## 1. El efecto medio, ¿queda cerca de cero?\n")
    efectos = pruebas[pruebas["familia"] == "principal"].groupby(
        ["tipo", "horizonte"])["efecto"].agg(["mean", "std", "count"])
    efectos["error_mc"] = efectos["std"] / np.sqrt(efectos["count"])
    escribe("Promedio, entre mercados, del retorno normalizado observado. "
            "Deberia ser cercano a cero.\n")
    escribe(_tabla(efectos.reset_index().round(4)))

    escribe("\n## 2. Tasa de falsos positivos por familia\n")
    resumen = resumen_por_familia(pruebas, cfg)
    escribe("`tasa_bruta` deberia rondar 0,05 y su intervalo contenerlo. "
            "`tasa_familia` es la proporcion de mercados con AL MENOS un "
            "rechazo tras corregir: deberia quedar en 0,05 o menos.\n")
    escribe(_tabla(resumen.round(4)))

    if con_rw and pruebas["p_romano_wolf"].notna().any():
        escribe("\n### Holm contra Romano-Wolf\n")
        comparacion = []
        for familia, bloque in pruebas.groupby("familia"):
            fila = {"familia": familia}
            for metodo in ("p_holm", "p_romano_wolf"):
                por_mercado = bloque.groupby("mercado")[metodo].apply(
                    lambda s: bool(np.nansum(s.to_numpy(float) <= cfg.ALFA) > 0))
                fila[metodo] = por_mercado.mean()
            comparacion.append(fila)
        escribe(_tabla(pd.DataFrame(comparacion).round(4)))

    escribe("\n### Detalle: la familia principal, prueba por prueba\n")
    escribe("Si el metodo esta calibrado, `p_medio` deberia dar alrededor de "
            "0,5 en cada celda y `tasa` alrededor de 0,05.\n")
    detalle = pruebas[pruebas["familia"] == "principal"].groupby(
        ["tipo", "horizonte"]).apply(
        lambda g: pd.Series({
            "mercados": len(g),
            "tasa": float((g["p_bruto"].to_numpy(float) <= cfg.ALFA).mean()),
            "p_medio": float(np.nanmean(g["p_bruto"].to_numpy(float)))}),
        include_groups=False).reset_index()
    escribe(_tabla(detalle.round(4)))

    escribe("\n## 3. H4: calibracion de MIN_DIAS_TRATADOS\n")
    escribe("Bloque largo, **sin** aplicar el minimo: aqui se esta calibrando, "
            "no aplicando.\n")
    escribe(_tabla(resumen_h4(h4, cfg).round(4)))

    escribe("\n### La misma tasa, pero por modo y TIPO de evento\n")
    escribe("Es la lectura que importa, porque cada combinacion de modo y tipo "
            "cae casi entera en un solo tramo: mirando solo los tramos, el "
            "tamano de la muestra tratada y el tipo de evento quedan "
            "confundidos y no se puede separar uno del otro.\n")
    por_tipo = h4.groupby(["modo", "tipo"]).apply(
        lambda g: pd.Series({
            "pruebas": len(g),
            "dias_tratados_medio": float(g["dias_tratados"].mean()),
            "dias_min": float(g["dias_tratados"].min()),
            "dias_max": float(g["dias_tratados"].max()),
            "tasa_estudentizado": float(
                (g["p_estudentizado"].to_numpy(float) <= cfg.ALFA).mean()),
            "tasa_sin_estudentizar": float(
                (g["p_sin_estudentizar"].to_numpy(float) <= cfg.ALFA).mean())}),
        include_groups=False).reset_index()
    escribe(_tabla(por_tipo.round(4)))

    escribe("\n### Cuanta muestra hay por ano\n")
    escribe("Sirve para saber si con 13 anos de datos reales las sostenidas "
            "van a tener muestra suficiente o si esa prueba nace descriptiva.\n")
    promedio = conteos.groupby(["modo", "tipo"])[
        ["eventos_por_anio", "tratados_por_anio", "dias_tratados_por_anio"]].mean()
    escribe(_tabla(promedio.reset_index().round(1)))

    escribe("\n## 4. Histograma de p-valores\n")
    escribe("Ver `control_negativo_pvalores.png`. Si el metodo esta calibrado, "
            "las barras se ven parejas.\n")

    escribe("\n## 5. Tipo descriptivo: ruptura\n")
    descriptivo = rupturas.groupby("horizonte")[
        ["media_observada", "p_dos_colas"]].mean()
    escribe(_tabla(descriptivo.reset_index().round(4)))

    return "\n".join(partes) + "\n"


def _tabla(marco):
    """
    Un DataFrame como tabla de markdown.

    Escrito a mano para no sumar una dependencia (`to_markdown` de pandas
    necesita `tabulate`) por diez lineas de codigo.
    """
    if len(marco) == 0:
        return "_(sin datos)_"
    columnas = [str(c) for c in marco.columns]
    filas = [[_texto(v) for v in fila] for fila in marco.itertuples(index=False)]
    lineas = ["| " + " | ".join(columnas) + " |",
              "|" + "|".join(["---"] * len(columnas)) + "|"]
    lineas += ["| " + " | ".join(fila) + " |" for fila in filas]
    return "\n".join(lineas)


def _texto(valor):
    """Un valor como texto corto y legible."""
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return "-"
    if isinstance(valor, (float, np.floating)):
        return f"{valor:.4f}".rstrip("0").rstrip(".") or "0"
    return str(valor)


if __name__ == "__main__":
    main()
