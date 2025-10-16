import os
import re
import io
import json
import requests
import datetime
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image
import pytesseract

app = FastAPI()

DB_URL = os.environ["DB_URL"]

class FileReq(BaseModel):
    url: str
    filename: str

def db_conn():
    return psycopg2.connect(DB_URL)

@app.post("/extract")
def extract(req: FileReq):
    try:
        # --- Descargar archivo desde Telegram ---
        r = requests.get(req.url, timeout=60)
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="No se pudo descargar la imagen.")
        img = Image.open(io.BytesIO(r.content))

        # --- OCR ---
        text = pytesseract.image_to_string(img, lang="spa")

        # --- Heurística simple para proveedor y total ---
        proveedor = text.split("\n")[0][:50].strip() or "Desconocido"
        moneda = "ARS" if "$" in text else "USD"

        total_match = re.search(r"Total\s*[:$]?\s*([\d.,]+)", text, re.IGNORECASE)
        if total_match:
            total_str = total_match.group(1).replace(",", ".")
            try:
                total = float(re.sub(r"[^0-9.]", "", total_str))
            except ValueError:
                total = 0.0
        else:
            total = 0.0

        # --- Guardar en base de datos ---
        conn = db_conn()
        cur = conn.cursor()

        # 1. Insertar o recuperar proveedor
        cur.execute(
            "INSERT INTO proveedores (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING RETURNING id;",
            (proveedor,)
        )
        result = cur.fetchone()
        if result:
            proveedor_id = result[0]
        else:
            cur.execute("SELECT id FROM proveedores WHERE nombre = %s;", (proveedor,))
            proveedor_id = cur.fetchone()[0]

        # 2. Insertar factura
        cur.execute(
            """
            INSERT INTO facturas (proveedor_id, fecha, moneda, total, raw_json)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (proveedor_id, datetime.date.today(), moneda, total, json.dumps({"texto": text}))
        )
        factura_id = cur.fetchone()[0]
        conn.commit()

        cur.close()
        conn.close()

        return {
            "factura_id": factura_id,
            "proveedor": proveedor,
            "total": total,
            "moneda": moneda,
            "items": [],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

