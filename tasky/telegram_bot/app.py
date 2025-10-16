import os
import httpx
import psycopg2
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ["TELEGRAM_TOKEN"]
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/telegram_in")
DB_URL = os.environ["DB_URL"]


# --- Comandos básicos --- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy Tasky, tu asistente de facturas.\n\n"
        "Envíame una factura (foto o PDF) para procesarla.\n"
        "Usá /ayuda para ver todos los comandos."
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "*Comandos disponibles:*\n"
        "/start — mensaje de bienvenida\n"
        "/ayuda — muestra este mensaje\n"
        "/ver_facturas — muestra las últimas facturas procesadas\n\n"
        "📸 Enviame una imagen o PDF de una factura para analizarla."
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


# --- Enviar archivos a n8n --- #
async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    file_id, file_name = None, None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"factura_{message.message_id}.jpg"
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    else:
        await message.reply_text("Solo acepto imágenes o archivos PDF.")
        return

    file = await context.bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"

    payload = {
        "user": update.effective_user.username or "usuario",
        "file_url": file_url,
        "file_name": file_name,
    }

    await message.reply_text("📤 Enviando la factura a Tasky para procesar...")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            await client.post(N8N_WEBHOOK_URL, json=payload)
        await message.reply_text("Factura enviada a procesamiento.")
    except Exception as e:
        await message.reply_text(f"Error al enviar la factura: {e}")


# --- Consultar últimas facturas desde la base --- #
async def ver_facturas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        con = psycopg2.connect(DB_URL)
        cur = con.cursor()
        cur.execute(
            """
            SELECT f.id, COALESCE(p.nombre, '(sin proveedor)'), 
                   TO_CHAR(f.fecha, 'YYYY-MM-DD'), f.total, f.moneda
            FROM facturas f 
            LEFT JOIN proveedores p ON p.id = f.proveedor_id
            ORDER BY f.created_at DESC LIMIT 5;
            """
        )
        rows = cur.fetchall()
        cur.close()
        con.close()

        if not rows:
            await update.message.reply_text("No hay facturas registradas aún.")
            return

        texto = "🧾 *Últimas facturas:*\n\n"
        for fid, prov, fecha, total, moneda in rows:
            texto += f"• #{fid} — {prov} — {fecha} — {total} {moneda}\n"

        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error al consultar la base: {e}")


# --- Comando de prueba --- #
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong! Tasky está online.")


# --- Inicialización del bot --- #
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ver_facturas", ver_facturas))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.PDF, handle_invoice))

    print("Bot iniciado y escuchando mensajes...")
    app.run_polling()


if __name__ == "__main__":
    main()

