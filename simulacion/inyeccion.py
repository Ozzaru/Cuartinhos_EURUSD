# -*- coding: utf-8 -*-
"""
INYECCION — agrega un efecto conocido a un mercado simulado.

Que se inyecta (definicion acordada en el punto E):

  - Solo en los tipos de la familia principal: sostenida y reingreso. La
    ruptura queda limpia.
  - En la direccion que predicen H1 y H2: la sostenida CONTINUA (+delta) y el
    reingreso se DEVUELVE (-delta), siempre medido en la direccion de la
    ruptura. El signo sale de la cola de cada prueba en FAMILIA_PRINCIPAL, asi
    que no hay dos lugares donde se defina.
  - El MISMO delta en todos los horizontes. Despues de un evento en t, al
    logaritmo del precio en t + tau se le suma

        direccion * signo * delta * sigma_ref * raiz(tau)

    hasta el fin de la franja del evento (o el cierre del mercado, lo que
    llegue primero: el mismo fin que usa el horizonte "fin_franja"), y de ahi
    en adelante queda fijo. Como el retorno normalizado divide por
    sigma_ref * raiz(h), a cualquier horizonte h dentro de la franja el retorno
    del evento sube exactamente delta en su direccion. Una deriva lineal no
    serviria: daria un delta que crece con raiz(h).
  - Consecuencia declarada: si el horizonte cruza el fin de la franja (el de
    120 minutos en eventos tardios, o cualquier horizonte fijo cerca del
    final), la deriva ya quedo fija y el delta realizado es menor POR
    CONSTRUCCION: delta * raiz(T / h), con T los minutos de franja que
    quedaban.

Como se aplica a las barras:

  - Se desplazan TODAS las columnas de precio (open, high, low y close, de bid
    y de ask, y las de precio medio si vinieran) multiplicando por
    exp(deriva). El orden entre columnas se conserva.
  - Cada barra usa la deriva de su APERTURA para `open` y la de su CIERRE para
    `close`; el maximo usa la mayor de las dos y el minimo la menor. Con eso la
    barra sigue siendo coherente y cada apertura empalma con el cierre de la
    barra anterior, igual que en el mercado original.
  - La barra que cierra en t, la del propio evento, no se toca: el efecto
    empieza despues del evento, nunca antes.

Los eventos se detectan en el mercado LIMPIO y la deriva se suma a ese mercado.
Despues el pipeline completo se corre sobre el mercado inyectado, como pasaria
con un efecto real: la deriva mueve precios que entran en sigma_ref y en los
extremos de las franjas siguientes, y puede crear o borrar eventos. Cuanto pesa
eso se mide en el control positivo (delta realizado, sigma_ref y cantidad de
eventos contra el mercado limpio). Si en una franja hay sostenida y reingreso,
sus derivas se suman.
"""
import numpy as np

from motor import tiempo

LADOS = ("open", "high", "low", "close")


def signos(cfg):
    """+1 para los tipos que la familia principal prueba "mayor", -1 para "menor"."""
    return {tipo: (1.0 if cola == "mayor" else -1.0)
            for tipo, _, _, cola in cfg.FAMILIA_PRINCIPAL}


def inyectables(eventos, cfg):
    """
    Los eventos que reciben efecto, con lo que hace falta para la deriva:
    instante, amplitud por unidad de delta (direccion * signo * sigma_ref) y
    minutos hasta el fin de su franja.

    Queda fuera un evento sin sigma_ref o sin minutos de franja por delante:
    su retorno tampoco se puede medir.
    """
    signo = signos(cfg)
    tipo = eventos["tipo"].to_numpy()
    sigma = eventos["sigma_ref"].to_numpy(float)
    minutos = eventos["h_fin_franja"].to_numpy(float)
    sirve = (np.isin(tipo, list(signo)) & np.isfinite(sigma) & (sigma > 0)
             & np.isfinite(minutos) & (minutos > 0))
    s = np.array([signo.get(t, 0.0) for t in tipo[sirve]])
    return {
        "t_ns": eventos["t_evento_ns"].to_numpy(np.int64)[sirve],
        "amplitud": eventos["direccion"].to_numpy(float)[sirve] * s * sigma[sirve],
        "minutos": np.round(minutos[sirve]).astype(np.int64),
    }


def deriva(instantes_ns, efectos, delta):
    """
    La deriva acumulada, en logaritmo del precio, en cada instante pedido.

    `instantes_ns` tiene que venir ordenado. `efectos` es la salida de
    `inyectables`. Cada evento aporta amplitud * delta * raiz(tau) mientras
    tau (minutos desde el evento) este dentro de su franja, y el valor final
    de ahi en adelante.
    """
    x = np.asarray(instantes_ns, dtype=np.int64)
    salida = np.zeros(len(x))
    escalon = np.zeros(len(x) + 1)
    for t_e, amplitud, minutos in zip(efectos["t_ns"], efectos["amplitud"],
                                      efectos["minutos"]):
        a = amplitud * delta
        fin = t_e + int(minutos) * tiempo.NS_MIN
        desde = np.searchsorted(x, t_e, side="right")       # tau > 0
        hasta = np.searchsorted(x, fin, side="right")       # tau <= minutos
        salida[desde:hasta] += a * np.sqrt((x[desde:hasta] - t_e) / tiempo.NS_MIN)
        escalon[hasta] += a * np.sqrt(minutos)
    return salida + np.cumsum(escalon)[:-1]


def inyectar(datos, eventos, delta, cfg):
    """
    Devuelve una copia de `datos` con el efecto inyectado.

    `eventos` es la tabla del motor sobre el mercado LIMPIO (con
    `h_fin_franja` ya calculado por `agregar_retornos`). Con delta = 0 se
    devuelve una copia sin cambios.
    """
    salida = datos.copy()
    if delta == 0:
        return salida
    efectos = inyectables(eventos, cfg)
    apertura_ns = tiempo.a_ns(datos.index)
    en_apertura = deriva(apertura_ns, efectos, delta)
    en_cierre = deriva(tiempo.cierre_ns(apertura_ns), efectos, delta)
    factor = {
        "open": np.exp(en_apertura),
        "close": np.exp(en_cierre),
        "high": np.exp(np.maximum(en_apertura, en_cierre)),
        "low": np.exp(np.minimum(en_apertura, en_cierre)),
    }
    for columna in datos.columns:
        lado = columna.rsplit("_", 1)[-1]
        if lado in LADOS:
            salida[columna] = datos[columna].to_numpy(float) * factor[lado]
    return salida
