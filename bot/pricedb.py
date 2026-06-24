"""Base de datos propia de precios (SQLite).

Sirve para dos cosas:
1. Recordar el precio "anterior" de un producto que ya habias publicado.
2. Decir si el precio actual es el minimo historico que hemos registrado.

Al principio esta vacia, asi que tardara semanas/meses en tener historico
propio fiable. Mientras tanto, el grafico de Keepa muestra el pasado real.
"""
import sqlite3
import time
import logging
from dataclasses import dataclass

from . import config

log = logging.getLogger(__name__)


@dataclass
class PriceInfo:
    is_all_time_min: bool      # es el minimo de todo lo registrado
    is_window_min: bool        # es el minimo dentro de la ventana configurada
    previous_price: float | None  # ultimo precio distinto registrado antes de ahora
    min_price: float | None    # minimo registrado (en la ventana)
    samples: int               # cuantas mediciones tenemos de este producto


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            asin    TEXT NOT NULL,
            price   REAL NOT NULL,
            ts      INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_asin_ts ON price_history(asin, ts)"
    )
    return conn


def record_price(asin: str, price: float) -> None:
    """Guarda una medicion de precio."""
    if price is None:
        return
    with _connect() as conn:
        conn.execute(
            "INSERT INTO price_history (asin, price, ts) VALUES (?, ?, ?)",
            (asin, price, int(time.time())),
        )


def tracked_asins() -> list[str]:
    """ASINs que ya hemos registrado alguna vez (para refrescar precios)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT asin FROM price_history"
        ).fetchall()
    return [r[0] for r in rows]


def analyze(asin: str, current_price: float | None) -> PriceInfo:
    """Compara el precio actual con el historico registrado.

    Importante: se llama ANTES de insertar el precio actual, para que
    'previous_price' y 'min_price' reflejen lo que sabiamos hasta ahora.
    """
    window_cutoff = 0
    if config.MIN_WINDOW_DAYS > 0:
        window_cutoff = int(time.time()) - config.MIN_WINDOW_DAYS * 86400

    with _connect() as conn:
        # Minimo en la ventana.
        row = conn.execute(
            "SELECT MIN(price), COUNT(*) FROM price_history "
            "WHERE asin = ? AND ts >= ?",
            (asin, window_cutoff),
        ).fetchone()
        min_price = row[0]
        samples = row[1]

        # Ultimo precio registrado (el "antes").
        prev_row = conn.execute(
            "SELECT price FROM price_history WHERE asin = ? "
            "ORDER BY ts DESC LIMIT 1",
            (asin,),
        ).fetchone()
        previous_price = prev_row[0] if prev_row else None

    is_window_min = False
    is_all_time_min = False
    if current_price is not None and min_price is not None:
        is_window_min = current_price <= min_price
        # Para el "todo el historico" repetimos sin ventana.
        if config.MIN_WINDOW_DAYS > 0:
            with _connect() as conn:
                all_min = conn.execute(
                    "SELECT MIN(price) FROM price_history WHERE asin = ?",
                    (asin,),
                ).fetchone()[0]
            is_all_time_min = all_min is not None and current_price <= all_min
        else:
            is_all_time_min = is_window_min

    return PriceInfo(
        is_all_time_min=is_all_time_min,
        is_window_min=is_window_min,
        previous_price=previous_price,
        min_price=min_price,
        samples=samples,
    )
