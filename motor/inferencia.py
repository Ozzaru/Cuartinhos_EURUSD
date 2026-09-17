# -*- coding: utf-8 -*-
"""
INFERENCIA — regresiones con moderadores y correccion por pruebas multiples.

Dos familias de pruebas, definidas en config.py:

  FAMILIA_PRINCIPAL     H1 y H2. El estadistico es el promedio del retorno
                        normalizado, sin controles: el emparejamiento de la
                        nula ya se encarga de la composicion de la muestra.
  FAMILIA_MODERADORES   H3 y H4. El estadistico es el coeficiente de cada
                        moderador en una regresion con efectos fijos de indice
                        de franja, dia de semana y ano.

Errores estandar agrupados por FECHA DE LONDRES: dos eventos del mismo dia
comparten shocks, y tratarlos como independientes inflaria la significancia.
Newey-West queda disponible como alternativa de robustez.

Sobre las dos correcciones:

  Holm es la principal. Vale con cualquier estructura de dependencia, asi que
  el solapamiento entre sostenida y reingreso (comparten la misma ruptura) no
  lo invalida. Se aplica a los p-valores BRUTOS de cada familia, sean de la
  nula emparejada (familia principal) o de la regresion (moderadores).

  Romano-Wolf es la secundaria. Gana potencia porque aprende la dependencia
  entre pruebas desde los datos, pero para eso necesita un estadistico comun y
  su propio remuestreo: trabaja siempre sobre los estadisticos t de la
  regresion, remuestreando DIAS con reemplazo. No usa los p-valores de la nula.
  Esa diferencia esta declarada a proposito y va al pre-registro.
"""
import numpy as np
import pandas as pd
from scipy import stats


# =============================================================================
#  Minimos cuadrados con errores agrupados
# =============================================================================
def ols_agrupado(y, X, inicio_grupo):
    """
    Minimos cuadrados con errores estandar agrupados (cluster).

    `inicio_grupo` son las posiciones donde empieza cada grupo; las filas tienen
    que venir ORDENADAS por grupo. Se calcula a mano y no con statsmodels porque
    el bootstrap de Romano-Wolf repite este ajuste decenas de miles de veces.
    La equivalencia con statsmodels esta comprobada en los tests.

    Correccion de muestra finita, la misma que usa Stata:
        G / (G - 1) * (n - 1) / (n - k)
    """
    n, k = X.shape
    G = len(inicio_grupo)
    if n <= k or G < 2:
        return np.full(k, np.nan), np.full(k, np.nan), G

    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ (X.T @ y)
    residuo = y - X @ beta

    # "Carne" del sandwich: la suma, por grupo, de X' e.
    por_grupo = np.add.reduceat(X * residuo[:, None], inicio_grupo, axis=0)
    carne = por_grupo.T @ por_grupo
    varianza = xtx_inv @ carne @ xtx_inv
    varianza *= (G / (G - 1)) * ((n - 1) / (n - k))
    error = np.sqrt(np.maximum(np.diag(varianza), 0.0))
    return beta, error, G


def _p_de_t(t, gl, cola="dos"):
    """
    p-valor de un estadistico t, con la cola que pide la hipotesis.

    "mayor" para H1 (se espera continuacion), "menor" para H2 (se espera
    reversion) y "dos" cuando el signo no se pre-especifica.
    """
    if not np.isfinite(t):
        return np.nan
    gl = max(int(gl), 1)
    if cola == "mayor":
        return float(stats.t.sf(t, df=gl))
    if cola == "menor":
        return float(stats.t.cdf(t, df=gl))
    return float(2.0 * stats.t.sf(abs(t), df=gl))


