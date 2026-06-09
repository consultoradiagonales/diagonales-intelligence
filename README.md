# Diagonales Intelligence Platform

Plataforma de inteligencia política y análisis de humor social para Consultora Diagonales.

> Un "Nosis" para el mundo de la consultoría política y el periodismo de datos.

---

## Qué hace

| Módulo | Descripción |
|--------|-------------|
| **Humor Social** | Mide sentimiento positivo/negativo/neutro sobre candidatos y empresas en tiempo real |
| **Radiografía** | Perfil 360°: identidad, BCRA, licitaciones, redes sociales y dorks OSINT |
| **Scraping RSS** | 19 portales nacionales y regionales, actualización cada 2 horas |
| **Scraping YouTube** | Videos + comentarios de canales políticos clave |
| **API REST** | FastAPI con endpoints para integrar con cualquier app o dashboard externo |

---

## Setup

### 1. Clonar e instalar
```bash
git clone https://github.com/consultoradiagonales/diagonales-intelligence
cd diagonales-intelligence
pip install -r requirements.txt
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env y agregar las API keys
```

### 3. Iniciar
```bash
python run.py          # API en http://localhost:8000
python run.py --once   # Ciclo completo de scraping una vez
python run.py --schedule  # Scheduler automático 24/7
```

---

## Obtener API Keys

### YouTube Data API v3 (gratis, 10.000 req/día)
1. Ir a [console.cloud.google.com](https://console.cloud.google.com)
2. Crear proyecto → buscar "YouTube Data API v3" → Habilitar
3. Credenciales → Crear clave de API
4. Pegar en `.env` como `YOUTUBE_API_KEY=`

---

## Estructura

```
diagonales-intelligence/
├── backend/
│   ├── api/main.py          ← FastAPI endpoints
│   ├── scrapers/            ← RSS, YouTube
│   ├── analyzers/           ← Sentimiento (pysentimiento), Identidad AFIP
│   └── db/                  ← SQLAlchemy models
├── frontend/
│   └── templates/           ← Dashboard, Radiografía
├── run.py                   ← Entrada principal
├── .env.example             ← Variables de entorno
└── requirements.txt
```

---

## Roadmap

- [x] Scraping RSS (19 portales)
- [x] Scraping YouTube + comentarios
- [x] Análisis de sentimiento en español (pysentimiento)
- [x] BCRA Central de Deudores API
- [x] Radiografía de identidad (DNI → CUIL algoritmo AFIP)
- [x] Search dorks OSINT automatizados
- [x] Dashboard web
- [ ] Twitter/X scraping
- [ ] Facebook / Instagram
- [ ] Alertas por Telegram/WhatsApp
- [ ] Multi-usuario con autenticación
- [ ] Exportación a PDF

---

**Consultora Diagonales** · MIT License
