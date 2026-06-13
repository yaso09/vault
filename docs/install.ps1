#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Vault — TUI Kurulum Aracı (PowerShell)
.DESCRIPTION
    Kararlı sürüm (Release) veya test sürümü (Commit artifact) kurar.
#>

$ErrorActionPreference = "Continue"   # Stop yerine Continue — API hatalarında script ölmez
$ProgressPreference    = "SilentlyContinue"

# ── ANSI + UTF-8 (Windows için zorunlu) ────────────────────────
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    try {
        # ANSI escape işleme
        $mode = [Console]::OutputEncoding
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $null = [System.Runtime.InteropServices.RuntimeInformation]  # suppress unused
        # VT100 / ANSI modunu etkinleştir (Windows 10 1903+)
        $kernel32 = Add-Type -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
[DllImport("kernel32.dll", SetLastError = true)]
public static extern IntPtr GetStdHandle(int nStdHandle);
'@ -Name "Kernel32" -Namespace "Win32" -PassThru -ErrorAction SilentlyContinue
        if ($kernel32) {
            $stdOut = [Win32.Kernel32]::GetStdHandle(-11)
            $consoleMode = 0
            [Win32.Kernel32]::GetConsoleMode($stdOut, [ref]$consoleMode) | Out-Null
            [Win32.Kernel32]::SetConsoleMode($stdOut, ($consoleMode -bor 0x0004)) | Out-Null
        }
    } catch { <# ANSI zaten açıksa veya desteklenmiyorsa sessizce geç #> }
}

# ── TUI Constants ───────────────────────────────────────────────
$ESC    = [char]27
$RESET  = "${ESC}[0m"
$BOLD   = "${ESC}[1m"
$DIM    = "${ESC}[2m"
$GREEN  = "${ESC}[32m"
$CYAN   = "${ESC}[36m"
$RED    = "${ESC}[31m"

$Script:IW = 48  # ││ arasındaki iç genişlik