# =============================================================================
#  Construccion de las celdas (una por tipo x horizonte x modelo)
# =============================================================================
class Celda:
    """
    Los datos ya preparados para una prueba: y, X, los nombres de las columnas
    y el mapa de que filas aporta cada dia.

    Se arma una sola vez y se reutiliza en todas las repeticiones del bootstrap.
    Las filas vienen ordenadas por dia, que es lo que necesita `ols_agrupado`.
    """

    def __init__(self, tipo, horizonte, modelo, y, X, nombres, dia):
        orden = np.argsort(dia, kind="stable")
        self.tipo, self.horizonte, self.modelo = tipo, horizonte, modelo
        self.y, self.X, self.nombres = y[orden], X[orden], nombres
        self.dia = dia[orden]
        self.inicio_grupo = np.flatnonzero(np.concatenate([[True], np.diff(self.dia) != 0]))
        # Para el bootstrap: que filas aporta cada dia, como tramos contiguos.
        self.dias_presentes = self.dia[self.inicio_grupo]
        fin = np.append(self.inicio_grupo[1:], len(self.dia))
        self.tramo = dict(zip(self.dias_presentes, zip(self.inicio_grupo, fin)))

    def estimar(self):
        return ols_agrupado(self.y, self.X, self.inicio_grupo)

    def estimar_remuestreado(self, dias_muestra):
        """
        Reajusta el modelo sobre una muestra de dias con reemplazo.

        Cada dia sorteado es un grupo nuevo, aunque sea el mismo dia repetido:
        de eso se trata el bootstrap por bloques.
        """
        tramos = [self.tramo[d] for d in dias_muestra if d in self.tramo]
        if len(tramos) < 2:
            return np.full(self.X.shape[1], np.nan), np.full(self.X.shape[1], np.nan), 0

        inicios = np.array([a for a, _ in tramos])
        largos = np.array([b - a for a, b in tramos])
        total = int(largos.sum())
        desplazamiento = np.repeat(inicios - np.concatenate([[0], np.cumsum(largos)[:-1]]), largos)
        filas = desplazamiento + np.arange(total)
        inicio_grupo = np.concatenate([[0], np.cumsum(largos)[:-1]])
        return ols_agrupado(self.y[filas], self.X[filas], inicio_grupo)


def _dummies(valores, prefijo):
    """Variables indicadoras dejando fuera la primera categoria."""
    niveles = np.unique(valores)
    if len(niveles) < 2:
        return np.zeros((len(valores), 0)), []
    columnas = np.column_stack([(valores == nivel).astype(float) for nivel in niveles[1:]])
    return columnas, [f"{prefijo}_{nivel}" for nivel in niveles[1:]]


def construir_celdas(eventos, cfg, dias_codigo=None):
    """
    Arma todas las celdas que las dos familias pueden necesitar.

    Devuelve (celdas, dias) donde `celdas` se indexa por (tipo, horizonte,
    modelo) y `dias` es la lista de codigos de dia de toda la muestra, que el
    bootstrap remuestrea igual para todas las celdas a la vez.
    """
    eventos = eventos.reset_index(drop=True)
    if dias_codigo is None:
        dias_codigo = pd.factorize(pd.DatetimeIndex(eventos["fecha_londres"]))[0]
    dias_codigo = np.asarray(dias_codigo)

    moderadores = np.column_stack(
        [eventos[nombre].to_numpy(float) for nombre in cfg.MODERADORES])
    anio_todos = pd.DatetimeIndex(eventos["fecha_londres"]).year.to_numpy()

    celdas = {}
    for tipo in cfg.TIPOS_EVENTO:
        del_tipo = eventos["tipo"].to_numpy() == tipo
        for h in cfg.HORIZONTES:
            ret = eventos[f"ret_{h}"].to_numpy(float)
            base = del_tipo & np.isfinite(ret)
            if base.sum() < 3:
                continue

            # Modelo 1: solo la constante. El coeficiente ES el promedio.
            filas = np.flatnonzero(base)
            celdas[(tipo, h, "media")] = Celda(
                tipo, h, "media", ret[filas], np.ones((len(filas), 1)),
                ["media"], dias_codigo[filas])

            # Modelo 2: moderadores mas efectos fijos.
            completo = base & np.all(np.isfinite(moderadores), axis=1)
            if completo.sum() < 3:
                continue
            filas = np.flatnonzero(completo)
            bloques = [np.ones((len(filas), 1)), moderadores[filas]]
            nombres = ["const"] + list(cfg.MODERADORES)
            for valores, prefijo in [(eventos["idx_franja"].to_numpy()[filas], "franja"),
                                     (eventos["dia_semana"].to_numpy()[filas], "dia"),
                                     (anio_todos[filas], "anio")]:
                columnas, etiquetas = _dummies(valores, prefijo)
                if columnas.shape[1]:
                    bloques.append(columnas)
                    nombres += etiquetas
            X = np.column_stack(bloques)
            X, nombres = _quitar_columnas_constantes(X, nombres)
            celdas[(tipo, h, "moderadores")] = Celda(
                tipo, h, "moderadores", ret[filas], X, nombres, dias_codigo[filas])
    return celdas, np.unique(dias_codigo)


def _quitar_columnas_constantes(X, nombres):
    """
    Saca los moderadores que no varian en esa celda.

    Pasa, por ejemplo, cuando ningun evento de un tipo cayo cerca de una
    noticia. Con la columna adentro la regresion queda indeterminada; sin ella,
    la prueba de ese coeficiente simplemente no existe y se informa como tal.
    """
    quedan, etiquetas = [], []
    for j, nombre in enumerate(nombres):
        if nombre == "const" or X[:, j].std() > 0:
            quedan.append(j)
            etiquetas.append(nombre)
    return X[:, quedan], etiquetas


