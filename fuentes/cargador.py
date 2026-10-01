# -*- coding: utf-8 -*-
"""
CARGADOR — la unica puerta por la que pasan los precios reales.

Pre-registro, seccion 2.4, y regla 3 del punto G. Hace tres cosas.

1. EL CANDADO. Toda lectura de precios procesados pasa por `leer`:
   - Mientras NO exista la etiqueta `prerregistro-v1`, solo entrega datos al
     modulo de calidad (`fuentes.calidad`, con proposito "calidad"), en
     cualquier tramo salvo el sellado. Cualquier otro pedido es un error.
   - Cuando exista la etiqueta, rige la seccion 2.4: el desarrollo se lee
     libre; validacion y sellado exigen la bandera `abrir="validacion"` o
     `abrir="sellado"`. El modulo de calidad sigue pudiendo leer validacion.
   - Toda lectura que toca validacion, y toda apertura, exige el arbol de git
     limpio y deja ANTES una linea en `registro/aperturas.md`: fecha UTC,
     clase, tramo, fuente, proposito, rango, commit y usuario de git. Las
     clases son las del pre-registro: "lectura de calidad" y "apertura".
     El arbol limpio admite una sola excepcion: el propio
     `registro/aperturas.md`, que es lo que el cargador escribe. Sin ella, la
     segunda lectura de una misma corrida ya no podria hacerse. Con dos
     condiciones (decision del grupo): ese archivo solo crece (el candado
     revisa que empiece exactamente con su version del ultimo commit) y se
     commitea al cierre de cada sesion de trabajo.

2. LA CONVERSION de los crudos a parquet (`convertir`): un archivo por fuente
   y ano UTC, con el indice en la hora de APERTURA de cada barra. Antes de leer
   un crudo verifica que siga igual a como quedo en el manifiesto. Cualquier
   minuto desde el inicio del sellado es un error. La conversion no le entrega
   precios a nadie, pero tambien los lee: si el rango toca validacion, sigue
   la misma regla y queda anotada como lectura de calidad.

3. QUE BARRA CUENTA (`diagnostico` y `limpiar`). Pasan a faltantes, sin
   corregirlas (pre-registro 3.3 y 3.4):
   - las velas planas de Dukascopy: minutos sin ticks, que la exportacion
     rellena con volumen 0 (incluido el fin de semana);
   - las barras invalidas: maximo < apertura o cierre, minimo > apertura o
     cierre, o spread (ask - bid) <= 0 en cualquiera de los cuatro precios, o
     un lado faltante.
   El modulo de calidad recibe todo, para poder contarlas; cualquier otro
   proposito recibe los datos ya limpios.

Los tramos se deciden por la fecha UTC del rango pedido. En los dos bordes
(1 de enero de 2017 y de 2021) Londres esta en GMT, asi que esa fecha coincide
con la de Londres, que es la que define el tramo de un evento (2.3).

Uso (conversion):
    python -m fuentes.cargador --convertir histdata --desde 2016-01-01 --hasta 2016-12-31
"""
import argparse
import datetime as dt
import glob
import io
import os
import shutil
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                             # noqa: E402
from fuentes import formatos, manifiesto  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO_APERTURAS = "registro/aperturas.md"
MODULO_CALIDAD = "fuentes.calidad"
PROPOSITO_CALIDAD = "calidad"
TRAMOS = ("desarrollo", "validacion", "sellado")

ENCABEZADO_APERTURAS = """# Registro de lecturas de precios

Lo escribe solo `fuentes/cargador.py` (pre-registro, seccion 2.4). Una linea por
lectura, escrita ANTES de entregar o convertir los datos. Clases:

- **lectura de calidad**: el control de calidad (o la conversion a parquet) lee
  un rango que toca validacion antes de abrirla. Nunca calcula retornos
  posteriores a eventos.
- **apertura**: la apertura unica de validacion (Etapa 3) o del sellado (Etapa 5).

| fecha UTC | clase | tramo | fuente | proposito | rango (UTC) | commit | usuario de git |
|---|---|---|---|---|---|---|---|
"""

COLUMNAS_DUKASCOPY = (
    [f"bid_{x}" for x in formatos.LADOS] + [f"ask_{x}" for x in formatos.LADOS]
    + [f"mid_{x}" for x in formatos.LADOS] + ["bid_volumen", "ask_volumen"])
COLUMNAS_HISTDATA = [f"bid_{x}" for x in formatos.LADOS] + ["volumen"]


class CandadoError(PermissionError):
    """El candado no deja pasar este pedido."""


