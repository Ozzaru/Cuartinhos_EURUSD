# -*- coding: utf-8 -*-
"""
DESCARGA DE HISTDATA — EUR/USD, velas de 1 minuto (Generic ASCII), un zip por ano.

Terminos (revisados el 01-10-2026): histdata.com no publica terminos de uso.
Su FAQ solo advierte que los datos son gratuitos y sin garantia ("use the data
at your own will and risk"); no pide registro y su robots.txt solo cierra
/wp-admin/. El acceso por FTP es pagado y es solo por velocidad. La descarga
gratuita es el formulario de cada pagina: un POST a get.php con un token que
trae la propia pagina. Este script hace lo mismo que un clic, uno por ano, con
pausas.

Reglas:
  - nada desde DESCARGA_TOPE (el inicio del sellado): un ano que lo toque se
    rechaza antes de pedir nada;
  - una pausa de DESCARGA_PAUSA_SEG entre pedidos y reintentos con espera
    creciente;
  - se puede retomar: un zip que ya esta y calza con el manifiesto no se vuelve
    a pedir;
  - se escribe a un archivo ".parcial" y se renombra al final, asi un corte a
    mitad no deja un zip roto con nombre valido;
  - cada zip queda en el manifiesto (registro/manifiesto_datos.csv).

Los zip se guardan tal como llegan; no se descomprimen aqui. La lectura de los
precios la hace solo el cargador.

Uso:
    python -m fuentes.descarga_histdata                 todos los anos de HISTDATA_ANIOS
    python -m fuentes.descarga_histdata --anios 2016    uno o varios anos
"""
import argparse
import datetime as dt
import http.cookiejar
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                   # noqa: E402
from fuentes import manifiesto  # noqa: E402

AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Cuartinhos_EURUSD/1.0 "
          "(tesis academica; descarga anual con pausas)")
_FORMULARIO = re.compile(r'<form id="file_down"(.*?)</form>', re.S)
_CAMPO = re.compile(r'<input type="hidden" name="(\w+)" id="\w+" value="([^"]*)"')


class SelladoError(PermissionError):
    """Se pidio algo del tramo sellado (o posterior) antes de la Etapa 5."""


def exigir_antes_del_sellado(desde, hasta, cfg=None):
    """Rechaza cualquier rango que llegue al inicio del sellado o lo pase."""
    cfg = cfg or config
    tope = dt.date.fromisoformat(cfg.DESCARGA_TOPE)
    for fecha in (desde, hasta):
        if dt.date.fromisoformat(str(fecha)) >= tope:
            raise SelladoError(
                f"{fecha}: nada desde el {tope} se descarga hasta la Etapa 5 (tramo sellado)")


def nombre_zip(anio):
    return f"HISTDATA_COM_ASCII_EURUSD_M1{anio}.zip"


def _abridor():
    abridor = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    abridor.addheaders = [("User-Agent", AGENTE)]
    return abridor


def _pedir_zip(abridor, anio, cfg):
    """Un intento: la pagina del ano, su formulario y el POST que devuelve el zip."""
    pagina = cfg.HISTDATA_PAGINA.format(anio=anio)
    with abridor.open(pagina, timeout=cfg.DESCARGA_TIMEOUT_SEG) as r:
        html = r.read().decode("utf-8", errors="replace")
    formulario = _FORMULARIO.search(html)
    if formulario is None:
        raise RuntimeError(f"{anio}: la pagina no trae el formulario de descarga")
    campos = dict(_CAMPO.findall(formulario.group(1)))
    if "tk" not in campos or campos.get("fxpair") != "EURUSD" or campos.get("timeframe") != "M1":
        raise RuntimeError(f"{anio}: formulario inesperado: {sorted(campos)}")
    time.sleep(cfg.DESCARGA_PAUSA_SEG)
    pedido = urllib.request.Request(
        cfg.HISTDATA_POST, data=urllib.parse.urlencode(campos).encode(),
        headers={"Referer": pagina, "Origin": "https://www.histdata.com"})
    with abridor.open(pedido, timeout=cfg.DESCARGA_TIMEOUT_SEG) as r:
        contenido = r.read()
    if not contenido.startswith(b"PK"):
        raise RuntimeError(f"{anio}: la respuesta no es un zip ({contenido[:60]!r})")
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        if z.testzip() is not None:
            raise RuntimeError(f"{anio}: zip corrupto")
        if not any(n.lower().endswith(f"{anio}.csv") for n in z.namelist()):
            raise RuntimeError(f"{anio}: el zip no trae el CSV del ano: {z.namelist()}")
    return pagina, contenido


def descargar_anio(anio, cfg=None, repo=None, abridor=None):
    """Baja un ano si hace falta. Devuelve 'ya estaba' o 'descargado'."""
    cfg = cfg or config
    exigir_antes_del_sellado(f"{anio}-01-01", f"{anio}-12-31", cfg)
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "histdata")
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, nombre_zip(anio))
    if os.path.exists(destino) and manifiesto.registrado(destino, cfg, repo):
        return "ya estaba"

    abridor = abridor or _abridor()
    for intento in range(1, cfg.DESCARGA_REINTENTOS + 1):
        try:
            pagina, contenido = _pedir_zip(abridor, anio, cfg)
            break
        except Exception as error:   # red, servidor o formato: se reintenta igual
            if intento == cfg.DESCARGA_REINTENTOS:
                raise
            espera = cfg.DESCARGA_PAUSA_SEG * 2 ** intento
            print(f"  {anio}: intento {intento} fallo ({error}); espero {espera} s", flush=True)
            time.sleep(espera)

    parcial = destino + ".parcial"
    with open(parcial, "wb") as f:
        f.write(contenido)
    os.replace(parcial, destino)
    manifiesto.registrar(destino, "histdata", pagina, cfg=cfg, repo=repo)
    return "descargado"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Descarga de HistData (EUR/USD M1)")
    parser.add_argument("--anios", type=int, nargs="+",
                        default=list(range(config.HISTDATA_ANIOS[0], config.HISTDATA_ANIOS[1] + 1)))
    args = parser.parse_args(argv)
    for anio in args.anios:   # se valida todo antes de pedir nada
        exigir_antes_del_sellado(f"{anio}-01-01", f"{anio}-12-31")
    abridor = _abridor()
    comienzo = time.perf_counter()
    for k, anio in enumerate(args.anios):
        estado = descargar_anio(anio, abridor=abridor)
        print(f"{anio}: {estado}  ({time.perf_counter() - comienzo:.0f} s)", flush=True)
        if estado == "descargado" and k < len(args.anios) - 1:
            time.sleep(config.DESCARGA_PAUSA_SEG)


if __name__ == "__main__":
    main()
