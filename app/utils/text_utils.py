def limpiar_texto(texto: str) -> str:
    if texto is None:
        return ""

    return texto.strip().lower()