# -----------------------------------------------------------------------------
#  Rangos y tramos
# -----------------------------------------------------------------------------
def rango(desde, hasta):
    """[inicio, fin) en UTC para dos fechas 'AAAA-MM-DD' incluidas las dos."""
    ini = pd.Timestamp(dt.date.fromisoformat(str(desde)), tz="UTC")
    fin = pd.Timestamp(dt.date.fromisoformat(str(hasta)), tz="UTC") + pd.Timedelta(days=1)
    if fin <= ini:
        raise ValueError(f"rango vacio: {desde} a {hasta}")
    return ini, fin


def tramos(desde, hasta, cfg=None):
    """Que tramos toca el rango: desarrollo, validacion y/o sellado."""
    cfg = cfg or config
    ini, fin = rango(desde, hasta)
    inicio_val = pd.Timestamp(cfg.VALIDACION[0], tz="UTC")
    inicio_sel = pd.Timestamp(cfg.SELLADO[0], tz="UTC")
    toca = []
    if ini < inicio_val:
        toca.append("desarrollo")
    if ini < inicio_sel and fin > inicio_val:
        toca.append("validacion")
    if fin > inicio_sel:
        toca.append("sellado")
    return toca


# -----------------------------------------------------------------------------
#  Git
# -----------------------------------------------------------------------------
def _git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} fallo: {r.stderr.strip()}")
    return r


def existe_etiqueta(repo, etiqueta):
    return _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{etiqueta}",
                check=False).returncode == 0


def cambios_pendientes(repo):
    """Lo que `git status` muestra, menos registro/aperturas.md."""
    salida = _git(repo, "status", "--porcelain", "--untracked-files=all").stdout
    lineas = [l for l in salida.splitlines() if l.strip()]
    return [l for l in lineas if l[3:].strip().strip('"') != REGISTRO_APERTURAS]


def exigir_solo_agregados(repo):
    """
    registro/aperturas.md solo crece: a lo commiteado se le agregan lineas al
    final, nunca se edita ni se borra nada (decision del grupo, punto G). Si
    el archivo de trabajo no empieza exactamente con la version del ultimo
    commit, el candado no deja pasar nada.
    """
    ruta = os.path.join(repo, REGISTRO_APERTURAS)
    commiteado = _git(repo, "show", f"HEAD:{REGISTRO_APERTURAS}", check=False)
    if commiteado.returncode != 0:
        return                                   # todavia no esta en el repositorio
    if not os.path.exists(ruta):
        raise CandadoError(f"{REGISTRO_APERTURAS} fue borrado: solo admite lineas agregadas")
    with open(ruta, encoding="utf-8", newline="") as f:
        actual = f.read().replace("\r\n", "\n")
    if not actual.startswith(commiteado.stdout.replace("\r\n", "\n")):
        raise CandadoError(f"{REGISTRO_APERTURAS} tiene lineas editadas o borradas respecto del "
                           "ultimo commit: solo admite lineas agregadas al final")


def exigir_arbol_limpio(repo):
    pendientes = cambios_pendientes(repo)
    if pendientes:
        raise CandadoError(
            "el arbol de git no esta limpio: lo que lee validacion tiene que ser "
            "codigo commiteado. Pendiente:\n  " + "\n  ".join(pendientes))
    exigir_solo_agregados(repo)


def anotar(repo, clase, tramos_tocados, fuente, proposito, desde, hasta):
    """Agrega una linea a registro/aperturas.md. Devuelve la linea."""
    exigir_solo_agregados(repo)
    ruta = os.path.join(repo, REGISTRO_APERTURAS)
    commit = _git(repo, "rev-parse", "HEAD").stdout.strip()
    usuario = _git(repo, "config", "user.name", check=False).stdout.strip() or "(sin user.name)"
    ahora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    linea = (f"| {ahora} | {clase} | {', '.join(tramos_tocados)} | {fuente} | {proposito} "
             f"| {desde} a {hasta} | {commit} | {usuario} |\n")
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", encoding="utf-8", newline="\n") as f:
        if nuevo:
            f.write(ENCABEZADO_APERTURAS)
        f.write(linea)
    return linea


# -----------------------------------------------------------------------------
#  El candado
# -----------------------------------------------------------------------------
def _modulo_de(marco):
    """Nombre del modulo de un marco de llamada (el de -m si corre como script)."""
    nombre = marco.f_globals.get("__name__", "")
    if nombre == "__main__":
        spec = marco.f_globals.get("__spec__")
        nombre = spec.name if spec is not None else nombre
    return nombre


