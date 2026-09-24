# -*- coding: utf-8 -*-
"""
AUDITORIA — prueba de truncamiento contra el sesgo de anticipacion.

Idea heredada del proyecto anterior (Cuartinhos_Goty, motor.py::causality_audit):
correr la deteccion con la muestra cortada en un instante y con la muestra
completa; los eventos anteriores al corte deben ser identicos. Alli se
verifico que NO conviene dejar un margen de seguridad alrededor del corte:
justamente las decisiones pegadas al corte son las unicas que una fuga
intradia puede alterar.

Cada corte se prueba de dos maneras:

  truncada     solo existen las barras que cierran en el corte o antes;
  reemplazada  las barras que cierran despues del corte se cambian por las de
               otro mercado simulado, empalmadas con el precio del corte.

Todo evento con t_evento <= corte, con todo lo que el motor declara de el en
ese instante, tiene que salir IDENTICO al de la corrida con la muestra
completa. Identico de verdad, sin tolerancia: el motor hace las mismas
operaciones sobre los mismos datos pasados, asi que cualquier diferencia, por
chica que sea, es informacion que vino del otro lado del corte.

Donde se ponen los cortes importa tanto como la comparacion. Una fuga de un
minuto solo cambia algo si el corte cae EXACTAMENTE en el instante de un
evento, y con cortes al azar eso casi nunca pasa. Por eso hay tres clases de
corte (las cantidades estan en config.py):

  evento        el instante exacto de un evento sorteado, mezclando los tres
                tipos;
  mitad_franja  la mitad de una franja que genero eventos, donde una fuga
                intradia se esconde mejor;
  azar          el cierre de una barra cualquiera, despues del primer evento.

Que se compara: todas las columnas de la tabla de eventos menos los resultados
(ret_* y h_fin_franja, que miran el futuro a proposito), mas la volatilidad
reciente en la barra del evento. NO se comparan los grupos de emparejamiento de
la nula (deciles de sigma_ref, tercios de volatilidad reciente, tercio de la
franja): se calculan con la muestra completa POR DISENO, porque la nula es una
herramienta de inferencia ex post y no algo que el motor sepa en t. El tercio,
en particular, usa el fin real de la franja, que depende de hasta donde llegan
los datos. Sus insumos que si existen en t (sigma_ref, volatilidad reciente,
indice de franja, dia de semana) si se comparan.

El calendario de anuncios se entrega completo a todas las corridas: los
anuncios macro tienen fecha publicada de antemano, asi que conocerlos no es
mirar el futuro.
"""
import numpy as np
import pandas as pd

from . import preparar as _preparar_motor
from . import resultados, tiempo

CLASES = ("evento", "mitad_franja", "azar")
COLUMNAS_PRECIO = ["bid_open", "bid_high", "bid_low", "bid_close",
                   "ask_open", "ask_high", "ask_low", "ask_close"]