# ── Retro Beep ─────────────────────────────────────────────────
function Write-Beep {
    param([string]$Pattern = "nav")
    try {
        switch ($Pattern) {
            "nav"     { [Console]::Beep(900, 60) }
            "select"  { [Console]::Beep(900, 60); Start-Sleep -Milliseconds 80; [Console]::Beep(1200, 80) }
            "error"   { [Console]::Beep(300, 150); Start-Sleep -Milliseconds 120; [Console]::Beep(200, 200); Start-Sleep -Milliseconds 120; [Console]::Beep(150, 300) }
            "success" { [Console]::Beep(600, 100); Start-Sleep -Milliseconds 80; [Console]::Beep(800, 100); Start-Sleep -Milliseconds 80; [Console]::Beep(1200, 200) }
        }
    } catch { <# Desteklenmeyen ortamlarda sessizce geç #> }
}

# ── TUI Primitives ──────────────────────────────────────────────
function Clear-Screen  { "${ESC}[2J${ESC}[H" | Write-Host -NoNewline }
function Hide-Cursor   { "${ESC}[?25l"        | Write-Host -NoNewline }
function Show-Cursor   { "${ESC}[?25h"        | Write-Host -NoNewline }

function Draw-BoxTop    { "  ┌$('─' * $Script:IW)┐" | Write-Host }
function Draw-BoxBottom { "  └$('─' * $Script:IW)┘" | Write-Host }
function Draw-Separator { "  ├$('─' * $Script:IW)┤" | Write-Host }
function Draw-Blank     { "  │$(' ' * $Script:IW)│" | Write-Host }

function Draw-Title {
    param([string]$Text)
    # Önce düz metin olarak doldur, sonra renk ekle — ANSI karakter sayısını bozmamak için
    $padded = "  $Text".PadRight($Script:IW)
    "  │${BOLD}${CYAN}${padded}${RESET}│" | Write-Host
}

function Draw-Item {
    param([int]$Selected, [string]$Text)
    $innerWidth = $Script:IW - 4
    # Düz metin doldur, ANSI sonra ekle
    $padded = $Text.PadRight($innerWidth)
    if ($Selected -eq 1) {
        "  │  ${GREEN}>${RESET} ${padded}│" | Write-Host
    } else {
        "  │    ${padded}│" | Write-Host
    }
}

# ── Menu Renderer ──────────────────────────────────────────────
function Render-Menu {
    param(
        [string[]]$Items,
        [int]$Selected,
        [string]$Title,
        [string]$Footer = "↑/↓: Gezin  Enter: Seç  Q: Çıkış"
    )

    Clear-Screen
    Draw-BoxTop
    Draw-Title -Text $Title
    Draw-Separator
    Draw-Blank

    for ($i = 0; $i -lt $Items.Length; $i++) {
        if ([string]::IsNullOrEmpty($Items[$i])) {
            Draw-Blank
        } elseif ($i -eq $Selected) {
            Draw-Item -Selected 1 -Text $Items[$i]
        } else {
            Draw-Item -Selected 0 -Text $Items[$i]
        }
    }

    Draw-Blank
    Draw-BoxBottom
    "${DIM}  ${Footer}${RESET}" | Write-Host
}

# ── Key Reader ─────────────────────────────────────────────────
function Read-KeyPress {
    $key = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    switch ($key.VirtualKeyCode) {
        38  { Write-Beep nav;    return "up" }
        40  { Write-Beep nav;    return "down" }
        13  { Write-Beep select; return "enter" }
        27  {                    return "esc" }
        81  {                    return "q" }   # Q
        113 {                    return "q" }   # q
    }
    return "other"
}

# ── GitHub API ─────────────────────────────────────────────────
$Script:REPO     = "yaso09/vault"
$Script:API_BASE = "https://api.github.com/repos/$($Script:REPO)"

function Invoke-GitHubAPI {
    param([string]$Url)
    $params = @{ Uri = $Url; UseBasicParsing = $true }
    if ($env:GITHUB_TOKEN) {
        $params.Headers = @{ Authorization = "Bearer $env:GITHUB_TOKEN" }
    }
    try {
        return Invoke-RestMethod @params -ErrorAction Stop
    } catch {
        return $null
    }
}

function Get-Releases {
    $data = Invoke-GitHubAPI -Url "$Script:API_BASE/releases?per_page=10"
    if (-not $data) { return @() }
    $result = @()
    foreach ($r in $data) {
        $result += [PSCustomObject]@{
            Tag  = $r.tag_name
            Date = if ($r.published_at -and $r.published_at.Length -ge 10) { $r.published_at.Substring(0,10) } else { "?" }
        }
    }
    return $result
}

function Get-WorkflowRuns {
    $data = Invoke-GitHubAPI -Url "$Script:API_BASE/actions/workflows/release.yml/runs?per_page=10&status=success"
    if (-not $data -or -not $data.workflow_runs) { return @() }
    $result = @()
    foreach ($r in $data.workflow_runs) {
        $msg = if ($r.head_commit -and $r.head_commit.message) {
            $r.head_commit.message.Split("`n")[0]
        } else { "?" }
        if ($msg.Length -gt 50) { $msg = $msg.Substring(0, 50) }
        $sha = if ($r.head_sha.Length -ge 7) { $r.head_sha.Substring(0, 7) } else { $r.head_sha }
        $result += [PSCustomObject]@{
            Sha     = $sha
            Message = $msg
            Branch  = $r.head_branch
            Date    = if ($r.created_at -and $r.created_at.Length -ge 10) { $r.created_at.Substring(0,10) } else { "?" }
            RunId   = [long]$r.id
        }
    }
    return $result
}

function Get-RunArtifacts {
    param([long]$RunId)
    $data = Invoke-GitHubAPI -Url "$Script:API_BASE/actions/runs/$RunId/artifacts"
    if (-not $data -or -not $data.artifacts) { return @() }
    $result = @()
    foreach ($a in $data.artifacts) {
        $result += [PSCustomObject]@{
            Name = $a.name
            Size = [long]$a.size_in_bytes
            Id   = [long]$a.id
        }
    }
    return $result
}

# ── Helpers ────────────────────────────────────────────────────
function Format-FileSize {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N1} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N1} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Get-InstallBase { return "$env:APPDATA\Vault" }

