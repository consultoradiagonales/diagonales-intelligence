param(
  [string]$OutputDir = "$(Split-Path -Parent (Split-Path -Parent $PSScriptRoot))\dist"
)

$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot
$SkillName = Split-Path -Leaf $SkillRoot
$ZipPath = Join-Path $OutputDir "$SkillName-skill.zip"

New-Item -ItemType Directory -Force $OutputDir | Out-Null
if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $SkillRoot -DestinationPath $ZipPath -Force

Write-Host "Exported $SkillName to $ZipPath"
