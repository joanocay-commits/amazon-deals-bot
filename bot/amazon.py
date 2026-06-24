"""Extraccion de datos de un producto de Amazon.

- Detecta el ASIN de cualquier formato de enlace (incluidos los cortos amzn.to).
- Construye el enlace de afiliado limpio.
- Hace scraping de titulo, precio e imagen de la pagina del producto.

El scraping de Amazon es fragil por naturaleza: Amazon a veces responde con
una pagina de robot/CAPTCHA. Por eso cada dato puede venir vacio y el bot
sabe seguir funcionando con lo que tenga (como minimo el enlace y el grafico
de Keepa siempre funcionan).
"""
import re
import json
import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from . import config

log = logging.getLogger(__name__)

# Cabeceras que imitan a un navegador real para reducir bloqueos.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Cualquier enlace de Amazon (largo o corto) dentro de un texto.
AMAZON_URL_RE = re.compile(
    r"https?://[^\s]*?(?:amazon\.[a-z.]+|amzn\.(?:to|eu))/[^\s]+",
    re.IGNORECASE,
)

# Patrones para sacar el ASIN de la URL.
ASIN_PATTERNS = [
    re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"/gp/product/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"/gp/aw/d/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"/product/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"/d/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"[?&]asin=([A-Z0-9]{10})", re.IGNORECASE),
]


@dataclass
class Product:
    asin: str
    affiliate_url: str
    title: str | None = None
    price: float | None = None      # precio actual scrapeado
    list_price: float | None = None  # precio "antes" / tachado, si aparece
    image_url: str | None = None


def find_amazon_url(text: str) -> str | None:
    """Devuelve el primer enlace de Amazon que aparezca en el texto."""
    if not text:
        return None
    m = AMAZON_URL_RE.search(text)
    return m.group(0) if m else None


def resolve_url(url: str) -> str:
    """Sigue las redirecciones (necesario para enlaces cortos amzn.to)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        return resp.url
    except requests.RequestException as e:
        log.warning("No se pudo resolver el enlace corto %s: %s", url, e)
        return url


def extract_asin(url: str) -> str | None:
    for pat in ASIN_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1).upper()
    return None


def build_affiliate_url(asin: str) -> str:
    return f"https://www.{config.AMAZON_DOMAIN}/dp/{asin}?tag={config.AFFILIATE_TAG}"


def _parse_price(text: str | None) -> float | None:
    """Convierte '359,00 €' o '1.299,00' a float."""
    if not text:
        return None
    # Quita todo menos digitos, comas y puntos.
    cleaned = re.sub(r"[^\d.,]", "", text)
    if not cleaned:
        return None
    # Formato europeo: el punto es separador de miles y la coma de decimales.
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return None


def scrape(url: str, asin: str) -> Product:
    """Descarga la pagina del producto y extrae lo que pueda."""
    product = Product(asin=asin, affiliate_url=build_affiliate_url(asin))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("No se pudo descargar la pagina %s: %s", url, e)
        return product

    soup = BeautifulSoup(resp.text, "lxml")

    # --- Titulo ---
    product.title = _first_text(soup, ["#productTitle", "span#title"])
    if not product.title:
        og = soup.select_one('meta[property="og:title"]')
        if og:
            product.title = og.get("content")
    if product.title:
        product.title = product.title.strip()

    # --- Precio actual ---
    price_text = _first_text(
        soup,
        [
            "span.priceToPay span.a-offscreen",
            "span.apexPriceToPay span.a-offscreen",
            "#corePrice_feature_div span.a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price span.a-offscreen",
        ],
    )
    product.price = _parse_price(price_text)

    # --- Precio anterior / tachado (PVP) ---
    list_text = _first_text(
        soup,
        [
            "span.basisPrice span.a-offscreen",
            ".a-text-price span.a-offscreen",
            "#listPrice",
            "#priceblock_listprice",
        ],
    )
    product.list_price = _parse_price(list_text)

    # --- Imagen (varias fuentes, de mas fiable a menos) ---
    product.image_url = _extract_image(soup, resp.text)

    return product


def _extract_image(soup: BeautifulSoup, html: str) -> str | None:
    # 1. Imagen principal en alta resolucion.
    img = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
    if img:
        url = img.get("data-old-hires")
        if url:
            return url
        # 2. data-a-dynamic-image: JSON {url: [w,h], ...}. Cogemos la mayor.
        dyn = img.get("data-a-dynamic-image")
        if dyn:
            try:
                data = json.loads(dyn)
                if data:
                    best = max(data.items(), key=lambda kv: kv[1][0] * kv[1][1])
                    return best[0]
            except (json.JSONDecodeError, ValueError, IndexError, TypeError):
                pass
        if img.get("src", "").startswith("http"):
            return img.get("src")
    # 3. Blob de JavaScript con "hiRes":"https://..."
    m = re.search(r'"hiRes"\s*:\s*"(https://[^"]+?\.jpg)"', html)
    if m:
        return m.group(1)
    m = re.search(r'"large"\s*:\s*"(https://[^"]+?\.jpg)"', html)
    if m:
        return m.group(1)
    # 4. Ultimo recurso: og:image.
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img and og_img.get("content"):
        return og_img.get("content")
    return None


def process_link(raw_url: str) -> Product | None:
    """Pipeline completo: resolver -> ASIN -> scraping."""
    url = raw_url
    if "amzn." in raw_url.lower():
        url = resolve_url(raw_url)
    asin = extract_asin(url)
    if not asin:
        log.info("No se encontro ASIN en %s", url)
        return None
    return scrape(url, asin)
