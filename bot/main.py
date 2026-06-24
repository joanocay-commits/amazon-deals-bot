"""Punto de entrada del bot de chollos.

Flujo (modo asistido):
1. Pegas un enlace de Amazon en el chat privado / grupo donde esta el bot.
2. El bot extrae datos y prepara la foto del producto y el grafico de Keepa
   como imagenes separadas (album), mas el texto.
3. Te manda una VISTA PREVIA con botones "Publicar" / "Cancelar".
4. Al pulsar Publicar, lo envia al canal.

Si AUTO_PUBLISH=true, se salta la vista previa y publica directo.
"""
import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import amazon, compose, config, keepa_graph, post, pricedb

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
# Silencia el ruido de las librerias para que se vean nuestras lineas importantes.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
log = logging.getLogger("bot")

# Sube este numero en cada cambio. Sirve para comprobar en los logs que el NAS
# esta corriendo de verdad la version nueva (y no una imagen vieja en cache).
VERSION = "1.3"

# Posts pendientes de confirmar: token -> payload
PENDING: dict[str, dict] = {}


def _in_staging(update: Update) -> bool:
    """True si el mensaje viene del chat configurado (o si no hay filtro)."""
    if not config.STAGING_CHAT_ID:
        return True
    return str(update.effective_chat.id) == str(config.STAGING_CHAT_ID)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola 👋 Soy tu bot de chollos.\n\n"
        "Pega un enlace de Amazon y te montaré el post con imagen, "
        "precios y gráfico de histórico.\n\n"
        "Comandos:\n"
        "/id — muestra el id de este chat\n"
        "/ping — comprueba que estoy vivo"
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.message.reply_text(
        f"Id de este chat: <code>{chat.id}</code>\nTipo: {chat.type}",
        parse_mode="HTML",
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong ✅")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not _in_staging(update):
        return

    raw = amazon.find_amazon_url(update.message.text)
    if not raw:
        return  # no hay enlace de Amazon, ignoramos

    status = await update.message.reply_text("⏳ Procesando el chollo…")

    product = amazon.process_link(raw)
    if not product:
        await status.edit_text("❌ No pude reconocer el producto en ese enlace.")
        return

    # Analizamos ANTES de registrar el precio de hoy.
    info = pricedb.analyze(product.asin, product.price)
    if product.price is not None:
        pricedb.record_price(product.asin, product.price)

    # Producto y grafico como imagenes separadas.
    product_bytes = compose.product_jpeg(product.image_url)
    graph_bytes = keepa_graph.download(product.asin)
    caption = post.build_caption(product, info)
    payload = {"product": product_bytes, "graph": graph_bytes, "caption": caption}

    log.info(
        "ASIN=%s titulo=%s precio=%s | imagen_url=%s producto=%s bytes keepa=%s bytes",
        product.asin,
        bool(product.title),
        product.price,
        bool(product.image_url),
        len(product_bytes) if product_bytes else 0,
        len(graph_bytes) if graph_bytes else 0,
    )

    if config.AUTO_PUBLISH:
        await _send_post(context, config.CHANNEL_ID, payload)
        await status.edit_text("✅ Publicado en el canal.")
        return

    # Vista previa: muestra el post y luego un mensaje con botones.
    token = uuid.uuid4().hex[:10]
    PENDING[token] = payload
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Publicar", callback_data=f"pub:{token}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel:{token}"),
            ]
        ]
    )
    await status.delete()
    await _send_post(context, update.effective_chat.id, payload)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👆 Vista previa. ¿Publicar en el canal?",
        reply_markup=keyboard,
    )


async def _send_post(context: ContextTypes.DEFAULT_TYPE, chat_id, payload: dict) -> None:
    """Envia el post con send_photo (metodo probado y fiable).

    Foto del producto con el texto + grafico de Keepa como segunda foto aparte.
    Si falta alguna, se adapta. Si no hay ninguna, manda solo texto.
    """
    caption = payload["caption"]
    product = payload["product"]
    graph = payload["graph"]

    if product:
        await context.bot.send_photo(
            chat_id=chat_id, photo=product, caption=caption, parse_mode="HTML"
        )
        if graph:
            await context.bot.send_photo(chat_id=chat_id, photo=graph)
    elif graph:
        await context.bot.send_photo(
            chat_id=chat_id, photo=graph, caption=caption, parse_mode="HTML"
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id, text=caption, parse_mode="HTML"
        )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, _, token = query.data.partition(":")

    if action == "cancel":
        PENDING.pop(token, None)
        await query.edit_message_text("❌ Cancelado.")
        return

    if action == "pub":
        payload = PENDING.pop(token, None)
        if not payload:
            await query.answer(
                "Este post ya caducó, vuelve a pegar el enlace.", show_alert=True
            )
            return
        await _send_post(context, config.CHANNEL_ID, payload)
        await query.edit_message_text("✅ Publicado en el canal.")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra cualquier excepcion no controlada en el log."""
    log.error("Error procesando una actualizacion:", exc_info=context.error)


async def refresh_prices(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tarea periodica: refresca el precio de los productos ya publicados."""
    asins = pricedb.tracked_asins()
    log.info("Refrescando precios de %d productos…", len(asins))
    for asin in asins:
        url = amazon.build_affiliate_url(asin)
        product = amazon.scrape(url, asin)
        if product.price is not None:
            pricedb.record_price(asin, product.price)


def main() -> None:
    errors = config.validate()
    if errors:
        for e in errors:
            log.error(e)
        raise SystemExit(1)

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(on_error)

    if app.job_queue and config.REFRESH_EVERY_HOURS > 0:
        app.job_queue.run_repeating(
            refresh_prices,
            interval=config.REFRESH_EVERY_HOURS * 3600,
            first=3600,
        )

    log.info("Bot arrancado (version %s). Esperando mensajes…", VERSION)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
