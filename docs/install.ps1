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

# 4. Extract
Write-Host "  [4/4] $Dest klasörüne çıkartılıyor..."
Expand-Archive -Path $archive -DestinationPath $Dest -Force
Remove-Item -Force $archive -ErrorAction SilentlyContinue

# 5. Create desktop shortcut
$exe = Get-ChildItem -Path "$Dest" -Include "vault.exe", "Vault.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($exe) {
    try {
        $wshell = New-Object -ComObject WScript.Shell
        $shortcut = $wshell.CreateShortcut("$env:USERPROFILE\Desktop\Vault.lnk")
        $shortcut.TargetPath = $exe.FullName
        $shortcut.WorkingDirectory = $Dest
        $shortcut.Save()
        Write-Host "  Masaüstüne kısayol eklendi."
    } catch {
        Write-Host "  (Kısayol oluşturulamadı)"
    }
}

# 6. Add to user PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$Dest*") {
    $newPath = "$Dest;$currentPath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  PATH'e eklendi: $Dest"
    Write-Host "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
} else {
    Write-Host "  $Dest zaten PATH'te mevcut."
}

Write-Host ""
Write-Host "  ┌======================================┐"
Write-Host "  │         KURULUM TAMAMLANDI           │"
Write-Host "  └======================================┘"
Write-Host ""
Write-Host "  Konum: $Dest"
Write-Host "  Kullanım: vault run --desktop"
Write-Host "            vault download <URL>"
Write-Host "            vault search <sorgu>"
Write-Host ""
