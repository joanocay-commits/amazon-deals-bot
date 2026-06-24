# Contexto del proyecto: botaffiumeiro — mejoras pendientes

## Quién soy y qué tengo montado

Soy Joan, tengo un canal de Telegram llamado **"Ofertas y Chollos Amazon y Aliexpress"** donde publico chollos con enlaces de afiliado de Amazon (tag: `jack051-21`). Para convertir los enlaces automáticamente, uso el bot **botaffiumeiro** (fork de [hectorzin/botaffiumeiro](https://github.com/hectorzin/botaffiumeiro)), corriendo en Docker en mi NAS UGREEN DXP2800 con UGOS Pro.

El flujo actual es:
1. Encuentro un chollo en Amazon
2. Pego el enlace en un grupo privado de Telegram donde está el bot
3. El bot lo convierte con mi tag de afiliado
4. Copio el resultado y lo publico en mi canal

---

## Estado actual del bot

### Infraestructura
- **Docker**: corriendo en UGOS Pro (NAS UGREEN DXP2800), interfaz gráfica sin terminal
- **Imagen**: `ghcr.io/hectorzin/botaffiumeiro`
- **Volumen montado**: `/volume1/docker/botaffiumeiro:/app/data`
- **Estado**: funcionando correctamente (running)

### Config actual (`/volume1/docker/botaffiumeiro/config.yaml`)

```yaml
telegram:
  bot_token: "TOKEN_AQUI"
  delete_messages: true
  excluded_users: []
amazon:
  amazon.es: jack051-21
affiliate_settings:
  creator_affiliate_percentage: 0
aliexpress:
  discount_codes: |
    Codigos descuento AliExpress:
    2$ de descuento en compras de +20$: IFPTKOH
discount_keywords:
  - descuentos
  - ofertas
messages:
  affiliate_link_modified: ""
  reply_provided_by_user: ""
```

### Problemas resueltos durante la sesión (para no repetirlos)

1. **Formato incorrecto de la sección amazon**: el bot NO usa `affiliate_id: "jack051-21"`. Usa el dominio como clave: `amazon.es: jack051-21`. Con el formato incorrecto el bot no reconocía el tag y le daba el 100% de los enlaces al creador.

2. **Porcentaje del creador**: el bot tiene por defecto un 10% de enlaces que van al tag del creador (hay dos autores: `HectorziN` y `danimart1991`, con 50% cada uno entre ellos). El campo correcto para eliminarlo es `affiliate_settings: creator_affiliate_percentage: 0`. El campo va bajo `affiliate_settings:`, no bajo `creators:` ni en otro sitio.

3. **Codificación UTF-8**: el bot se cae con `UnicodeDecodeError` si el config.yaml no está en UTF-8 puro. Los acentos y emojis guardados con codificación Latin-1/Windows rompen el bot. Solución: guardar en UTF-8 o evitar caracteres especiales en el config.

4. **YAML inválido**: el bot se cae si hay comillas envolviendo todo el bloque, propiedades en la misma línea, o tabuladores en vez de espacios. El YAML es muy estricto con la indentación.

5. **Privacidad del bot en grupos**: si no se desactiva "Group Privacy" en BotFather (`/mybots → Bot Settings → Group Privacy → Disable`), el bot no lee los mensajes del grupo. Además, si el bot ya estaba en el grupo antes de desactivar la privacidad, hay que sacarlo y volver a añadirlo.

---

## Estructura del código fuente del bot

```
botaffiumeiro/
├── botaffiumeiro.py          # Entry point
├── config.py                 # Carga y gestión del config.yaml
├── creators_affiliates.yaml  # Tags de afiliado de los autores del bot
├── handlers/
│   ├── base_handler.py       # Lógica principal: procesar mensajes y construir respuesta
│   ├── aliexpress_handler.py
│   ├── aliexpress_api_handler.py
│   ├── pattern_handler.py
│   └── patterns.py
└── tests/
```

### Fragmento clave de `handlers/base_handler.py` (línea ~137)

```python
user_first_name = message.from_user.first_name
user_username = message.from_user.username
polite_message = f"{self.config_manager.msg_reply_provided_by_user} @{user_username if user_username else user_first_name}:\n\n{new_text}\n\n{self.config_manager.msg_affiliate_link_modified}"
```

Este es el mensaje que el bot construye. El `@usuario` está **hardcodeado** en el código, no en el config. Aunque `reply_provided_by_user` esté vacío en el config, el bot sigue poniendo `@tunombre:` al inicio del mensaje.

### Método de envío en `base_handler.py`

```python
if self.config_manager.delete_messages:
    await message.delete()
    await message.chat.send_message(text=polite_message, ...)
else:
    await message.chat.send_message(text=polite_message, reply_to_message_id=message.message_id)
```

El bot solo usa `send_message` (texto puro). **No tiene ninguna función para enviar fotos, imágenes ni miniaturas del producto.**

---

## Mejoras que quiero implementar

### Mejora 1 — Eliminar el `@usuario` del mensaje (PRIORITARIA)
**Problema**: aunque `reply_provided_by_user: ""` esté vacío en el config, el bot siempre añade `@tunombre:` porque está hardcodeado en el código.

**Dónde está**: `handlers/base_handler.py`, línea ~137, en la construcción de `polite_message`.

**Lo que quiero**: que el mensaje sea simplemente el enlace convertido, sin ninguna referencia al usuario que lo pegó. Algo así:

```python
polite_message = f"{new_text}"
# O si se quiere mantener el mensaje de afiliado:
polite_message = f"{new_text}\n\n{self.config_manager.msg_affiliate_link_modified}" if self.config_manager.msg_affiliate_link_modified else new_text
```

O mejor, hacer que sea configurable desde el config: un campo `show_username: false` que controle si aparece el `@usuario` o no.

---

### Mejora 2 — Enviar imagen del producto junto con el enlace
**Problema**: el bot solo envía texto (`send_message`). No extrae ni envía la imagen del producto de Amazon.

**Lo que quiero**: que cuando convierta un enlace de Amazon, además del texto con el enlace afiliado, envíe la imagen principal del producto. Esto haría los posts del canal mucho más atractivos visualmente.

**Cómo se podría implementar**:
- Extraer el ASIN del enlace de Amazon (ya lo hace el bot para construir la URL afiliada)
- Con el ASIN, hacer una petición a la página del producto y extraer la imagen principal (scraping del og:image o similar)
- Usar `send_photo` en vez de `send_message`, o `send_message` con la imagen adjunta

**Consideraciones**:
- La API oficial de Amazon (Product Advertising API) da imágenes de forma fiable, pero requiere 3 ventas previas para obtener acceso. Sin la API hay que hacer scraping, que es menos estable.
- Amazon bloquea el scraping agresivo, habría que ir con cuidado (headers, user-agent, etc.)
- Alternativa más simple: usar la URL de og:image de la página del producto, que suele ser accesible sin autenticación.

---

### Mejora 3 — Acortar los enlaces (opcional)
**Problema**: el bot devuelve URLs largas de Amazon con todos los parámetros. Quedan feas en el canal.

**Lo que quiero**: que el enlace final sea corto, preferiblemente en formato `amzn.to/xxxxx`.

**Opciones**:
- Usar el acortador oficial de Amazon (`amzn.to`) — requiere la API de Amazon
- Usar un acortador externo (Bitly API, etc.) — añade dependencia externa pero no requiere API de Amazon
- Hacer que el bot construya la URL limpia con solo el ASIN y el tag: `https://www.amazon.es/dp/ASIN?tag=jack051-21` (no es acortado pero es limpio y corto)

---

## Contexto técnico adicional

- **Telegram bot library**: el bot usa `python-telegram-bot`
- **El bot corre en Docker**: cualquier modificación implica hacer un fork del repo, modificar el código, construir una imagen Docker propia y desplegarla. O bien montar el volumen con el código modificado encima de la imagen original.
- **Sin acceso a terminal en el NAS**: el NAS tiene interfaz gráfica de Docker (UGOS Pro). No hay acceso SSH/terminal directo. Cualquier solución tiene que funcionar como imagen Docker estándar.
- **Mi nivel técnico**: no tengo experiencia con Python. Necesito instrucciones muy concretas y código listo para copiar/pegar. Para construir la imagen Docker necesitaré guía paso a paso.

---

## Pregunta principal para esta sesión

Quiero implementar las mejoras descritas arriba, empezando por la **Mejora 1** (eliminar el @usuario) y la **Mejora 2** (enviar imagen del producto). Necesito:

1. El código modificado concreto para cada mejora
2. Instrucciones para construir una imagen Docker propia con esas modificaciones y desplegarla en mi NAS UGREEN (sin terminal, solo con la interfaz gráfica de UGOS Pro o usando GitHub Actions / Docker Hub si es necesario)