# =============================================================================
#  Tabla de estadisticos de una familia
# =============================================================================
def estadisticos(celdas, familia):
    """
    Estimacion, error estandar, t y p-valor bruto de cada prueba de la familia.

    Una prueba cuyo coeficiente no existe en su celda (por ejemplo, un
    moderador que no varia) se informa con NaN y despues cuenta como no
    rechazada.
    """
    filas = []
    for tipo, h, coeficiente, cola in familia:
        modelo = "media" if coeficiente == "media" else "moderadores"
        celda = celdas.get((tipo, h, modelo))
        fila = {"tipo": tipo, "horizonte": h, "coeficiente": coeficiente, "cola": cola,
                "n": 0, "estimacion": np.nan, "error": np.nan, "t": np.nan,
                "p_bruto": np.nan}
        if celda is not None and coeficiente in celda.nombres:
            beta, error, grupos = celda.estimar()
            j = celda.nombres.index(coeficiente)
            t = beta[j] / error[j] if error[j] > 0 else np.nan
            fila.update(n=len(celda.y), estimacion=beta[j], error=error[j], t=t,
                        p_bruto=_p_de_t(t, grupos - 1, cola))
        filas.append(fila)
    return pd.DataFrame(filas)


# =============================================================================
#  Correccion por pruebas multiples
# =============================================================================
def holm(p_valores):
    """
    Correccion de Holm (1979), escrita paso a paso.

    Se ordenan los p-valores de menor a mayor. Al mas chico se le exige el
    umbral mas duro (multiplicar por m), al siguiente por m-1, y asi. Despues se
    impone que la lista corregida no baje, porque un p-valor corregido no puede
    ser menor que el de una prueba mas significativa.

    Vale con cualquier dependencia entre las pruebas, que es justo lo que hace
    falta aqui: sostenida y reingreso comparten la misma ruptura.

    Los NaN (pruebas que no se pudieron correr) salen como NaN y no gastan
    lugar en la familia.
    """
    p = np.asarray(p_valores, dtype=float)
    salida = np.full(len(p), np.nan)
    hay = np.flatnonzero(np.isfinite(p))
    if len(hay) == 0:
        return salida

    m = len(hay)
    orden = hay[np.argsort(p[hay], kind="stable")]
    acumulado = 0.0
    for paso, indice in enumerate(orden):
        ajustado = (m - paso) * p[indice]
        acumulado = max(acumulado, min(ajustado, 1.0))
        salida[indice] = acumulado
    return salida


def romano_wolf(celdas, familia, dias, repeticiones, semilla):
    """
    Romano y Wolf (2005), stepdown con el maximo del estadistico t.

    La idea en simple: en vez de castigar cada prueba como si las demas fueran
    independientes, se aprende de los datos cuanto se parecen entre si. Si las
    pruebas estan muy correlacionadas, el maximo de un grupo de estadisticos no
    es mucho mayor que uno solo, y el castigo resulta menor que el de Holm.

    El algoritmo:
      1. Se calculan los t observados de todas las pruebas de la familia.
      2. B veces se remuestrean DIAS con reemplazo (el mismo sorteo de dias para
         TODAS las pruebas a la vez, para conservar la dependencia entre ellas)
         y se recalculan todos los estadisticos. Cada uno se centra en su valor
         observado, que es la forma de imponer la hipotesis nula:
             w = (estimacion_remuestreada - estimacion_observada) / error_remuestreado
      3. Se ordenan las pruebas de mayor a menor |t| observado. Para la primera,
         el p-valor es la proporcion de remuestreos en que el MAXIMO de |w|
         sobre toda la familia supera su |t|. Se saca esa prueba del conjunto y
         se repite con el maximo sobre las que quedan (eso es el "stepdown").
      4. Se impone que los p-valores no bajen al avanzar.

    Devuelve un array de p-valores alineado con `familia`.
    """
    claves = []
    for tipo, h, coeficiente, _ in familia:
        modelo = "media" if coeficiente == "media" else "moderadores"
        celda = celdas.get((tipo, h, modelo))
        claves.append((celda, coeficiente))

    m = len(familia)
    t_obs = np.full(m, np.nan)
    beta_obs = np.full(m, np.nan)
    for i, (celda, coeficiente) in enumerate(claves):
        if celda is None or coeficiente not in celda.nombres:
            continue
        beta, error, grupos = celda.estimar()
        j = celda.nombres.index(coeficiente)
        beta_obs[i] = beta[j]
        if error[j] > 0:
            t_obs[i] = beta[j] / error[j]

    vivos = np.flatnonzero(np.isfinite(t_obs))
    salida = np.full(m, np.nan)
    if len(vivos) == 0:
        return salida

    rng = np.random.default_rng(semilla)
    w = np.full((repeticiones, m), np.nan)
    for b in range(repeticiones):
        muestra = rng.choice(dias, size=len(dias), replace=True)
        cache = {}
        for i in vivos:
            celda, coeficiente = claves[i]
            llave = (celda.tipo, celda.horizonte, celda.modelo)
            if llave not in cache:
                cache[llave] = celda.estimar_remuestreado(muestra)
            beta, error, _ = cache[llave]
            j = celda.nombres.index(coeficiente)
            if np.isfinite(error[j]) and error[j] > 0:
                w[b, i] = (beta[j] - beta_obs[i]) / error[j]

    absoluto = np.abs(w)
    orden = vivos[np.argsort(-np.abs(t_obs[vivos]), kind="stable")]
    restantes = list(orden)
    acumulado = 0.0
    for indice in orden:
        columnas = np.array(restantes)
        # Un remuestreo puede dejar sin definir el estadistico de alguna prueba
        # (por ejemplo, si el grupo tratado desaparecio de la muestra de dias).
        # Esas casillas no aportan al maximo y el remuestreo entero se descarta
        # solo si ninguna prueba quedo definida.
        bloque = absoluto[:, columnas]
        maximo = np.where(np.isfinite(bloque), bloque, -np.inf).max(axis=1)
        validos = np.isfinite(maximo)
        if not validos.any():
            salida[indice] = np.nan
            restantes.remove(indice)
            continue
        extremas = np.sum(maximo[validos] >= abs(t_obs[indice]))
        p = (1 + extremas) / (1 + validos.sum())
        acumulado = max(acumulado, min(float(p), 1.0))
        salida[indice] = acumulado
        restantes.remove(indice)
    return salida


