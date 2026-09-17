# -*- coding: utf-8 -*-
"""
FRANJAS — barras, sesiones de mercado y calendario de franjas.

Tres cosas, en este orden:

1. `Barras`: los datos de mercado pasados a arrays de numpy, con el instante de
   CIERRE de cada barra ya calculado. Es la pieza que hace operativa la regla de
   causalidad: en el instante t solo existen las barras cuyo cierre es <= t.
   (Idea copiada de la clase TF de Cuartinhos_Goty, motor.py.)

2. `sesiones`: el mercado no opera el fin de semana. Un hueco de datos mayor a
   HUECO_CIERRE_MIN minutos se lee como un cierre, y parte una sesion nueva.
   Ningun horizonte puede cruzar de una sesion a otra.

3. `calendario`: una fila por franja de 6 horas en hora de Londres, con su
   inicio y fin en UTC, su cobertura y sus extremos. El calendario se arma con
   TODAS las franjas del periodo, tenga datos o no: asi la franja de referencia
   de la franja k siempre es su vecina en el calendario, y una franja sin datos
   se detecta como cobertura cero en vez de pasar inadvertida.

Sobre el horario de verano: los limites (0, 6, 12, 18) son horas de Londres, no
de UTC. La franja [6,12) empieza a las 05:00 UTC en verano y a las 06:00 UTC en
invierno, y el dia del cambio de hora una franja dura 5 o 7 horas. Por eso los
minutos esperados de cada franja se calculan de su inicio y su fin reales, y
nunca se dan por sentados 360.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import tiempo

COLUMNAS = ["bid_open", "bid_high", "bid_low", "bid_close",
            "ask_open", "ask_high", "ask_low", "ask_close"]

LADOS = ["open", "high", "low", "close"]


def agregar_medios(datos):
    """
    Agrega las columnas mid_open, mid_high, mid_low y mid_close.

    mid_X = (bid_X + ask_X) / 2.

    ATENCION: `mid_high` y `mid_low` son una APROXIMACION. El maximo del precio
    medio dentro del minuto no tiene por que coincidir con el promedio del
    maximo del bid y del maximo del ask, porque el spread se mueve dentro del
    minuto. Con el spread tipico del EUR/USD (una fraccion de pip) la diferencia
    es pequena, pero queda declarada aqui y en el pre-registro.
    """
    faltan = [c for c in COLUMNAS if c not in datos.columns]
    if faltan:
        raise ValueError(f"faltan columnas en los datos: {faltan}")
    salida = datos.copy()
    for lado in LADOS:
        salida[f"mid_{lado}"] = (datos[f"bid_{lado}"] + datos[f"ask_{lado}"]) / 2.0
    return salida


def sesiones(apertura_ns, hueco_cierre_min):
    """
    Numera las sesiones de mercado: sube en 1 cada vez que hay un cierre.

    El hueco entre dos barras consecutivas son los minutos SIN DATOS que quedan
    entre el cierre de una y la apertura de la siguiente. Si dos barras son
    consecutivas el hueco es 0. Se considera cierre un hueco mayor que
    `hueco_cierre_min`.
    """
    apertura_ns = np.asarray(apertura_ns, dtype=np.int64)
    if apertura_ns.size == 0:
        return np.zeros(0, dtype=np.int64)
    hueco_min = np.diff(apertura_ns) // tiempo.NS_MIN - 1
    corte = np.concatenate([[False], hueco_min > hueco_cierre_min])
    return np.cumsum(corte).astype(np.int64)


@dataclass
class Barras:
    """
    Los datos de mercado en arrays, listos para comparar instantes con enteros.

    `apertura_ns` es la hora de apertura de cada barra y `cierre_ns` la de su
    cierre, que es cuando su informacion existe. Todo el motor decide con
    `cierre_ns`, nunca con `apertura_ns`.
    """
    indice: pd.DatetimeIndex
    apertura_ns: np.ndarray
    cierre_ns: np.ndarray
    mid_o: np.ndarray
    mid_h: np.ndarray
    mid_l: np.ndarray
    mid_c: np.ndarray
    sesion: np.ndarray

    @classmethod
    def desde(cls, datos, cfg):
        """Construye las barras a partir del DataFrame de mercado."""
        datos = _validar(datos)
        if not all(f"mid_{lado}" in datos.columns for lado in LADOS):
            datos = agregar_medios(datos)
        apertura_ns = tiempo.a_ns(datos.index)
        return cls(
            indice=datos.index,
            apertura_ns=apertura_ns,
            cierre_ns=tiempo.cierre_ns(apertura_ns),
            mid_o=datos["mid_open"].to_numpy(float),
            mid_h=datos["mid_high"].to_numpy(float),
            mid_l=datos["mid_low"].to_numpy(float),
            mid_c=datos["mid_close"].to_numpy(float),
            sesion=sesiones(apertura_ns, cfg.HUECO_CIERRE_MIN),
        )

    def __len__(self):
        return len(self.apertura_ns)

    def cerradas_hasta(self, t_ns):
        """Cuantas barras tienen su cierre en t_ns o antes (las observables en t)."""
        return int(np.searchsorted(self.cierre_ns, t_ns, side="right"))

    def indice_al_cierre(self, t_ns, tolerancia_min=0):
        """
        Posicion de la barra que cierra en t_ns, o -1 si no existe.

        Con `tolerancia_min` > 0 se acepta la ultima barra que haya cerrado
        dentro de los `tolerancia_min` minutos anteriores a t_ns. Sirve para
        datos con huecos de uno o dos minutos. Nunca mira hacia adelante.
        """
        t = np.asarray(t_ns, dtype=np.int64)
        j = np.searchsorted(self.cierre_ns, t, side="right") - 1
        limite = t - int(tolerancia_min) * tiempo.NS_MIN
        valido = (j >= 0) & (self.cierre_ns[np.maximum(j, 0)] >= limite)
        salida = np.where(valido, j, -1)
        return int(salida) if np.isscalar(t_ns) or np.ndim(t_ns) == 0 else salida


def _validar(datos):
    """Revisa las condiciones que el resto del motor da por sentadas."""
    if not isinstance(datos.index, pd.DatetimeIndex):
        raise ValueError("el indice de los datos debe ser de fechas")
    if datos.index.tz is None:
        raise ValueError("el indice de los datos debe traer zona horaria (UTC)")
    if not datos.index.is_monotonic_increasing:
        raise ValueError("el indice debe venir ordenado de menor a mayor")
    if datos.index.has_duplicates:
        raise ValueError("el indice tiene minutos repetidos")
    apertura_ns = tiempo.a_ns(datos.index)
    if np.any(apertura_ns % tiempo.NS_MIN != 0):
        raise ValueError("hay barras que no empiezan en un minuto exacto")
    return datos


def calendario(barras, cfg):
    """
    Una fila por franja de 6 horas, ordenadas en el tiempo.

    Columnas:
      fecha_londres     dia de Londres al que pertenece la franja (sin zona)
      idx_franja        0..3 segun LIMITES_HORAS
      dia_semana        0 = lunes ... 6 = domingo, segun la fecha de Londres
      inicio_ns/fin_ns  limites de la franja en nanosegundos UTC
      minutos_esperados duracion real de la franja (5, 6 o 7 horas si hay cambio
                        de hora)
      minutos_presentes barras con datos dentro de la franja
      cobertura         presentes / esperados
      H, L              maximo de mid_high y minimo de mid_low de la franja
      rango             H - L
      i0, i1            posiciones de las barras de la franja: barras[i0:i1]
      sesion            sesion de mercado de la primera barra de la franja
                        (-1 si la franja no tiene datos)
      hueco_inicial     minutos entre el inicio de la franja y su primera barra
                        (infinito si la franja no tiene datos). Un hueco grande
                        significa que la franja EMPEZO con el mercado cerrado,
                        que es lo que pasa la tarde del domingo.

    El calendario incluye franjas SIN datos (cobertura 0). Eso es a proposito:
    la franja de referencia de la franja k es siempre la fila anterior, asi que
    una franja que falta invalida la siguiente en vez de colarse sin avisar.
    """
    if len(barras) == 0:
        raise ValueError("no hay barras para construir el calendario")

    limites = list(cfg.LIMITES_HORAS[:-1])
    local = tiempo.a_zona(barras.indice, cfg.ZONA)
    fechas = pd.DatetimeIndex(local.normalize()).tz_localize(None)
    # Un dia extra al final: sirve para que la ultima franja tenga su "fin".
    dias = pd.date_range(fechas.min(), fechas.max() + pd.Timedelta(days=1), freq="D")

    fecha_rep = pd.DatetimeIndex(np.repeat(dias.values, len(limites)))
    hora_rep = np.tile(np.array(limites, dtype="int64"), len(dias))
    # tz_localize sin argumentos extra revienta si alguna hora fuera ambigua o
    # inexistente por el cambio de horario. Con limites 0/6/12/18 en Londres eso
    # no pasa, y si algun dia cambiara la regla preferimos el error al silencio.
    inicio_local = fecha_rep + pd.to_timedelta(hora_rep, unit="h")
    bordes_ns = tiempo.a_ns(inicio_local.tz_localize(cfg.ZONA))

    n = len(dias) * len(limites) - len(limites)      # se descarta el dia extra
    cal = pd.DataFrame({
        "fecha_londres": fecha_rep[:n],
        "idx_franja": np.tile(np.arange(len(limites)), len(dias))[:n],
        "inicio_ns": bordes_ns[:n],
        "fin_ns": bordes_ns[1:n + 1],
    })
    cal["dia_semana"] = cal["fecha_londres"].dt.dayofweek
    cal["minutos_esperados"] = (cal["fin_ns"] - cal["inicio_ns"]) // tiempo.NS_MIN

    # A que franja pertenece cada barra. Los bordes vienen ordenados, asi que
    # una sola busqueda binaria basta.
    pos = np.searchsorted(cal["inicio_ns"].to_numpy(), barras.apertura_ns, side="right") - 1
    if pos.min() < 0:
        raise ValueError("hay barras anteriores al inicio del calendario")

    resumen = pd.DataFrame({"pos": pos, "h": barras.mid_h, "l": barras.mid_l}).groupby("pos")
    agregado = resumen.agg(minutos_presentes=("h", "size"), H=("h", "max"), L=("l", "min"))
    agregado = agregado.reindex(range(n))
    cal["minutos_presentes"] = agregado["minutos_presentes"].fillna(0).to_numpy(int)
    cal["H"] = agregado["H"].to_numpy(float)
    cal["L"] = agregado["L"].to_numpy(float)
    cal["rango"] = cal["H"] - cal["L"]
    cal["cobertura"] = cal["minutos_presentes"] / cal["minutos_esperados"]

    cal["i0"] = np.searchsorted(pos, np.arange(n), side="left")
    cal["i1"] = np.searchsorted(pos, np.arange(n), side="right")
    hay = cal["minutos_presentes"].to_numpy() > 0
    primera = np.minimum(cal["i0"].to_numpy(), len(barras) - 1)
    cal["sesion"] = np.where(hay, barras.sesion[primera], -1)
    demora = (barras.apertura_ns[primera] - cal["inicio_ns"].to_numpy()) / tiempo.NS_MIN
    cal["hueco_inicial"] = np.where(hay, demora, np.inf)
    return cal


def etiquetas_por_minuto(barras, cal):
    """
    Para cada barra: a que franja del calendario pertenece y sus etiquetas.

    Lo usa la hipotesis nula, que necesita sortear minutos con el mismo indice
    de franja y el mismo dia de semana que el evento real.
    """
    pos = np.searchsorted(cal["inicio_ns"].to_numpy(), barras.apertura_ns, side="right") - 1
    return pd.DataFrame({
        "pos_franja": pos,
        "fecha_londres": cal["fecha_londres"].to_numpy()[pos],
        "idx_franja": cal["idx_franja"].to_numpy()[pos],
        "dia_semana": cal["dia_semana"].to_numpy()[pos],
    }, index=barras.indice)