# ── Download & Install ─────────────────────────────────────────
function Invoke-Download {
    param([string]$Url, [string]$Dest)
    Write-Host "  İndiriliyor..."
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add("User-Agent", "Vault-Installer")
        if ($env:GITHUB_TOKEN) {
            $wc.Headers.Add("Authorization", "Bearer $env:GITHUB_TOKEN")
        }
        $wc.DownloadFile($Url, $Dest)
        return $true
    } catch {
        return $false
    }
}

function Install-Artifact {
    param([string]$Archive, [string]$VersionLabel)

    $baseDir = Get-InstallBase
    $dest    = Join-Path $baseDir $VersionLabel

    Write-Host "  [1/4] Hedef hazırlanıyor..."
    if (Test-Path $baseDir) {
        Remove-Item -Recurse -Force $baseDir -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $baseDir -Force | Out-Null

    Write-Host "  [2/4] Çıkartılıyor..."
    $tmpDir = Join-Path $env:TEMP "vault-extract"
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
    try {
        Expand-Archive -Path $Archive -DestinationPath $tmpDir -Force -ErrorAction Stop
    } catch {
        Write-Beep error
        Write-Host "  ${RED}Çıkarma başarısız: $_${RESET}"
        return $false
    }

    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    $inner = Get-ChildItem -Directory -Path $tmpDir -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($inner) {
        # Wildcard'lı Join-Path yerine güvenli Get-ChildItem | Move-Item
        Get-ChildItem -Path $inner.FullName | Move-Item -Destination $dest -Force -ErrorAction SilentlyContinue
    } else {
        Get-ChildItem -Path $tmpDir | Move-Item -Destination $dest -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue

    Write-Host "  [3/4] PATH güncelleniyor..."
    Update-UserPath -NewPath $dest

    Write-Host "  [4/4] Kısayol oluşturuluyor..."
    $exe = Get-ChildItem -Path $dest -Filter "*.exe" -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -match "^[Vv]ault\.exe$" } |
           Select-Object -First 1
    if ($exe) {
        try {
            $wshell   = New-Object -ComObject WScript.Shell
            $shortcut = $wshell.CreateShortcut("$env:USERPROFILE\Desktop\Vault.lnk")
            $shortcut.TargetPath      = $exe.FullName
            $shortcut.WorkingDirectory = $dest
            $shortcut.Save()
            Write-Host "  Masaüstü kısayolu: $env:USERPROFILE\Desktop\Vault.lnk"
        } catch {
            Write-Host "  ${DIM}(Kısayol oluşturulamadı)${RESET}"
        }
    }

    Write-Host ""
    Write-Host "  ┌──────────────────────────────────────┐"
    Write-Host "  │         KURULUM TAMAMLANDI           │"
    Write-Host "  └──────────────────────────────────────┘"
    Write-Beep success
    Write-Host ""
    Write-Host "  Konum: $dest"
    Write-Host "  Kullanım: vault run --desktop"
    Write-Host ""
    return $true
}

function Update-UserPath {
    param([string]$NewPath)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$NewPath*") {
        [Environment]::SetEnvironmentVariable("Path", "$NewPath;$currentPath", "User")
        Write-Host "  PATH'e eklendi: $NewPath"
        Write-Host "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
    } else {
        Write-Host "  $NewPath zaten PATH'te mevcut."
    }
}

