"""
Script de prueba para verificar que la integración con Gemini funciona.

Uso:
    1) Activa el entorno virtual:
        venv\Scripts\Activate.ps1

    2) Asegúrate de tener en `.env`:
        GEMINI_API_KEY=tu_clave
        GEMINI_MODEL=gemini-2.5-flash   (o el modelo que uses)

    3) Instala la librería de Gemini (si aún no lo hiciste):
        pip install google-generativeai

    4) Ejecuta:
        python -m test.test_gemini
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pprint

import django


def main() -> None:
    # Asegurar que la raíz del proyecto esté en sys.path
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    # Inicializar Django para poder usar el cliente y servicios
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    django.setup()

    from ia.gemini_client import call_gemini_for_solicitud

    texto = (
        "PC 25111045 para cliente SUC LOS ANGELES, bodega 013-01, "
        "transporte Camión PESCO. Productos: 3502040 CILINDRO x 5 unidades, "
        "3502021 VALVULA x 2 unidades."
    )

    print("Llamando a Gemini con texto de ejemplo...")
    payload = call_gemini_for_solicitud(texto)

    print("\nPayload devuelto por Gemini (interpretado como solicitud):")
    pprint(payload)


if __name__ == "__main__":
    main()



