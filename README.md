# Bot de chollos de Amazon para Telegram

Bot propio (reemplazo de botaffiumeiro) que, a partir de un enlace de Amazon,
publica en tu canal un post con:

- 🖼️ Imagen del producto + 📊 gráfico de histórico de precios (Keepa) en una sola imagen
- 💰 Precio actual y precio anterior, con % de descuento y ahorro
- 🏆 Badge de **precio mínimo histórico** (base de datos propia que crece con el tiempo)
- 👉 Enlace de afiliado limpio con tu tag
- 🔥 Texto con plantilla y emojis

Todo **gratis**, sin pagar APIs.

---

## Cómo funciona (modo asistido)

1. Pegas un enlace de Amazon en tu grupo/chat privado donde está el bot.
2. El bot lo procesa y te manda una **vista previa** con botones `✅ Publicar` / `❌ Cancelar`.
3. Pulsas Publicar y el post va a tu canal.

(Si pones `AUTO_PUBLISH=true`, publica directo sin vista previa.)

---

## Variables de entorno

Se configuran en la pantalla del contenedor en UGOS (sección *Environment*).

| Variable | Obligatoria | Ejemplo | Para qué sirve |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | `12345:ABC...` | Token del bot (BotFather) |
| `CHANNEL_ID` | ✅ | `@miCanal` o `-1001234567890` | Canal donde publicar (el bot debe ser admin) |
| `AFFILIATE_TAG` | ✅ | `jack051-21` | Tu tag de afiliado |
| `STAGING_CHAT_ID` | opcional | `-1009876543210` | Chat donde pegas enlaces. Vacío = cualquier chat |
| `AUTO_PUBLISH` | opcional | `false` | `true` = publica sin pedir confirmación |
| `AMAZON_DOMAIN` | opcional | `amazon.es` | Dominio de Amazon |
| `KEEPA_DOMAIN` | opcional | `es` | País del gráfico de Keepa |
| `SHOW_KEEPA_GRAPH` | opcional | `true` | Incluir el gráfico de Keepa |
| `MIN_WINDOW_DAYS` | opcional | `0` | Ventana del mínimo en días (0 = todo el historial) |
| `REFRESH_EVERY_HOURS` | opcional | `24` | Cada cuánto refresca precios para llenar el historial |
| `DB_PATH` | opcional | `/app/data/prices.db` | Ruta de la base de datos (no tocar) |

---

## Paso 1 — Crear el bot en Telegram (BotFather)

1. Abre [@BotFather](https://t.me/BotFather) en Telegram.
2. `/newbot` → elige nombre y usuario. Copia el **token**.
3. `/mybots` → tu bot → *Bot Settings* → *Group Privacy* → **Disable**
   (si no, no lee los mensajes del grupo).
4. Crea tu canal (si no lo tienes) y **añade el bot como administrador** con permiso de publicar.
5. Crea un grupo privado para ti, añade el bot, y úsalo para pegar enlaces.

> 💡 Para saber el id de un chat o canal: añade el bot, escribe `/id` y te lo dice.
> El id de un canal suele empezar por `-100`.

---

## Paso 2 — Subir el código a GitHub

1. Crea una cuenta en [github.com](https://github.com) si no la tienes.
2. Crea un repositorio nuevo (privado o público), por ejemplo `amazon-deals-bot`.
3. Sube **todos los archivos de esta carpeta** al repo (puedes arrastrarlos en la web
   de GitHub: botón *Add file → Upload files*). Asegúrate de subir también la carpeta
   `.github/workflows/docker.yml`.

En cuanto subas a la rama `main`, GitHub Actions construye la imagen automáticamente
(pestaña **Actions** del repo). Tarda 1-2 minutos.

---

## Paso 3 — Hacer pública la imagen (para que el NAS la descargue)

1. En tu perfil de GitHub → pestaña **Packages** → entra en `amazon-deals-bot`.
2. *Package settings* → *Danger Zone* → **Change visibility → Public**.

La imagen queda en:

```
ghcr.io/TU_USUARIO/amazon-deals-bot:latest
```

(sustituye `TU_USUARIO` por tu usuario de GitHub, en minúsculas).

---

## Paso 4 — Desplegar en UGOS Pro (NAS UGREEN)

1. Abre **Docker** en UGOS.
2. *Imágenes* → *Añadir* / *Extraer de registro* → pega:
   `ghcr.io/TU_USUARIO/amazon-deals-bot:latest`
3. Crea un **contenedor** con esa imagen.
4. En **Volúmenes**, monta una carpeta del NAS para guardar la base de datos:
   - Carpeta del NAS: `/volume1/docker/amazon-deals-bot`
   - Ruta en el contenedor: `/app/data`
5. En **Environment**, añade las variables de la tabla de arriba
   (como mínimo `BOT_TOKEN`, `CHANNEL_ID`, `AFFILIATE_TAG`).
6. **Política de reinicio**: *Siempre* (para que arranque solo).
7. Aplica y arranca el contenedor.

Comprueba los *logs* del contenedor: deberías ver `Bot arrancado. Esperando mensajes…`.

---

## Paso 5 — Probar

1. En tu grupo privado, escribe `/ping` → el bot responde `pong ✅`.
2. Pega un enlace de Amazon → te llega la vista previa → pulsa **Publicar**.

---

## Actualizar el bot en el futuro

Cambias el código en GitHub → Actions reconstruye la imagen sola →
en UGOS: *Imágenes → actualizar/extraer de nuevo* la imagen `:latest` y recrea el contenedor.

---

## Notas y límites

- **El scraping de Amazon es frágil**: a veces Amazon devuelve una página de robot y
  algún dato (precio o imagen) puede venir vacío. El bot sigue funcionando con lo que
  tenga; el enlace y el gráfico de Keepa siempre funcionan.
- **El mínimo histórico propio arranca vacío**: las primeras semanas el badge será
  prudente ("Buen precio"). El gráfico de Keepa muestra el pasado real desde el día 1.
  Con `REFRESH_EVERY_HOURS` el historial propio se va llenando solo.
- **Fase 2 (futuro)**: scraper automático de ofertas por categoría. Más potente pero
  más frágil; se añade cuando esto funcione bien.
