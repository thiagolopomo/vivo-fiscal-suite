param(
    [string]$Notes = "",
    [switch]$patch,
    [switch]$minor,
    [switch]$major
)

$ErrorActionPreference = "Stop"

Set-Location "C:\Users\ThiagoLopomo\Documents\Exes Vivo\app_vivo"

.\.venv\Scripts\Activate.ps1

$configPath = ".\release_config.json"

if (!(Test-Path $configPath)) {
    throw "release_config.json não encontrado"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json

$version = $config.version
$parts = $version.Split(".")

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

Write-Host ""
Write-Host "Nova versão:" $newVersion
Write-Host ""

$config.version = $newVersion
$config.notes = $Notes

$config | ConvertTo-Json -Depth 5 | Set-Content ".\release_config.json"

# chama build
.\build_release.ps1 -Version $newVersion -Notes $Notes

git add release_config.json version.json app_version.json
git commit -m "release v$newVersion"
git push

gh release create "v$newVersion" ".\package.zip" `
  --repo "thiagolopomo/vivo-fiscal-suite" `
  --title "VIVO Fiscal Suite $newVersion" `
  --notes "$Notes"

Write-Host ""
Write-Host "===================================="
Write-Host "RELEASE PUBLICADA"
Write-Host "Versão:" $newVersion
Write-Host "===================================="