# ── Flow Screens ────────────────────────────────────────────────
function Start-Install {
    param(
        [string]$SourceType,
        [string]$VersionLabel,
        [string]$Platform,
        [long]$ArtifactId = 0
    )

    $archive = Join-Path $env:TEMP "vault-install.zip"

    Write-Host ""
    Draw-BoxTop
    # Düzeltildi: PadRight önce uygulanır, sonra ANSI eklenir
    $titleText = ("  $VersionLabel Kuruluyor...").PadRight($Script:IW)
    "  │${BOLD}${titleText}${RESET}│" | Write-Host
    Draw-BoxBottom
    Write-Host ""

    $url = if ($SourceType -eq "release") {
        "https://github.com/$($Script:REPO)/releases/download/$VersionLabel/${Platform}-build-artifact.zip"
    } else {
        "$($Script:API_BASE)/actions/artifacts/$ArtifactId/zip"
    }

    $ok = Invoke-Download -Url $url -Dest $archive
    if (-not $ok) {
        Write-Beep error
        Write-Host "  ${RED}İndirme başarısız.${RESET}"
        Remove-Item $archive -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 2000
        return
    }

    if (-not (Test-Path $archive) -or (Get-Item $archive).Length -eq 0) {
        Write-Beep error
        Write-Host "  ${RED}İndirilen dosya boş veya geçersiz.${RESET}"
        Remove-Item $archive -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 2000
        return
    }

    Install-Artifact -Archive $archive -VersionLabel $VersionLabel
    Remove-Item $archive -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "  Ana menüye dönmek için bir tuşa basın..."
    $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
}

function Show-ReleaseFlow {
    Write-Host ""
    Write-Host "  Sürümler alınıyor..."
    $releases = @(Get-Releases)
    if ($releases.Count -eq 0) {
        Write-Beep error
        Write-Host "  ${RED}Henüz bir sürüm yayınlanmamış.${RESET}"
        Start-Sleep -Milliseconds 1500
        return
    }

    $display = @()
    $tags    = @()
    foreach ($r in $releases) {
        $display += "$($r.Tag)  •  $($r.Date)"
        $tags    += $r.Tag
    }

    $selected = 0
    while ($true) {
        Render-Menu -Items $display -Selected $selected `
            -Title "📦  Kararlı Sürüm Seçin" -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        switch (Read-KeyPress) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" { Show-PlatformFlow -Tag $tags[$selected]; return }
            { $_ -in "esc","q" } { return }
        }
    }
}

function Show-PlatformFlow {
    param([string]$Tag)

    $platforms   = @("windows","linux","macos","apk","aab")
    $display     = @()
    $detectedIdx = 0

    for ($i = 0; $i -lt $platforms.Length; $i++) {
        switch ($platforms[$i]) {
            "windows" { $display += "windows (otomatik tespit)"; $detectedIdx = $i }
            "apk"     { $display += "apk (Android APK)" }
            "aab"     { $display += "aab (Android AAB)" }
            default   { $display += $platforms[$i] }
        }
    }

    $selected = $detectedIdx
    while ($true) {
        Render-Menu -Items $display -Selected $selected `
            -Title "Platform Seçin — $Tag" -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        switch (Read-KeyPress) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                Start-Install -SourceType "release" -VersionLabel $Tag -Platform $platforms[$selected]
                return
            }
            { $_ -in "esc","q" } { return }
        }
    }
}

