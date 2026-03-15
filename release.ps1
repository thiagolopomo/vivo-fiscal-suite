param(
    [string]$Notes = "",
    [switch]$patch,
    [switch]$minor,
    [switch]$major,
    [bool]$Mandatory = $false
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==== $msg ====" -ForegroundColor Yellow
}

$ProjectRoot = "C:\Users\ThiagoLopomo\Documents\Exes Vivo\app_vivo"
Set-Location $ProjectRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}
else {
    Write-Host "Aviso: .venv local não encontrada. Usando o Python/ambiente já ativo." -ForegroundColor Yellow
}

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) não encontrado no PATH."
}

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git não encontrado no PATH."
}

gh auth status | Out-Null

if (!(Test-Path ".\.git")) {
    throw "Esta pasta não é um repositório Git. Inicialize/conecte o Git antes de publicar releases."
}

$configPath = ".\release_config.json"
if (!(Test-Path $configPath)) {
    throw "release_config.json não encontrado."
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$version = $config.version
$parts = $version.Split(".")

if ($parts.Count -ne 3) {
    throw "Versão atual inválida em release_config.json: $version"
}

$maj = [int]$parts[0]
$min = [int]$parts[1]
$pat = [int]$parts[2]

if ($patch) {
    $pat++
}
elseif ($minor) {
    $min++
    $pat = 0
}
elseif ($major) {
    $maj++
    $min = 0
    $pat = 0
}
else {
    throw "Use -patch, -minor ou -major"
}

$newVersion = "$maj.$min.$pat"

Write-Step "Nova versão calculada: $newVersion"

.\build_release.ps1 -Version $newVersion -Notes $Notes -Mandatory $Mandatory

Write-Step "Limpando artefatos do índice Git"
git rm -r --cached --ignore-unmatch dist build package assets/updates/build assets/updates/dist *> $null
git rm --cached --ignore-unmatch package.zip assets/updates/updater.spec *> $null

Write-Step "Commitando arquivos"
git add .gitignore
git add release_config.json version.json app_version.json
git add *.py 2>$null
git add *.ps1 2>$null
git add pages workers assets/fonts assets/updates/updater.py assets/updates/updater.exe 2>$null
git add icone.ico icone.png logo_vivo.png 2>$null

$hasChanges = git diff --cached --name-only
if ($hasChanges) {
    git commit -m "release: v$newVersion"
    git push
} else {
    Write-Host "Nenhuma mudança para commit."
}

Write-Step "Publicando GitHub Release"
$config = Get-Content $configPath -Raw | ConvertFrom-Json
$repo = "$($config.repo_owner)/$($config.repo_name)"

gh release create "v$newVersion" ".\package.zip" `
  --repo $repo `
  --title "VIVO Fiscal Suite $newVersion" `
  --notes "$Notes"

Write-Step "Release publicada com sucesso"
Write-Host "Versão: $newVersion" -ForegroundColor Green
Write-Host "Repo: $repo"
Write-Host "App teste: $(Resolve-Path .\dist\main\main.exe)"
Write-Host "ZIP: $(Resolve-Path .\package.zip)"