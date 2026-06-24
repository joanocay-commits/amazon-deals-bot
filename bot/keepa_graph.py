"""Grafico de historico de precios de Keepa (gratuito, sin API).

Keepa expone publicamente el grafico de precios como imagen PNG. No hace falta
clave ni pagar. Solo construimos la URL con el ASIN y descargamos la imagen.
"""
import logging

import requests

from . import config
from .amazon import HEADERS

log = logging.getLogger(__name__)

# Keepa rechaza peticiones sin cabeceras de navegador (responde 403).
KEEPA_HEADERS = dict(HEADERS)
KEEPA_HEADERS["Referer"] = "https://keepa.com/"

BASE = "https://graph.keepa.com/pricehistory.png"


def graph_url(asin: str) -> str:
    params = (
        f"?asin={asin}"
        f"&domain={config.KEEPA_DOMAIN}"
        "&amazon=1"   # precio de Amazon
        "&new=1"      # precio nuevo de terceros
        "&salesrank=0"
        "&width=600"
        "&height=240"
        "&range=365"  # ultimo ano
    )
    return BASE + params


def download(asin: str) -> bytes | None:
    """Descarga la imagen del grafico. Devuelve None si falla."""
    if not config.SHOW_KEEPA_GRAPH:
        return None
    url = graph_url(asin)
    try:
        resp = requests.get(url, headers=KEEPA_HEADERS, timeout=20)
        resp.raise_for_status()
        if "image" not in resp.headers.get("Content-Type", ""):
            log.warning("Keepa no devolvio una imagen para %s", asin)
            return None
        return resp.content
    except requests.RequestException as e:
        log.warning("No se pudo descargar el grafico de Keepa para %s: %s", asin, e)
        return None