function Show-CommitFlow {
    if (-not $env:GITHUB_TOKEN) {
        Write-Host ""
        Write-Host "  Workflow artifact'leri için GitHub Token gerekli."
        Write-Host "  (https://github.com/settings/tokens adresinden oluşturabilirsiniz)"
        Write-Host ""
        # SecureString olarak al, düz metin terminalde görünmez
        $secure = Read-Host "  GitHub Token" -AsSecureString
        $bstr   = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $token  = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        if ([string]::IsNullOrEmpty($token)) {
            Write-Beep error
            Write-Host "  ${RED}Token gerekli. Ana menüye dönülüyor.${RESET}"
            Start-Sleep -Milliseconds 1500
            return
        }
        $env:GITHUB_TOKEN = $token
    }

    Write-Host ""
    Write-Host "  Workflow run'ları alınıyor..."
    $runs = @(Get-WorkflowRuns)
    if ($runs.Count -eq 0) {
        Write-Beep error
        Write-Host "  ${RED}Hiç test yapısı bulunamadı.${RESET}"
        Start-Sleep -Milliseconds 1500
        return
    }

    $display = @()
    $data    = @()   # Her run için tek kayıt — display'deki çift satırla eşleşme için [Math]::Floor kullanılır
    foreach ($r in $runs) {
        $maxMsg  = $Script:IW - 4 - 9   # SHA(7) + 2 boşluk
        $msgDisp = if ($r.Message.Length -gt $maxMsg) { $r.Message.Substring(0, $maxMsg - 3) + "..." } else { $r.Message }

        $maxBr  = $Script:IW - 4 - 23  # "   branch: "(11) + date(10) + boşluk(2)
        $brDisp = if ($r.Branch.Length -gt $maxBr) { $r.Branch.Substring(0, $maxBr - 3) + "..." } else { $r.Branch }

        $display += "$($r.Sha)  $msgDisp"
        $display += "   branch: $brDisp  $($r.Date)"
        $data    += [PSCustomObject]@{ RunId = $r.RunId; Sha = $r.Sha }
    }

    $selected = 0
    while ($true) {
        Render-Menu -Items $display -Selected $selected `
            -Title "🔧  Test Sürümü Seçin" -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        switch (Read-KeyPress) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                # Her run 2 satır kaplar; Math::Floor ile doğru data index'i bulunur
                $dataIdx = [Math]::Floor($selected / 2)
                Show-ArtifactFlow -RunId $data[$dataIdx].RunId -Sha $data[$dataIdx].Sha
                return
            }
            { $_ -in "esc","q" } { return }
        }
    }
}

function Show-ArtifactFlow {
    param([long]$RunId, [string]$Sha)

    Write-Host ""
    Write-Host "  Yapıtlar alınıyor..."
    $artifacts = @(Get-RunArtifacts -RunId $RunId)
    if ($artifacts.Count -eq 0) {
        Write-Host "  ${RED}Seçilen commit için yapı bulunamadı.${RESET}"
        Start-Sleep -Milliseconds 1500
        return
    }

    $display  = @()
    $artNames = @()
    $artIds   = @()
    foreach ($a in $artifacts) {
        $displayName = $a.Name -replace "-build-artifact$", ""
        $display  += "$displayName ($(Format-FileSize -Bytes $a.Size))"
        $artNames += $a.Name
        $artIds   += $a.Id
    }

    $selected = 0
    while ($true) {
        Render-Menu -Items $display -Selected $selected `
            -Title "Yapı Seçin — $Sha" -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        switch (Read-KeyPress) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                $platform = $artNames[$selected] -replace "-build-artifact$", ""
                Start-Install -SourceType "artifact" -VersionLabel $Sha `
                    -Platform $platform -ArtifactId $artIds[$selected]
                return
            }
            { $_ -in "esc","q" } { return }
        }
    }
}

# ── Main Menu ──────────────────────────────────────────────────
function Show-MainMenu {
    $options  = @(
        "📦  Kararlı sürüm kur"
        "🔧  Test sürümü kur"
        ""
        "❌  Çıkış"
    )
    $selected = 0

    while ($true) {
        Render-Menu -Items $options -Selected $selected `
            -Title "VAULT KURULUM — yaso09/vault" -Footer "↑/↓: Gezin  Enter: Seç  Q: Çıkış"

        switch (Read-KeyPress) {
            "up"   { if ($selected -gt 0) { $selected-- } }
            "down" { if ($selected -lt ($options.Length - 1)) { $selected++ } }
            "enter" {
                switch ($selected) {
                    0 { Show-ReleaseFlow }
                    1 { Show-CommitFlow }
                    3 { Clear-Screen; Show-Cursor; exit 0 }
                }
            }
            { $_ -in "q","esc" } { Clear-Screen; Show-Cursor; exit 0 }
        }

        # Boş satırları atla
        while ($selected -lt $options.Length -and [string]::IsNullOrEmpty($options[$selected])) {
            $selected++
        }
    }
}

# ── Entry Point ─────────────────────────────────────────────────
Hide-Cursor
try {
    Show-MainMenu
} finally {
    Show-Cursor
}