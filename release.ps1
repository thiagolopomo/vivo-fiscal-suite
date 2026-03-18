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

function Require-Command($name, $friendlyName) {
    if (!(Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$friendlyName não encontrado no PATH."
    }
}

$ProjectRoot = "C:\Users\ThiagoLopomo\Documents\Exes Vivo\app_vivo"
Set-Location $ProjectRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}
else {
    Write-Host "Aviso: .venv local não encontrada. Usando o ambiente já ativo." -ForegroundColor Yellow
}

Require-Command "git" "Git"
Require-Command "gh" "GitHub CLI"

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

if (!(Test-Path ".\.git")) {
    throw "Esta pasta não é um repositório Git."
}

$configPath = ".\release_config.json"
if (!(Test-Path $configPath)) {
    throw "release_config.json não encontrado."
}

Write-Step "Validando autenticação GitHub"
gh auth status | Out-Null

Write-Step "Validando estado do repositório"
git fetch origin

$branch = (git branch --show-current).Trim()
if ($branch -ne "main") {
    throw "Branch atual é '$branch'. Execute o release na branch main."
}

$statusPorcelain = git status --porcelain
if ($statusPorcelain) {
    Write-Host "Há mudanças locais pendentes antes do release:" -ForegroundColor Red
    git status --short
    throw "Faça commit/stash das alterações antes de rodar o release."
}

Write-Step "Sincronizando com origin/main"
git pull --rebase origin main

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$version = $config.version
$parts = $version.Split(".")

if ($parts.Count -ne 3) {
    throw "Versão inválida em release_config.json: $version"
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
    throw "Use -patch, -minor ou -major."
}

$newVersion = "$maj.$min.$pat"

Write-Step "Nova versão calculada: $newVersion"

Write-Step "Validando se tag já existe"

$existingTag = git tag -l "v$newVersion"
if ($existingTag) {
    throw "A tag v$newVersion já existe localmente. Escolha outra versão."
}

$remoteTagExists = $null
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"

try {
    $remoteTagExists = gh release view "v$newVersion" --json tagName --jq ".tagName" 2>$null
}
catch {
    $remoteTagExists = $null
}
finally {
    $ErrorActionPreference = $oldEAP
}

if ($remoteTagExists -eq "v$newVersion") {
    throw "A release v$newVersion já existe no GitHub."
}

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
    throw "package.zip não encontrado após o build."
}

if (-not $SkipInstaller) {
    if (-not $innoCompiler) {
        throw "ISCC.exe não encontrado. Use -SkipInstaller ou instale o Inno Setup."
    }

    if (!(Test-Path ".\installer.iss")) {
        throw "installer.iss não encontrado."
    }

    Write-Step "Compilando instalador Inno Setup"
    & $innoCompiler "/DMyAppVersion=$newVersion" ".\installer.iss"

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao compilar o instalador."
    }
}

Write-Step "Removendo artefatos pesados do índice Git"
git rm -r --cached --ignore-unmatch dist build package assets/updates/build assets/updates/dist *> $null
git rm --cached --ignore-unmatch package.zip assets/updates/updater.spec *> $null

git rm -r --cached --ignore-unmatch installer_output *> $null
Write-Step "Preparando commit"

git add -A

$stagedNow = @(git diff --cached --name-only)

if ($stagedNow -contains "package.zip") {
    git restore --staged -- "package.zip"
}

if ($stagedNow | Where-Object { $_ -like "installer_output/*" }) {
    git restore --staged --worktree --source=HEAD -- installer_output 2>$null
    git restore --staged -- installer_output 2>$null
}

# impedir arquivos grandes no commit
$largeFiles = git diff --cached --name-only | Where-Object {
    (Get-Item $_ -ErrorAction SilentlyContinue).Length -gt 100MB
}

if ($largeFiles) {
    Write-Host "Arquivos grandes detectados no commit:" -ForegroundColor Red
    $largeFiles
    throw "Release abortada: arquivos maiores que 100MB não podem ir para o Git."
}

Write-Step "Status preparado para commit"
git status --short

$hasChanges = git diff --cached --name-only

if ($hasChanges) {
    git commit -m "release: v$newVersion"

    git push origin main
    if ($LASTEXITCODE -ne 0) {
        throw "Falha no git push. Release abortada."
    }
}
else {
    throw "Nenhuma mudança foi preparada para commit."
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

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$versionUrl = "https://raw.githubusercontent.com/$($config.repo_owner)/$($config.repo_name)/main/version.json"

Write-Step "Concluído"
Write-Host "Versão: $newVersion" -ForegroundColor Green
Write-Host "ZIP final: $(Resolve-Path .\package.zip)"
Write-Host "Manifesto: $versionUrl"

if (Test-Path ".\installer_output") {
    Write-Host "Setup(s):"
    Get-ChildItem ".\installer_output\*.exe" | ForEach-Object {
        Write-Host " - $($_.FullName)"
    }
}