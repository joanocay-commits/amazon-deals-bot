"""Punto de entrada del bot de chollos.

Flujo (modo asistido):
1. Pegas un enlace de Amazon en el chat privado / grupo donde esta el bot.
2. El bot extrae datos, compone la imagen (producto + grafico Keepa) y el texto.
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
log = logging.getLogger("bot")

# Posts pendientes de confirmar: token -> {"photo": bytes, "caption": str}
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

    graph = keepa_graph.download(product.asin)
    image = compose.build_post_image(product.image_url, graph)
    caption = post.build_caption(product, info)

    if config.AUTO_PUBLISH:
        await _publish(context, image, caption)
        await status.edit_text("✅ Publicado en el canal.")
        return

    # Vista previa con botones.
    token = uuid.uuid4().hex[:10]
    PENDING[token] = {"photo": image, "caption": caption}
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Publicar", callback_data=f"pub:{token}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel:{token}"),
            ]
        ]
    )
    await status.delete()
    if image:
        await update.message.reply_photo(
            photo=image, caption=caption, parse_mode="HTML", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            caption, parse_mode="HTML", reply_markup=keyboard,
            disable_web_page_preview=False,
        )


async def _publish(context: ContextTypes.DEFAULT_TYPE, image: bytes | None, caption: str) -> None:
    if image:
        await context.bot.send_photo(
            chat_id=config.CHANNEL_ID, photo=image, caption=caption, parse_mode="HTML"
        )
    else:
        await context.bot.send_message(
            chat_id=config.CHANNEL_ID, text=caption, parse_mode="HTML"
        )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, _, token = query.data.partition(":")
    payload = PENDING.pop(token, None)

    if action == "cancel":
        if query.message.photo:
            await query.edit_message_caption(caption="❌ Cancelado.")
        else:
            await query.edit_message_text("❌ Cancelado.")
        return

    if action == "pub":
        if not payload:
            await query.answer("Este post ya caducó, vuelve a pegar el enlace.", show_alert=True)
            return
        await _publish(context, payload["photo"], payload["caption"])
        if query.message.photo:
            await query.edit_message_caption(
                caption=payload["caption"] + "\n\n✅ <i>Publicado en el canal</i>",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(
                payload["caption"] + "\n\n✅ <i>Publicado en el canal</i>",
                parse_mode="HTML",
            )


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

    if app.job_queue and config.REFRESH_EVERY_HOURS > 0:
        app.job_queue.run_repeating(
            refresh_prices,
            interval=config.REFRESH_EVERY_HOURS * 3600,
            first=3600,
        )

    log.info("Bot arrancado. Esperando mensajes…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