# =============================================================================
#  Donde cortar
# =============================================================================
def generar_cortes(barras, cal, eventos, cfg, semilla):
    """
    Los instantes de corte, en nanosegundos UTC, con su clase.

    Es el UNICO generador de cortes: lo usan la auditoria real y el test que
    verifica que la auditoria detecta una fuga. Si un tipo no tiene eventos
    suficientes se toman los que haya.

    Devuelve un DataFrame ordenado en el tiempo con columnas `clase`,
    `tipo_evento` (solo en la clase "evento") y `t_corte_ns`.
    """
    rng = np.random.default_rng(semilla)
    filas = []

    # 1. En el instante exacto de un evento, repartiendo entre los tipos.
    tipos = list(cfg.TIPOS_EVENTO)
    cuantos = [len(parte) for parte in
               np.array_split(np.arange(cfg.CORTES_AUDITORIA_EVENTO), len(tipos))]
    for tipo, n in zip(tipos, cuantos):
        instantes = eventos.loc[eventos["tipo"] == tipo, "t_evento_ns"].to_numpy(np.int64)
        elegidos = rng.choice(instantes, size=min(n, len(instantes)), replace=False)
        filas += [{"clase": "evento", "tipo_evento": tipo, "t_corte_ns": int(t)}
                  for t in elegidos]

    # 2. En la mitad de una franja que genero eventos.
    con_eventos = np.unique(eventos["pos_franja"].to_numpy(int))
    elegidas = rng.choice(con_eventos, size=min(cfg.CORTES_AUDITORIA_MITAD_FRANJA,
                                                len(con_eventos)), replace=False)
    inicio = cal["inicio_ns"].to_numpy(np.int64)[elegidas]
    fin = cal["fin_ns"].to_numpy(np.int64)[elegidas]
    mitad = inicio + ((fin - inicio) // 2) // tiempo.NS_MIN * tiempo.NS_MIN
    filas += [{"clase": "mitad_franja", "tipo_evento": "", "t_corte_ns": int(t)}
              for t in mitad]

    # 3. En el cierre de una barra cualquiera, desde el primer evento.
    primero = int(eventos["t_evento_ns"].min())
    cierres = barras.cierre_ns[barras.cierre_ns >= primero]
    elegidos = rng.choice(cierres, size=min(cfg.CORTES_AUDITORIA_AZAR, len(cierres)),
                          replace=False)
    filas += [{"clase": "azar", "tipo_evento": "", "t_corte_ns": int(t)} for t in elegidos]

    tabla = pd.DataFrame(filas).sort_values(["t_corte_ns", "clase"], kind="stable")
    return tabla.reset_index(drop=True)


# =============================================================================
#  Que se compara
# =============================================================================
def conocido_en_t(barras, eventos, cfg):
    """
    Lo que el motor declara de cada evento en su propio instante: todas las
    columnas de la tabla menos los resultados, mas la volatilidad reciente en
    la barra del evento (la misma barra que lee la nula para emparejar).
    """
    columnas = [c for c in eventos.columns
                if not (c.startswith("ret_") or c == "h_fin_franja")]
    tabla = eventos[columnas].reset_index(drop=True).copy()
    vol = resultados.volatilidad_reciente(barras, cfg)
    barra = np.asarray(barras.indice_al_cierre(tabla["t_evento_ns"].to_numpy(np.int64),
                                               cfg.TOLERANCIA_PRECIO_MIN))
    tabla["vol_reciente"] = np.where(barra >= 0, vol[np.maximum(barra, 0)], np.nan)
    return tabla


def _iguales(a, b):
    """Igualdad elemento a elemento; dos NaN cuentan como iguales."""
    a, b = np.asarray(a), np.asarray(b)
    if a.dtype.kind == "f" or b.dtype.kind == "f":
        a, b = a.astype(float), b.astype(float)
        return (a == b) | (np.isnan(a) & np.isnan(b))
    return a == b


def comparar(completa, variante, t_corte_ns):
    """
    Compara los eventos con t_evento <= corte de dos corridas.

    Devuelve un diccionario con cuantos eventos hay en cada una, cuantas filas
    difieren y en que columnas. Si cambia la cantidad de eventos, la
    comparacion fila a fila no tiene sentido y se informa solo eso.
    """
    a = completa[completa["t_evento_ns"] <= t_corte_ns].reset_index(drop=True)
    b = variante[variante["t_evento_ns"] <= t_corte_ns].reset_index(drop=True)
    salida = {"eventos_completa": len(a), "eventos_variante": len(b),
              "filas_distintas": 0, "columnas_distintas": ""}
    if len(a) != len(b):
        salida["filas_distintas"] = abs(len(a) - len(b))
        salida["columnas_distintas"] = "(cantidad de eventos)"
        return salida

    distinta = np.zeros(len(a), dtype=bool)
    columnas = []
    for columna in a.columns:
        iguales = _iguales(a[columna].to_numpy(), b[columna].to_numpy())
        if not iguales.all():
            columnas.append(columna)
            distinta |= ~iguales
    salida["filas_distintas"] = int(distinta.sum())
    salida["columnas_distintas"] = ", ".join(columnas)
    return salida


# =============================================================================
#  La auditoria
# =============================================================================
def _reemplazar_futuro(datos, alternativo, desde):
    """
    Cambia las barras desde la posicion `desde` por las de `alternativo`,
    reescaladas para que empalmen con el ultimo precio anterior al corte.
    """
    otros = datos.copy()
    if desde >= len(datos):
        return otros
    if desde > 0:
        medio_real = (datos["bid_close"].iloc[desde - 1] + datos["ask_close"].iloc[desde - 1]) / 2
        medio_alt = (alternativo["bid_close"].iloc[desde - 1]
                     + alternativo["ask_close"].iloc[desde - 1]) / 2
        factor = medio_real / medio_alt
    else:
        factor = 1.0
    bloque = alternativo[COLUMNAS_PRECIO].to_numpy(float)[desde:] * factor
    otros.iloc[desde:, [otros.columns.get_loc(c) for c in COLUMNAS_PRECIO]] = bloque
    return otros


def auditar(datos, cfg, alternativo, semilla, noticias=None):
    """
    Corre la auditoria completa y devuelve (cortes, detalle).

    `alternativo` es otro mercado con el MISMO indice de minutos: de ahi sale
    el futuro reemplazado. `detalle` tiene una fila por corte y variante con el
    resultado de `comparar`, y `cortes` agrega el veredicto de cada corte.

    El motor se llama por su camino normal (`motor.preparar`), asi que un test
    puede reemplazar una pieza del motor por una version con fuga y ver si la
    auditoria la detecta.
    """
    if not datos.index.equals(alternativo.index):
        raise ValueError("el mercado alternativo tiene que tener el mismo indice de minutos")

    barras, cal, eventos = _preparar_motor(datos, cfg, noticias=noticias)
    completa = conocido_en_t(barras, eventos, cfg)
    cortes = generar_cortes(barras, cal, eventos, cfg, semilla)

    filas = []
    for _, corte in cortes.iterrows():
        t_corte = int(corte["t_corte_ns"])
        hasta = barras.cerradas_hasta(t_corte)       # barras que ya cerraron en el corte
        variantes = {
            "truncada": datos.iloc[:hasta],
            "reemplazada": _reemplazar_futuro(datos, alternativo, hasta),
        }
        for nombre, muestra in variantes.items():
            b, _, ev = _preparar_motor(muestra, cfg, noticias=noticias)
            resultado = comparar(completa, conocido_en_t(b, ev, cfg), t_corte)
            filas.append({"t_corte_ns": t_corte, "variante": nombre, **resultado})

    detalle = pd.DataFrame(filas)
    detalle["pasa"] = detalle["filas_distintas"] == 0
    veredicto = detalle.groupby("t_corte_ns", sort=False)["pasa"].all()
    cortes["pasa"] = cortes["t_corte_ns"].map(veredicto).astype(bool)
    cortes["t_corte_utc"] = tiempo.de_ns(cortes["t_corte_ns"].to_numpy(np.int64))
    return cortes, detalle
