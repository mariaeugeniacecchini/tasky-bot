import os
import asyncio
import httpx
import psycopg2
from aiogram import Bot, Dispatcher, types

TOKEN = os.environ["TELEGRAM_TOKEN"]
PROCESSOR_URL = os.environ["PROCESSOR_URL"]
DB_URL = os.environ["DB_URL"]

bot = Bot(token=TOKEN)
dp = Dispatcher()


def db_conn():
    return psycopg2.connect(DB_URL)


@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("📄 Enviame una factura en imagen o PDF para procesarla.")


@dp.message(content_types=["photo", "document"])
async def handle_invoice(message: types.Message):
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = message.document.file_id

    file = await bot.get_file(file_id)
    file_path = file.file_path
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

    await message.answer("🔍 Procesando la factura...")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(PROCESSOR_URL, json={"url": file_url, "filename": file_path})
        data = resp.json()

    await message.answer(
        f"✅ Factura procesada.\nProveedor: {data.get('proveedor','?')}\n"
        f"Total: {data.get('total','?')} {data.get('moneda','')}\n"
        f"Items: {len(data.get('items', []))}"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

