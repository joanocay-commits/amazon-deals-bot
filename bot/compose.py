"""Preparacion de las imagenes del post.

El producto y el grafico de Keepa van como imagenes SEPARADAS (un album en
Telegram). Aqui solo descargamos y normalizamos la foto del producto a JPEG.
El grafico de Keepa ya viene como imagen desde keepa_graph.py.
"""
import io
import logging

import requests
from PIL import Image

from .amazon import HEADERS

log = logging.getLogger(__name__)

MAX_SIDE = 1000  # lado maximo de la foto del producto


def _download_image(url: str | None) -> Image.Image | None:
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except (requests.RequestException, OSError) as e:
        log.warning("No se pudo abrir la imagen %s: %s", url, e)
        return None


def _fit_box(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Escala la imagen entera para que quepa en max_w x max_h, sin recortar."""
    ratio = min(max_w / img.width, max_h / img.height)
    if ratio >= 1:
        return img
    return img.resize(
        (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
        Image.LANCZOS,
    )


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def product_jpeg(image_url: str | None) -> bytes | None:
    """Devuelve la foto del producto como JPEG, o None si no se pudo."""
    img = _download_image(image_url)
    if img is None:
        return None
    img = _fit_box(img, MAX_SIDE, MAX_SIDE)
    return _to_jpeg(img)