# =============================================================================
#  Entrada principal
# =============================================================================
def analizar(eventos, cfg, familia, semilla, p_brutos=None, con_romano_wolf=False,
             celdas=None, dias=None, repeticiones_rw=None):
    """
    Tabla final de una familia: estadistico, p bruto, p corregido y decision.

    `p_brutos` permite reemplazar los p-valores de la regresion por otros ya
    calculados. Asi la familia principal se corrige sobre los p-valores de la
    nula emparejada, que es la prueba que se va a pre-registrar, y no sobre el
    t de una regresion.
    """
    if celdas is None:
        celdas, dias = construir_celdas(eventos, cfg)
    if con_romano_wolf and dias is None:
        raise ValueError("Romano-Wolf necesita la lista de dias de la muestra")
    tabla = estadisticos(celdas, familia)

    if p_brutos is not None:
        llaves = list(zip(tabla["tipo"], tabla["horizonte"], tabla["coeficiente"]))
        tabla["p_bruto"] = [p_brutos.get(llave, np.nan) for llave in llaves]

    tabla["p_holm"] = holm(tabla["p_bruto"].to_numpy(float))
    if con_romano_wolf:
        repeticiones = cfg.RW_REPETICIONES if repeticiones_rw is None else repeticiones_rw
        tabla["p_romano_wolf"] = romano_wolf(celdas, familia, dias, repeticiones, semilla)
    else:
        tabla["p_romano_wolf"] = np.nan

    principal = "p_holm" if cfg.CORRECCION_PRINCIPAL == "holm" else "p_romano_wolf"
    tabla["p_corregido"] = tabla[principal]
    tabla["rechaza"] = tabla["p_corregido"].to_numpy(float) <= cfg.ALFA
    return tabla


def con_newey_west(celda, coeficiente, rezagos):
    """
    Alternativa de robustez: errores de Newey-West (HAC) en vez de agrupados.

    Se apoya en statsmodels, que ya trae la implementacion estandar. No se usa
    en el bootstrap de Romano-Wolf por costo: es solo para contrastar la tabla
    principal.
    """
    import statsmodels.api as sm

    if coeficiente not in celda.nombres:
        return np.nan, np.nan, np.nan
    ajuste = sm.OLS(celda.y, celda.X).fit(cov_type="HAC",
                                          cov_kwds={"maxlags": rezagos, "use_correction": True})
    j = celda.nombres.index(coeficiente)
    return float(ajuste.params[j]), float(ajuste.bse[j]), float(ajuste.tvalues[j])


def p_brutos_desde_nula(tabla_nula, cfg):
    """
    Traduce la salida de nula.py al diccionario que espera `analizar` para la
    familia principal: se usa el p-valor de la cola que pide cada hipotesis.
    """
    salida = {}
    for _, fila in tabla_nula.iterrows():
        if fila["cola"] in ("mayor", "menor"):
            salida[(fila["tipo"], fila["horizonte"], "media")] = fila["p_una_cola"]
    return salida
