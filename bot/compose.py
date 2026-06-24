"""Composicion de la imagen final del post.

Junta la foto del producto y el grafico de Keepa en una sola imagen vertical,
sobre fondo blanco, lista para enviar a Telegram.
"""
import io
import logging

import requests
from PIL import Image

from .amazon import HEADERS

log = logging.getLogger(__name__)

CANVAS_WIDTH = 600
MARGIN = 20
GAP = 16
BG = (255, 255, 255)


def _download_image(url: str | None) -> Image.Image | None:
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        return img.convert("RGB")
    except (requests.RequestException, OSError) as e:
        log.warning("No se pudo abrir la imagen %s: %s", url, e)
        return None


def _fit_width(img: Image.Image, width: int) -> Image.Image:
    """Escala una imagen para que ocupe el ancho dado, manteniendo proporcion."""
    if img.width == width:
        return img
    ratio = width / img.width
    new_height = max(1, int(img.height * ratio))
    return img.resize((width, new_height), Image.LANCZOS)


def build_post_image(product_image_url: str | None, graph_bytes: bytes | None) -> bytes | None:
    """Devuelve los bytes JPEG de la imagen compuesta, o None si no hay nada.

    - Si hay foto y grafico: los apila (foto arriba, grafico abajo).
    - Si solo hay uno de los dos: devuelve ese.
    """
    inner_width = CANVAS_WIDTH - 2 * MARGIN

    product_img = _download_image(product_image_url)
    if product_img:
        product_img = _fit_width(product_img, inner_width)
        # Limita la altura del producto para que no domine.
        max_h = 420
        if product_img.height > max_h:
            crop_top = (product_img.height - max_h) // 2
            product_img = product_img.crop(
                (0, crop_top, product_img.width, crop_top + max_h)
            )

    graph_img = None
    if graph_bytes:
        try:
            graph_img = Image.open(io.BytesIO(graph_bytes)).convert("RGB")
            graph_img = _fit_width(graph_img, inner_width)
        except OSError as e:
            log.warning("No se pudo abrir el grafico de Keepa: %s", e)

    parts = [p for p in (product_img, graph_img) if p is not None]
    if not parts:
        return None
    if len(parts) == 1:
        return _to_jpeg(parts[0])

    total_height = MARGIN * 2 + sum(p.height for p in parts) + GAP * (len(parts) - 1)
    canvas = Image.new("RGB", (CANVAS_WIDTH, total_height), BG)
    y = MARGIN
    for p in parts:
        canvas.paste(p, (MARGIN, y))
        y += p.height + GAP

    return _to_jpeg(canvas)


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()
