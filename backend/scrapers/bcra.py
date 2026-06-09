"""
Scraper BCRA Central de Deudores.
Usa la API REST pública del BCRA (sin Playwright, sin CAPTCHA).
API docs: https://api.bcra.gob.ar/CentralDeDeudores/v1.0
"""
import httpx
import json
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

BCRA_API_BASE = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0"

# Headers mínimos para la API pública
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Diagonales-Intelligence/1.0"
}


def consultar_deudas(identificacion: str, timeout: int = 15) -> dict:
    """
    Consulta la Central de Deudores del BCRA para un CUIT/CUIL.
    Devuelve el estado crediticio y detalle de deudas si existen.
    """
    limpio = "".join(c for c in identificacion if c.isdigit())
    resultado = {
        "identificacion": limpio,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fuente": BCRA_API_BASE,
        "estado": "desconocido",
        "deudas": [],
        "historico": [],
        "cheques_rechazados": [],
        "error": None
    }

    try:
        # 1. Deudas actuales
        r = httpx.get(f"{BCRA_API_BASE}/Deudas/{limpio}", headers=HEADERS, timeout=timeout, verify=False)

        if r.status_code == 200:
            data = r.json()
            resultados = data.get("results", {})
            periodos = resultados.get("periodos", [])

            if not periodos:
                resultado["estado"] = "sin_deudas"
            else:
                resultado["estado"] = "con_deudas"
                for p in periodos:
                    for entidad in p.get("entidades", []):
                        resultado["deudas"].append({
                            "periodo":   p.get("periodo"),
                            "entidad":   entidad.get("entidad"),
                            "situacion": entidad.get("situacion"),
                            "monto":     entidad.get("monto"),
                            "diasAtrasoPago": entidad.get("diasAtrasoPago"),
                            "refinanciaciones": entidad.get("refinanciaciones"),
                        })

        elif r.status_code == 404:
            resultado["estado"] = "sin_deudas"
        else:
            resultado["estado"] = "error_api"
            resultado["error"] = f"HTTP {r.status_code}"

        # 2. Historial
        r2 = httpx.get(f"{BCRA_API_BASE}/DeudasHistoricas/{limpio}", headers=HEADERS, timeout=timeout, verify=False)
        if r2.status_code == 200:
            data2 = r2.json()
            for p in data2.get("results", {}).get("periodos", []):
                for ent in p.get("entidades", []):
                    resultado["historico"].append({
                        "periodo":   p.get("periodo"),
                        "entidad":   ent.get("entidad"),
                        "situacion": ent.get("situacion"),
                        "monto":     ent.get("monto"),
                    })

        # 3. Cheques rechazados
        r3 = httpx.get(f"{BCRA_API_BASE}/ChequesRechazados/{limpio}", headers=HEADERS, timeout=timeout, verify=False)
        if r3.status_code == 200:
            data3 = r3.json()
            for cheque in data3.get("results", {}).get("causales", []):
                resultado["cheques_rechazados"].append({
                    "causal":   cheque.get("causal"),
                    "entidad":  cheque.get("entidad"),
                    "nroCheque": cheque.get("nroCheque"),
                    "monto":    cheque.get("monto"),
                    "fecha":    cheque.get("fechaRechazo"),
                })

    except httpx.TimeoutException:
        resultado["estado"] = "timeout"
        resultado["error"] = "La API del BCRA no respondió"
    except Exception as e:
        resultado["estado"] = "error"
        resultado["error"] = str(e)
        log.error(f"BCRA error para {limpio}: {e}")

    log.info(f"BCRA [{limpio}]: {resultado['estado']} | {len(resultado['deudas'])} deudas")
    return resultado


def consultar_multiples(cuils: list[str]) -> list[dict]:
    """Consulta BCRA para varios CUIL/CUIT y devuelve todos los resultados."""
    return [consultar_deudas(c) for c in cuils]


def clasificar_riesgo(resultado: dict) -> str:
    """Clasifica el riesgo crediticio en base al resultado del BCRA."""
    if resultado["estado"] == "sin_deudas":
        return "bajo"
    if resultado["estado"] == "error":
        return "indeterminado"

    situaciones = [d.get("situacion", 1) for d in resultado["deudas"]]
    if not situaciones:
        return "bajo"

    max_sit = max(situaciones)
    if max_sit >= 4:
        return "alto"
    if max_sit >= 2:
        return "medio"
    return "bajo"
