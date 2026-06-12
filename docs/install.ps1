#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Vault — Windows Kurulumu (PowerShell)
.DESCRIPTION
    Windows için Vault'un en son sürümünü indirir, kurar ve PATH'e ekler.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Repo = "yaso09/vault"
$Dest = "$env:APPDATA\Vault"

Write-Host ""
Write-Host "  ┌======================================┐"
Write-Host "  │       VAULT — Windows Kurulumu       │"
Write-Host "  └======================================┘"
Write-Host ""
Write-Host "  Hedef: $Dest"
Write-Host ""

# 1. Get latest release version
Write-Host "  [1/4] Sürüm bilgisi alınıyor..."
try {
    $api = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
    $tag = $api.tag_name
} catch {
    Write-Host "  Hata: Sürüm bilgisi alınamadı."
    exit 1
}
Write-Host "  Sürüm: $tag"

# 2. Prepare target directory
if (Test-Path "$Dest") {
    Write-Host "  [2/4] Eski kurulum kaldırılıyor..."
    Remove-Item -Recurse -Force "$Dest" -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path "$Dest" -Force | Out-Null

# 3. Download build
$url = "https://github.com/$Repo/releases/download/$tag/windows-build-artifact.zip"
$archive = "$env:TEMP\vault-windows.zip"
Write-Host "  [3/4] İndiriliyor: $url"
try {
    Invoke-WebRequest -Uri $url -OutFile $archive
} catch {
    Write-Host "  Hata: İndirme başarısız."
    exit 1
}

# 4. Extract — zip içinden windows-build-artifact/ klasörü çıkar,
#    onu sürüm adıyla $Dest altına taşı
Write-Host "  [4/4] Çıkartılıyor..."
$tempDir = "$env:TEMP\vault-extract"
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
Expand-Archive -Path $archive -DestinationPath $tempDir -Force
Remove-Item -Force $archive -ErrorAction SilentlyContinue

$inner = Get-ChildItem -Directory -Path $tempDir | Select-Object -First 1
if ($inner) {
    Move-Item -Path $inner.FullName -Destination "$Dest\$tag" -Force
} else {
    # fallback: dosyalar doğrudan kökteyse
    New-Item -ItemType Directory -Path "$Dest\$tag" -Force | Out-Null
    Get-ChildItem -Path $tempDir | Move-Item -Destination "$Dest\$tag" -Force
}
Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue

$versionDir = "$Dest\$tag"

# 5. Create desktop shortcut
$exe = Get-ChildItem -Path $versionDir -Include "vault.exe", "Vault.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($exe) {
    try {
        $wshell = New-Object -ComObject WScript.Shell
        $shortcut = $wshell.CreateShortcut("$env:USERPROFILE\Desktop\Vault.lnk")
        $shortcut.TargetPath = $exe.FullName
        $shortcut.WorkingDirectory = $versionDir
        $shortcut.Save()
        Write-Host "  Masaüstüne kısayol eklendi."
    } catch {
        Write-Host "  (Kısayol oluşturulamadı)"
    }
}

# 6. Add versioned directory to user PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$versionDir*") {
    $newPath = "$versionDir;$currentPath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  PATH'e eklendi: $versionDir"
    Write-Host "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
} else {
    Write-Host "  $versionDir zaten PATH'te mevcut."
}

Write-Host ""
Write-Host "  ┌======================================┐"
Write-Host "  │         KURULUM TAMAMLANDI           │"
Write-Host "  └======================================┘"
Write-Host ""
Write-Host "  Konum: $versionDir"
Write-Host "  Kullanım: vault run --desktop"
Write-Host "            vault download <URL>"
Write-Host "            vault search <sorgu>"
Write-Host ""
