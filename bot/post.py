"""Construccion del texto (caption) del post con plantilla y emojis."""
import html

from .amazon import Product
from .pricedb import PriceInfo
from . import config

# Limite de caracteres de un caption en Telegram.
CAPTION_LIMIT = 1024


def _fmt_price(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def build_caption(product: Product, info: PriceInfo) -> str:
    """Devuelve el caption en HTML (parse_mode=HTML)."""
    lines: list[str] = []

    title = product.title or "Oferta de Amazon"
    lines.append(f"🔥 <b>{html.escape(title)}</b>")
    lines.append("")

    # Precio "antes": prioriza nuestro historico; si no, el PVP scrapeado.
    before = product.list_price
    if info.previous_price and (before is None or info.previous_price > (product.price or 0)):
        before = info.previous_price

    now = product.price
    now_s = _fmt_price(now)
    before_s = _fmt_price(before)

    if now_s and before_s and before and now and before > now:
        discount = round((1 - now / before) * 100)
        saving = _fmt_price(before - now)
        lines.append(f"💰 <b>{now_s}</b>  <s>{before_s}</s>  (-{discount}%)")
        if saving:
            lines.append(f"🤑 Ahorras {saving}")
    elif now_s:
        lines.append(f"💰 <b>{now_s}</b>")
    lines.append("")

    # Badge de minimo historico (solo si tenemos datos suficientes).
    if info.is_all_time_min and info.samples >= 2:
        lines.append("🏆 <b>¡Precio MÍNIMO histórico!</b>")
    elif info.is_window_min and info.samples >= 2 and config.MIN_WINDOW_DAYS > 0:
        lines.append(f"📉 <b>Precio mínimo de los últimos {config.MIN_WINDOW_DAYS} días</b>")
    elif now_s and before_s and before and now and before > now:
        lines.append("📉 <b>¡Buen precio!</b>")

    lines.append("")
    lines.append(f'👉 <a href="{html.escape(product.affiliate_url, quote=True)}">Comprar en Amazon</a>')

    caption = "\n".join(lines)
    if len(caption) > CAPTION_LIMIT:
        caption = caption[: CAPTION_LIMIT - 1] + "…"
    return caption