def autorizar(tramos_tocados, proposito, abrir, llamador, cfg, repo):
    """
    Decide si un pedido pasa y que linea deja. Devuelve la clase de linea
    ("lectura de calidad", "apertura") o None si no hace falta anotar.
    Levanta CandadoError si no pasa.
    """
    if abrir not in (None, "validacion", "sellado"):
        raise ValueError(f"abrir tiene que ser None, 'validacion' o 'sellado', no {abrir!r}")

    if proposito == PROPOSITO_CALIDAD:
        if llamador != MODULO_CALIDAD:
            raise CandadoError(f"solo {MODULO_CALIDAD} puede leer con proposito "
                               f"'{PROPOSITO_CALIDAD}' (lo pidio {llamador})")
        if "sellado" in tramos_tocados:
            raise CandadoError("el control de calidad no lee el sellado en esta etapa")
        if "validacion" in tramos_tocados:
            exigir_arbol_limpio(repo)
            return "lectura de calidad"
        return None

    if not existe_etiqueta(repo, cfg.ETIQUETA_PRERREGISTRO):
        raise CandadoError(
            f"no existe la etiqueta {cfg.ETIQUETA_PRERREGISTRO}: hasta el congelamiento, "
            f"el cargador solo entrega datos al modulo de calidad (pidio {llamador}, "
            f"proposito {proposito!r})")

    restringidos = [t for t in tramos_tocados if t != "desarrollo"]
    if not restringidos:
        return None
    if len(restringidos) > 1 or abrir != restringidos[0]:
        raise CandadoError(f"el rango toca {restringidos}: se abre solo con "
                           f"abrir='{restringidos[-1]}', un tramo por vez")
    exigir_arbol_limpio(repo)
    return "apertura"


def _archivo_procesado(fuente, anio, cfg):
    return os.path.join(cfg.RUTA_PROCESADOS, fuente, f"{fuente}_EURUSD_M1_{anio}.parquet")


def leer(fuente, desde, hasta, proposito, abrir=None, cfg=None, repo=None):
    """
    Precios procesados de una fuente entre dos fechas UTC (incluidas).

    Pasa por el candado (ver arriba). Con proposito "calidad" devuelve todas
    las barras, planas e invalidas incluidas; con cualquier otro, solo las que
    cuentan (`limpiar`).
    """
    cfg = cfg or config
    repo = repo or RAIZ
    llamador = _modulo_de(sys._getframe(1))
    if fuente not in cfg.FUENTES:
        raise ValueError(f"fuente desconocida: {fuente}")
    ini, fin = rango(desde, hasta)
    tocados = tramos(desde, hasta, cfg)
    clase = autorizar(tocados, proposito, abrir, llamador, cfg, repo)

    archivos = [_archivo_procesado(fuente, a, cfg)
                for a in range(ini.year, (fin - pd.Timedelta(1, "ns")).year + 1)]
    faltan = [a for a in archivos if not os.path.exists(a)]
    if faltan:
        raise FileNotFoundError("faltan datos procesados (hay que convertir antes):\n  "
                                + "\n  ".join(faltan))
    if clase is not None:
        anotar(repo, clase, tocados, fuente, proposito, desde, hasta)

    datos = pd.concat([pd.read_parquet(a) for a in archivos])
    datos = datos[(datos.index >= ini) & (datos.index < fin)]
    return datos if proposito == PROPOSITO_CALIDAD else limpiar(datos, fuente)


# -----------------------------------------------------------------------------
#  Que barra cuenta
# -----------------------------------------------------------------------------
def _ohlc_roto(datos, lado):
    o, h, l, c = (datos[f"{lado}_{x}"] for x in formatos.LADOS)
    sano = (h >= o) & (h >= c) & (l <= o) & (l <= c)
    return ~sano.to_numpy()


