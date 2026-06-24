"""Configuracion del bot, leida desde variables de entorno.

En UGOS Pro las variables se ponen en la pantalla del contenedor (Environment),
asi no hace falta tocar ficheros ni terminal.
"""
import os


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "si", "sí", "y")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except (ValueError, TypeError):
        return default


# --- Telegram ---
# Token del bot (BotFather). Obligatorio.
BOT_TOKEN = _get("BOT_TOKEN")

# Chat privado donde pegas los enlaces. Si se deja vacio, el bot procesa
# enlaces en cualquier chat donde este. Para un grupo: el id suele ser
# negativo (ej. -1001234567890).
STAGING_CHAT_ID = _get("STAGING_CHAT_ID")

# Canal donde se publican las ofertas. Puede ser @nombredecanal o el id -100...
# El bot debe ser administrador del canal.
CHANNEL_ID = _get("CHANNEL_ID")

# Si es true, publica directo en el canal sin pedir confirmacion.
# Si es false (recomendado al empezar), manda una vista previa con botones.
AUTO_PUBLISH = _get_bool("AUTO_PUBLISH", False)

# --- Afiliacion Amazon ---
AFFILIATE_TAG = _get("AFFILIATE_TAG", "jack051-21")
AMAZON_DOMAIN = _get("AMAZON_DOMAIN", "amazon.es")

# --- Keepa (grafico gratuito) ---
# Codigo de pais para el grafico de Keepa: es, com, de, fr, it, co.uk...
KEEPA_DOMAIN = _get("KEEPA_DOMAIN", "es")
SHOW_KEEPA_GRAPH = _get_bool("SHOW_KEEPA_GRAPH", True)

# --- Base de datos de precios ---
DB_PATH = _get("DB_PATH", "/app/data/prices.db")

# Ventana en dias para el calculo del minimo. 0 = todo el historico registrado.
MIN_WINDOW_DAYS = _get_int("MIN_WINDOW_DAYS", 0)

# Cada cuantas horas se refrescan los precios de los productos ya publicados,
# para que la base de datos crezca aunque no publiques nada nuevo.
REFRESH_EVERY_HOURS = _get_int("REFRESH_EVERY_HOURS", 24)


def validate() -> list[str]:
    """Devuelve una lista de errores de configuracion (vacia si todo ok)."""
    errors = []
    if not BOT_TOKEN:
        errors.append("Falta BOT_TOKEN (token del bot de BotFather).")
    if not CHANNEL_ID:
        errors.append("Falta CHANNEL_ID (canal donde publicar).")
    if not AFFILIATE_TAG:
        errors.append("Falta AFFILIATE_TAG (tu tag de afiliado).")
    return errors
