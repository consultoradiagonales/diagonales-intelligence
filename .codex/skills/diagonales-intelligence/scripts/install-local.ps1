param(
  [string]$DestinationRoot = "$env:USERPROFILE\.codex\skills"
)

$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot
$SkillName = Split-Path -Leaf $SkillRoot
$Destination = Join-Path $DestinationRoot $SkillName

New-Item -ItemType Directory -Force $DestinationRoot | Out-Null
if (Test-Path $Destination) {
  Remove-Item -LiteralPath $Destination -Recurse -Force
}
Copy-Item -LiteralPath $SkillRoot -Destination $Destination -Recurse

Write-Host "Installed $SkillName to $Destination"