def diagnostico(datos, fuente):
    """
    Una fila por barra, con marcas booleanas:
      plana        Dukascopy: volumen 0 en algun lado (minuto sin ticks).
      falta_lado   Dukascopy: un lado no vino.
      ohlc_bid     maximo o minimo del bid inconsistente con apertura y cierre.
      ohlc_ask     lo mismo en el ask (Dukascopy).
      spread       ask - bid <= 0 en alguno de los cuatro precios (Dukascopy).
      invalida     barra no plana con cualquiera de los problemas anteriores.
    """
    n = len(datos)
    marcas = pd.DataFrame(index=datos.index)
    if fuente == "dukascopy":
        bid = datos[[f"bid_{x}" for x in formatos.LADOS]].to_numpy()
        ask = datos[[f"ask_{x}" for x in formatos.LADOS]].to_numpy()
        marcas["plana"] = ((datos["bid_volumen"] == 0) | (datos["ask_volumen"] == 0)).to_numpy()
        marcas["falta_lado"] = np.isnan(bid).any(axis=1) | np.isnan(ask).any(axis=1)
        marcas["ohlc_bid"] = _ohlc_roto(datos, "bid")
        marcas["ohlc_ask"] = _ohlc_roto(datos, "ask")
        with np.errstate(invalid="ignore"):
            marcas["spread"] = ((ask - bid) <= 0).any(axis=1)
    else:
        bid = datos[[f"bid_{x}" for x in formatos.LADOS]].to_numpy()
        marcas["plana"] = np.zeros(n, dtype=bool)
        marcas["falta_lado"] = np.isnan(bid).any(axis=1)
        marcas["ohlc_bid"] = _ohlc_roto(datos, "bid")
    problemas = [c for c in marcas.columns if c != "plana"]
    marcas["invalida"] = ~marcas["plana"] & marcas[problemas].any(axis=1)
    return marcas


def limpiar(datos, fuente):
    """Solo las barras que cuentan: sin velas planas ni barras invalidas."""
    marcas = diagnostico(datos, fuente)
    return datos[~(marcas["plana"] | marcas["invalida"]).to_numpy()]


# -----------------------------------------------------------------------------
#  Conversion de crudos a parquet
# -----------------------------------------------------------------------------
def _exigir_antes_del_tope(indice, nombre, cfg):
    tope = pd.Timestamp(cfg.DESCARGA_TOPE, tz="UTC")
    despues = int((indice >= tope).sum())
    if despues:
        raise CandadoError(f"{nombre}: {despues} minutos desde el {cfg.DESCARGA_TOPE} "
                           "(sellado). No se convierte nada.")


def _unico(tabla, nombre):
    """Junta minutos repetidos (dos exportaciones que se solapan) si dicen lo mismo."""
    tabla = tabla.sort_index(kind="stable")
    repetidos = tabla.index.duplicated(keep=False)
    if repetidos.any():
        grupos = tabla[repetidos].groupby(level=0).nunique(dropna=False)
        if (grupos > 1).any().any():
            raise ValueError(f"{nombre}: hay minutos repetidos con precios distintos")
        tabla = tabla[~tabla.index.duplicated(keep="first")]
    return tabla


def _escribir(tabla, fuente, anio, cfg):
    ruta = _archivo_procesado(fuente, anio, cfg)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tabla.to_parquet(ruta + ".parcial", engine="pyarrow")
    os.replace(ruta + ".parcial", ruta)
    return ruta


def _crudos(fuente, patron, cfg, repo):
    archivos = sorted(glob.glob(os.path.join(cfg.RUTA_CRUDOS, fuente, patron)))
    if not archivos:
        raise FileNotFoundError(f"no hay crudos de {fuente} en {cfg.RUTA_CRUDOS}")
    for a in archivos:
        manifiesto.verificar(a, cfg, repo)
    return archivos


def _convertir_histdata(ini, fin, cfg, repo):
    resumen = []
    por_anio = {}
    for archivo in _crudos("histdata", "*.zip", cfg, repo):
        with zipfile.ZipFile(archivo) as z:
            csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if len(csvs) != 1:
                raise formatos.FormatoError(f"{archivo}: se esperaba un CSV y trae {csvs}")
            with z.open(csvs[0]) as crudo:
                tabla = formatos.histdata_m1(io.TextIOWrapper(crudo, encoding="ascii"),
                                             cfg.HISTDATA_HORAS_A_UTC)
        _exigir_antes_del_tope(tabla.index, archivo, cfg)
        tabla.columns = COLUMNAS_HISTDATA
        dentro = (tabla.index >= ini) & (tabla.index < fin)
        resumen.append((os.path.basename(archivo), len(tabla), int(dentro.sum())))
        for anio, trozo in tabla[dentro].groupby(tabla.index[dentro].year):
            por_anio.setdefault(anio, []).append(trozo)
    escritos = {}
    for anio, trozos in sorted(por_anio.items()):
        tabla = _unico(pd.concat(trozos), f"histdata {anio}")
        escritos[anio] = (_escribir(tabla, "histdata", anio, cfg), len(tabla))
    return resumen, escritos


