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

function Remove-IfExists($path) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Assert-Exists([string]$Path, [string]$Label) {
    if (!(Test-Path $Path)) {
        throw "$Label não encontrado: $Path"
    }
}

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}
else {
    Write-Host "Aviso: .venv local não encontrada. Usando o ambiente já ativo." -ForegroundColor Yellow
}

Assert-Exists ".\release_config.json" "release_config.json"
Assert-Exists ".\main.py" "main.py"
Assert-Exists ".\icone.ico" "icone.ico"
Assert-Exists ".\logo_vivo.png" "logo_vivo.png"
Assert-Exists ".\assets\updates\updater.py" "updater.py"
Assert-Exists ".\Mapeamento_CFOP.csv" "Mapeamento_CFOP.csv"
Assert-Exists ".\Tabela_Divisao.csv" "Tabela_Divisao.csv"

$configPath = Join-Path $ProjectRoot "release_config.json"
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

Write-Step "Limpando builds anteriores"
Remove-IfExists ".\build"
Remove-IfExists ".\dist"
Remove-IfExists ".\package"
Remove-IfExists ".\package.zip"
Remove-IfExists ".\main.spec"
Remove-IfExists ".\assets\updates\build"
Remove-IfExists ".\assets\updates\dist"
Remove-IfExists ".\assets\updates\updater.spec"

Write-Step "Compilando updater"
Set-Location ".\assets\updates"

pyinstaller --noconfirm --clean --onefile --windowed --name updater updater.py

Assert-Exists ".\dist\updater.exe" "updater.exe gerado"
Move-Item ".\dist\updater.exe" ".\updater.exe" -Force
Assert-Exists ".\updater.exe" "updater.exe final"

Set-Location "..\.."

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
  --add-data ".\Mapeamento_CFOP.csv;." `
  --add-data ".\Tabela_Divisao.csv;." `
  --hidden-import "pages.dashboard_page" `
  --hidden-import "pages.p9_page" `
  --hidden-import "pages.consolidator_page" `
  --hidden-import "workers.p9_worker" `
  --hidden-import "workers.consolidator_worker" `
  main.py

Assert-Exists ".\dist\main\main.exe" "main.exe"

Write-Step "Garantindo updater no dist"
New-Item -ItemType Directory -Force -Path ".\dist\main\assets\updates" | Out-Null
Copy-Item ".\assets\updates\updater.exe" ".\dist\main\assets\updates\updater.exe" -Force
Assert-Exists ".\dist\main\assets\updates\updater.exe" "updater.exe copiado para dist"

Write-Step "Montando package"
New-Item -ItemType Directory -Path ".\package" -Force | Out-Null
Copy-Item ".\dist\main\*" ".\package" -Recurse -Force

Assert-Exists ".\package\main.exe" "main.exe no package"
Assert-Exists ".\package\Mapeamento_CFOP.csv" "Mapeamento_CFOP.csv no package"
Assert-Exists ".\package\Tabela_Divisao.csv" "Tabela_Divisao.csv no package"

Write-Step "Compactando package.zip"
Compress-Archive -Path ".\package\*" -DestinationPath ".\package.zip" -Force
Assert-Exists ".\package.zip" "package.zip"

$sha256 = Get-FileSha256 ".\package.zip"
$packageUrl = "https://github.com/$($config.repo_owner)/$($config.repo_name)/releases/download/v$($config.version)/package.zip"

Write-Step "Gerando version.json"
$escapedNotes = $config.notes
if ($null -eq $escapedNotes) { $escapedNotes = "" }
$escapedNotes = $escapedNotes.Replace('\', '\\').Replace('"', '\"')

$versionContent = @"
{
  "version": "$($config.version)",
  "mandatory": $($config.mandatory.ToString().ToLower()),
  "notes": "$escapedNotes",
  "url": "$packageUrl",
  "sha256": "$sha256"
}
"@
Write-Utf8NoBom ".\version.json" $versionContent

Write-Step "Copiando version.json para dist/package"
Copy-Item ".\version.json" ".\dist\main\version.json" -Force
Copy-Item ".\version.json" ".\package\version.json" -Force

Assert-Exists ".\dist\main\version.json" "version.json no dist"
Assert-Exists ".\package\version.json" "version.json no package"

Write-Step "Manifesto gerado"
Get-Content ".\version.json"

Write-Step "Build finalizado"
Write-Host "Versão: $($config.version)" -ForegroundColor Green
Write-Host "SHA256: $sha256"
Write-Host "App teste: $(Resolve-Path .\dist\main\main.exe)"
Write-Host "ZIP: $(Resolve-Path .\package.zip)"
Write-Host "Manifesto: $(Resolve-Path .\version.json)"