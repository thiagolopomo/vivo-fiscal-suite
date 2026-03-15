param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [string]$Notes = "",

    [bool]$Mandatory = $false
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==== $msg ====" -ForegroundColor Cyan
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLower()
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $fullPath = $Path
    }
    else {
        $fullPath = Join-Path $ProjectRoot $Path
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($fullPath, $Content, $utf8NoBom)
}

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}
else {
    Write-Host "Aviso: .venv local não encontrada. Usando o Python/ambiente já ativo." -ForegroundColor Yellow
}

$configPath = Join-Path $ProjectRoot "release_config.json"
if (!(Test-Path $configPath)) {
    throw "release_config.json não encontrado."
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$config.version = $Version
if ($Notes -ne "") { $config.notes = $Notes }
$config.mandatory = $Mandatory

Write-Step "Atualizando release_config.json"
$jsonConfig = $config | ConvertTo-Json -Depth 10
Write-Utf8NoBom $configPath $jsonConfig

Write-Step "Gerando app_version.json"
$appVersionContent = @"
{
  "version": "$($config.version)"
}
"@
Write-Utf8NoBom ".\app_version.json" $appVersionContent

Write-Step "Compilando updater"
Set-Location ".\assets\updates"

pyinstaller --noconfirm --clean --onefile --windowed --name updater updater.py

if (!(Test-Path ".\dist\updater.exe")) {
    throw "Falha: updater.exe não foi gerado."
}

Move-Item ".\dist\updater.exe" ".\updater.exe" -Force

if (!(Test-Path ".\updater.exe")) {
    throw "Falha: updater.exe não existe após mover."
}

Set-Location "..\.."

Write-Step "Limpando build anterior"
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
Remove-Item -Force .\main.spec -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\package -ErrorAction SilentlyContinue
Remove-Item -Force .\package.zip -ErrorAction SilentlyContinue

Write-Step "Compilando app principal"
pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name "main" `
  --icon ".\icone.ico" `
  --add-data ".\logo_vivo.png;." `
  --add-data ".\icone.ico;." `
  --add-data ".\app_version.json;." `
  --add-data ".\release_config.json;." `
  --add-data ".\assets;assets" `
  --hidden-import "pages.dashboard_page" `
  --hidden-import "pages.p9_page" `
  --hidden-import "pages.consolidator_page" `
  --hidden-import "workers.p9_worker" `
  --hidden-import "workers.consolidator_worker" `
  main.py

if (!(Test-Path ".\dist\main\main.exe")) {
    throw "Falha: main.exe não foi gerado."
}

Write-Step "Garantindo updater no dist"
New-Item -ItemType Directory -Force -Path ".\dist\main\assets\updates" | Out-Null
Copy-Item ".\assets\updates\updater.exe" ".\dist\main\assets\updates\updater.exe" -Force

if (!(Test-Path ".\dist\main\assets\updates\updater.exe")) {
    throw "Falha: updater.exe não foi copiado para o dist."
}

Write-Step "Montando package.zip"
New-Item -ItemType Directory -Path .\package | Out-Null
Copy-Item ".\dist\main\*" ".\package" -Recurse -Force
Compress-Archive -Path ".\package\*" -DestinationPath ".\package.zip" -Force

if (!(Test-Path ".\package.zip")) {
    throw "Falha: package.zip não foi gerado."
}

$sha256 = Get-FileSha256 ".\package.zip"
$packageUrl = "https://github.com/$($config.repo_owner)/$($config.repo_name)/releases/download/v$($config.version)/package.zip"

Write-Step "Gerando version.json"
$versionContent = @"
{
  "version": "$($config.version)",
  "mandatory": $($config.mandatory.ToString().ToLower()),
  "notes": "$($config.notes.Replace('"','\"'))",
  "url": "$packageUrl",
  "sha256": "$sha256"
}
"@
Write-Utf8NoBom ".\version.json" $versionContent

Write-Step "Build finalizado"
Write-Host "Versão: $($config.version)" -ForegroundColor Green
Write-Host "SHA256: $sha256"
Write-Host "App teste: $(Resolve-Path .\dist\main\main.exe)"
Write-Host "ZIP: $(Resolve-Path .\package.zip)"
Write-Host "Manifesto: $(Resolve-Path .\version.json)"