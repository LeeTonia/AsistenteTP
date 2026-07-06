from fastapi import FastAPI, Request, HTTPException, Response
import json
from pydantic import BaseModel

from app.config import Config
from app.database.connection import probar_conexion_bd, obtener_drivers_odbc
from app.services.productos_service import buscar_productos
from app.services.chat_service import responder_chat
from app.routes.whatsapp_routes import router as whatsapp_router


app = FastAPI(
    title="Asistente Virtual de WhatsApp",
    description="Bot para atención automática de clientes usando WhatsApp, SQL e IA.",
    version="1.0.0"
)

app.include_router(whatsapp_router)


class MensajeEntrada(BaseModel):
    mensaje: str


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Asistente virtual funcionando correctamente",
        "negocio": Config.NOMBRE_NEGOCIO
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "asistente-whatsapp"
    }


@app.get("/db/test")
def db_test():
    return probar_conexion_bd()


@app.get("/db/drivers")
def db_drivers():
    return obtener_drivers_odbc()


@app.get("/productos/buscar")
def productos_buscar(texto: str, solo_disponibles: bool = True, limite: int = 10):
    return buscar_productos(
        texto=texto,
        solo_disponibles=solo_disponibles,
        limite=limite
    )


@app.post("/chat/test")
def chat_test(data: MensajeEntrada):
    return responder_chat(data.mensaje)

@app.get("/webhook")
async def verificar_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    print("GET /webhook recibido:", dict(params), flush=True)

    if mode == "subscribe" and token == Config.WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge or "", media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verify token incorrecto")


@app.post("/webhook")
async def recibir_webhook(request: Request):
    data = await request.json()

    print("POST /webhook recibido:", json.dumps(data, indent=2, ensure_ascii=False), flush=True)

    return {"status": "ok"}