def _lado_dukascopy(nombre):
    n = os.path.basename(nombre).lower()
    lados = [lado for lado in ("bid", "ask") if lado in n]
    if len(lados) != 1:
        raise formatos.FormatoError(f"{nombre}: el nombre tiene que decir Bid o Ask (uno solo)")
    return lados[0]


def _convertir_dukascopy(ini, fin, cfg, repo):
    """
    Dos pasadas, para no tener millones de filas de los dos lados en memoria:
    cada CSV se lee por trozos a partes temporales por lado y ano; despues,
    ano por ano, se juntan bid y ask.
    """
    partes = os.path.join(cfg.RUTA_PROCESADOS, "_partes_dukascopy")
    shutil.rmtree(partes, ignore_errors=True)
    os.makedirs(partes)
    resumen = []
    anios = set()
    for archivo in _crudos("dukascopy", "*.csv", cfg, repo):
        lado = _lado_dukascopy(archivo)
        total = dentro_total = 0
        with open(archivo, encoding="utf-8-sig", newline="") as flujo:
            for k, trozo in enumerate(formatos.dukascopy_jforex(flujo)):
                _exigir_antes_del_tope(trozo.index, archivo, cfg)
                dentro = (trozo.index >= ini) & (trozo.index < fin)
                total += len(trozo)
                dentro_total += int(dentro.sum())
                trozo = trozo[dentro]
                trozo.columns = [f"{lado}_{x}" for x in formatos.LADOS] + [f"{lado}_volumen"]
                for anio, sub in trozo.groupby(trozo.index.year):
                    anios.add(anio)
                    nombre = f"{lado}_{anio}_{os.path.basename(archivo)}_{k}.parquet"
                    sub.to_parquet(os.path.join(partes, nombre), engine="pyarrow")
        resumen.append((os.path.basename(archivo), total, dentro_total))

    escritos = {}
    for anio in sorted(anios):
        lados = {}
        for lado in ("bid", "ask"):
            piezas = sorted(glob.glob(os.path.join(partes, f"{lado}_{anio}_*.parquet")))
            if not piezas:
                raise FileNotFoundError(f"dukascopy {anio}: no hay datos del lado {lado}")
            lados[lado] = _unico(pd.concat([pd.read_parquet(p) for p in piezas]),
                                 f"dukascopy {lado} {anio}")
        tabla = lados["bid"].join(lados["ask"], how="outer")
        for x in formatos.LADOS:
            tabla[f"mid_{x}"] = (tabla[f"bid_{x}"] + tabla[f"ask_{x}"]) / 2.0
        tabla = tabla[COLUMNAS_DUKASCOPY]
        escritos[anio] = (_escribir(tabla, "dukascopy", anio, cfg), len(tabla))
    shutil.rmtree(partes, ignore_errors=True)
    return resumen, escritos


def convertir(fuente, desde, hasta, cfg=None, repo=None):
    """
    Convierte los crudos de una fuente a parquet por ano UTC, solo en el rango
    pedido. Devuelve (resumen por archivo, {ano: (ruta, filas)}).

    Toda linea de los crudos se interpreta (para eso hay que leerla), pero solo
    se escribe lo que cae en el rango. Si el rango toca validacion, la
    conversion queda anotada como lectura de calidad y exige el arbol limpio.
    """
    cfg = cfg or config
    repo = repo or RAIZ
    ini, fin = rango(desde, hasta)
    tocados = tramos(desde, hasta, cfg)
    if "sellado" in tocados:
        raise CandadoError("el sellado no se convierte hasta la Etapa 5")
    if "validacion" in tocados:
        exigir_arbol_limpio(repo)
        anotar(repo, "lectura de calidad", tocados, fuente, "conversion a parquet", desde, hasta)
    if fuente == "histdata":
        return _convertir_histdata(ini, fin, cfg, repo)
    if fuente == "dukascopy":
        return _convertir_dukascopy(ini, fin, cfg, repo)
    raise ValueError(f"fuente desconocida: {fuente}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Conversion de crudos a parquet en UTC")
    parser.add_argument("--convertir", choices=config.FUENTES, required=True)
    parser.add_argument("--desde", required=True)
    parser.add_argument("--hasta", required=True)
    args = parser.parse_args(argv)
    resumen, escritos = convertir(args.convertir, args.desde, args.hasta)
    for nombre, total, dentro in resumen:
        print(f"{nombre}: {total} filas, {dentro} en el rango")
    for anio, (ruta, filas) in escritos.items():
        print(f"{anio}: {filas} filas -> {ruta}")


if __name__ == "__main__":
    main()
