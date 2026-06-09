#!/usr/bin/env python3
"""
Launcher — Diagonales Intelligence Dashboard
Ejecuta la API FastAPI con el dashboard web
Uso: python run_dashboard.py [puerto]
"""
import sys
import os
import webbrowser
import time
import uvicorn

BASE = os.path.dirname(__file__)
os.chdir(BASE)
sys.path.insert(0, BASE)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

print(f"""
╔════════════════════════════════════════════════════════════════╗
║          DIAGONALES INTELLIGENCE DASHBOARD                     ║
╚════════════════════════════════════════════════════════════════╝

🚀 Iniciando en puerto {PORT}...
🌐 Abre: http://localhost:{PORT}

📊 Dashboard:     http://localhost:{PORT}/
🔍 Radiografía:  http://localhost:{PORT}/radiografia

Presiona Ctrl+C para detener
""")

# Esperar un segundo y abrir navegador
time.sleep(1)
try:
    webbrowser.open(f"http://localhost:{PORT}")
except:
    print(f"(No se abrió navegador automáticamente)")

# Iniciar servidor
uvicorn.run("backend.api.main:app", host="0.0.0.0", port=PORT, reload=False)
