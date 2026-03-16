param(
    [string]$Notes = "",
    [switch]$patch,
    [switch]$minor,
    [switch]$major,
    [bool]$Mandatory = $false,
    [switch]$SkipGitHubRelease,
    [switch]$SkipInstaller,
    [switch]$KeepBuildArtifacts
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==== $msg ====" -ForegroundColor Yellow
}

function Remove-IfExists($path) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
    }
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

$innoCompiler = $null
$possibleInno = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

foreach ($path in $possibleInno) {
    if (Test-Path $path) {
        $innoCompiler = $path
        break
    }
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

Write-Step "Limpando artefatos antigos"
Remove-IfExists ".\dist"
Remove-IfExists ".\build"
Remove-IfExists ".\package"
Remove-IfExists ".\package.zip"
Remove-IfExists ".\installer_output"

Write-Step "Executando build_release.ps1"
.\build_release.ps1 -Version $newVersion -Notes $Notes -Mandatory $Mandatory

if (!(Test-Path ".\package")) {
    throw "A pasta 'package' não foi gerada pelo build."
}

if (!(Test-Path ".\package.zip")) {
    Write-Step "Gerando package.zip manualmente"
    Compress-Archive -Path ".\package\*" -DestinationPath ".\package.zip" -Force
}

if (!(Test-Path ".\package.zip")) {
    throw "package.zip não encontrado após o build."
}

if (-not $SkipInstaller) {
    if (-not $innoCompiler) {
        throw "Inno Setup Compiler (ISCC.exe) não encontrado. Use -SkipInstaller ou instale o Inno Setup."
    }

    if (!(Test-Path ".\installer.iss")) {
        throw "installer.iss não encontrado na raiz do projeto."
    }

    Write-Step "Compilando instalador Inno Setup"
    & $innoCompiler "/DMyAppVersion=$newVersion" ".\installer.iss"

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao compilar o instalador."
    }
}

Write-Step "Limpando artefatos do índice Git"
git rm -r --cached --ignore-unmatch dist build package assets/updates/build assets/updates/dist *> $null
git rm --cached --ignore-unmatch package.zip assets/updates/updater.spec *> $null

Write-Step "Commitando arquivos"
git add .gitignore
git add release_config.json version.json app_version.json
git add *.py 2>$null
git add *.ps1 2>$null
git add *.iss 2>$null
git add pages workers assets/fonts assets/updates/updater.py assets/updates/updater.exe 2>$null
git add icone.ico icone.png logo_vivo.png 2>$null

$hasChanges = git diff --cached --name-only
if ($hasChanges) {
    git commit -m "release: v$newVersion"
    git push
} else {
    Write-Host "Nenhuma mudança para commit."
}

if (-not $SkipGitHubRelease) {
    Write-Step "Publicando GitHub Release"
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    $repo = "$($config.repo_owner)/$($config.repo_name)"

    gh release create "v$newVersion" ".\package.zip" `
      --repo $repo `
      --title "VIVO Fiscal Suite $newVersion" `
      --notes "$Notes"
}

if (-not $KeepBuildArtifacts) {
    Write-Step "Limpando artefatos locais pesados"
    Remove-IfExists ".\dist"
    Remove-IfExists ".\build"
    Remove-IfExists ".\package"
}

Write-Step "Concluído"
Write-Host "Versão: $newVersion" -ForegroundColor Green
Write-Host "ZIP final: $(Resolve-Path .\package.zip)"
if (Test-Path ".\installer_output") {
    Write-Host "Setup(s):"
    Get-ChildItem ".\installer_output\*.exe" | ForEach-Object {
        Write-Host " - $($_.FullName)"
    }
}