"""
Motor de identidad argentina.
Absorbe la lógica de validators.js del repo OSINT-SCRAPING original.
Calcula CUIT/CUIL desde DNI usando el algoritmo módulo 11 de AFIP.
"""
import re
from typing import Optional


PESOS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
PREFIJOS = {
    "masculino": ["20", "23", "24", "27"],
    "femenino":  ["27", "23"],
    "empresa":   ["30", "33", "34"],
}


def _digito_verificador(prefijo: str, dni: str) -> Optional[int]:
    """Algoritmo módulo 11 de AFIP para calcular dígito verificador."""
    base = prefijo + dni.zfill(8)
    if len(base) != 10:
        return None
    suma = sum(int(base[i]) * PESOS[i] for i in range(10))
    resto = suma % 11
    if resto == 0:
        return 0
    if resto == 1:
        return None  # combinación inválida
    return 11 - resto


def derivar_cuils(dni: str) -> list[dict]:
    """
    Dado un DNI, devuelve todos los posibles CUIT/CUIL válidos.
    Replica la lógica de reverseIntelligence() del repo original.
    """
    dni_limpio = re.sub(r"\D", "", dni).lstrip("0")
    if len(dni_limpio) < 7 or len(dni_limpio) > 8:
        return []

    variantes = []
    for genero, prefijos in PREFIJOS.items():
        for pref in prefijos:
            dv = _digito_verificador(pref, dni_limpio)
            if dv is not None:
                cuil = f"{pref}{dni_limpio.zfill(8)}{dv}"
                variantes.append({
                    "cuil": cuil,
                    "cuil_formateado": f"{cuil[:2]}-{cuil[2:10]}-{cuil[10]}",
                    "prefijo": pref,
                    "tipo": genero,
                    "confianza": "alta"
                })

    # Deduplicar por CUIL
    vistos = set()
    unicos = []
    for v in variantes:
        if v["cuil"] not in vistos:
            vistos.add(v["cuil"])
            unicos.append(v)

    return unicos


def validar_cuil(cuil: str) -> bool:
    """Valida que un CUIL/CUIT tenga formato y dígito verificador correctos."""
    limpio = re.sub(r"\D", "", cuil)
    if len(limpio) != 11:
        return False
    dv_esperado = _digito_verificador(limpio[:2], limpio[2:10])
    return dv_esperado is not None and int(limpio[10]) == dv_esperado


def normalizar_identificador(raw: str) -> dict:
    """
    Detecta si es DNI, CUIL, o CUIT y normaliza.
    Devuelve: {tipo, valor_limpio, cuils_derivados}
    """
    limpio = re.sub(r"\D", "", raw)

    if len(limpio) == 11:
        return {
            "tipo": "cuil_cuit",
            "valor_limpio": limpio,
            "formateado": f"{limpio[:2]}-{limpio[2:10]}-{limpio[10]}",
            "valido": validar_cuil(limpio),
            "cuils_derivados": [limpio]
        }
    elif 7 <= len(limpio) <= 8:
        cuils = derivar_cuils(limpio)
        return {
            "tipo": "dni",
            "valor_limpio": limpio,
            "formateado": f"{int(limpio):,}".replace(",", "."),
            "valido": True,
            "cuils_derivados": [c["cuil"] for c in cuils],
            "variantes": cuils
        }

    return {"tipo": "desconocido", "valor_limpio": limpio, "valido": False, "cuils_derivados": []}


def generar_dorks(nombre: str, cuil: Optional[str] = None) -> dict:
    """
    Genera search dorks para OSINT sobre una persona o empresa.
    Absorbe la lógica de dork-building del server.js original.
    """
    nombre_q = f'"{nombre}"'
    cuil_q = f'"{cuil}"' if cuil else ""

    base = nombre_q
    if cuil_q:
        base = f"{nombre_q} OR {cuil_q}"

    return {
        "general": [
            f"{nombre_q} Argentina",
            f"{nombre_q} político OR candidato OR funcionario",
            f"{nombre_q} empresa OR sociedad OR CUIT",
        ],
        "judiciales": [
            f'site:pjn.gov.ar {nombre_q}',
            f'site:csjn.gov.ar {nombre_q}',
            f'site:jusbaires.gob.ar {nombre_q}',
            f'{nombre_q} causa judicial OR imputado OR procesado',
        ],
        "patrimoniales": [
            f'site:declaraciones.jusnacion.gob.ar {nombre_q}',
            f'site:boletinoficial.gob.ar {base}',
            f'{nombre_q} licitación OR contratación OR compras',
            f'site:compras.gob.ar {nombre_q}',
        ],
        "redes_sociales": [
            f'site:x.com {nombre_q}',
            f'site:instagram.com {nombre_q}',
            f'site:facebook.com {nombre_q}',
            f'site:linkedin.com {nombre_q}',
        ],
        "medios": [
            f'site:infobae.com {nombre_q}',
            f'site:clarin.com {nombre_q}',
            f'site:lanacion.com.ar {nombre_q}',
            f'site:pagina12.com.ar {nombre_q}',
        ],
    }
