from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Config
from app.database.connection import probar_conexion_bd, obtener_drivers_odbc
from app.services.productos_service import buscar_productos
from app.services.chat_service import responder_chat


app = FastAPI(
    title="Asistente Virtual de WhatsApp",
    description="Bot para atención automática de clientes usando WhatsApp, SQL e IA.",
    version="1.0.0"
)


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