# Ejecutor maestro — Diagonales Intelligence
# Uso:
#   .\EXEC.ps1 dashboard    → Lanza web en :8000
#   .\EXEC.ps1 scraping     → Ciclo completo (RSS + YT + análisis + reportes)
#   .\EXEC.ps1 reportes     → Solo genera reportes

param([string]$command = "dashboard")

$ErrorActionPreference = "Stop"
$BASE = Split-Path -Parent $MyInvocation.MyCommand.Path
$SCRAPING_DATOS = "$BASE\..\SCRAPING DATOS"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║          DIAGONALES INTELLIGENCE — EJECUTOR MAESTRO            ║" -ForegroundColor Magenta
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

switch ($command) {
    "dashboard" {
        Write-Host "🌐 Iniciando DASHBOARD WEB..." -ForegroundColor Cyan
        Write-Host "   Abrirá: http://localhost:8000" -ForegroundColor Green
        Write-Host ""
        cd $BASE
        python run_dashboard.py
    }

    "scraping" {
        Write-Host "🔄 Ejecutando CICLO COMPLETO DE SCRAPING..." -ForegroundColor Cyan
        Write-Host "   1. RSS (19 portales)"
        Write-Host "   2. YouTube (videos + comentarios)"
        Write-Host "   3. Análisis sentimiento"
        Write-Host "   4. Reportes (Excel + DOCX + HTML)"
        Write-Host ""
        cd "$SCRAPING_DATOS"
        python scheduler.py --ahora
    }

    "reportes" {
        Write-Host "📊 Generando REPORTES..." -ForegroundColor Cyan
        Write-Host "   Outputs: Excel | DOCX | HTML | Consola"
        Write-Host ""
        cd "$SCRAPING_DATOS"
        python scrapers/generador_reportes.py
    }

    "rss" {
        Write-Host "📰 Scraping RSS solamente..." -ForegroundColor Cyan
        cd "$SCRAPING_DATOS"
        python scheduler.py --rss
    }

    "youtube" {
        Write-Host "▶️  Scraping YouTube solamente..." -ForegroundColor Cyan
        cd "$SCRAPING_DATOS"
        python scheduler.py --yt
    }

    "objetivos" {
        Write-Host "👥 Gestión de OBJETIVOS" -ForegroundColor Cyan
        Write-Host "   Opciones:"
        Write-Host "   • listar"
        Write-Host "   • agregar"
        Write-Host "   • activar <id>"
        Write-Host "   • desactivar <id>"
        Write-Host ""
        $accion = Read-Host "Ingresa comando"
        cd "$SCRAPING_DATOS"
        python gestionar.py $accion
    }

    default {
        Write-Host "❌ Comando desconocido: $command" -ForegroundColor Red
        Write-Host ""
        Write-Host "Comandos disponibles:" -ForegroundColor Yellow
        Write-Host "   dashboard   → Dashboard web en http://localhost:8000"
        Write-Host "   scraping    → Ciclo completo (RSS + YT + análisis + reportes)"
        Write-Host "   reportes    → Solo generar reportes"
        Write-Host "   rss         → Solo RSS scraping"
        Write-Host "   youtube     → Solo YouTube scraping"
        Write-Host "   objetivos   → Gestionar objetivos"
        Write-Host ""
        Write-Host "Ejemplo:"
        Write-Host "   .\EXEC.ps1 dashboard" -ForegroundColor Cyan
    }
}
