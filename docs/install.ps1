#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Vault — TUI Kurulum Aracı (PowerShell)
.DESCRIPTION
    Kararlı sürüm (Release) veya test sürümü (Commit artifact) kurar.
#>

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

# ── TLS Setup ──────────────────────────────────────────────────
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor 12288
} catch {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
}

# ── ANSI + UTF-8 (Windows için zorunlu) ────────────────────────
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
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
            $cmode  = 0
            [Win32.Kernel32]::GetConsoleMode($stdOut, [ref]$cmode) | Out-Null
            [Win32.Kernel32]::SetConsoleMode($stdOut, ($cmode -bor 0x0004)) | Out-Null
        }
    } catch {}
}

# ── TUI Constants ───────────────────────────────────────────────
$ESC    = [char]27
$RESET  = "${ESC}[0m"
$BOLD   = "${ESC}[1m"
$DIM    = "${ESC}[2m"
$GREEN  = "${ESC}[32m"
$CYAN   = "${ESC}[36m"
$YELLOW = "${ESC}[33m"
$RED    = "${ESC}[31m"

$Script:IW = 48   # ││ arasındaki iç genişlik

# ── Beep ────────────────────────────────────────────────────────
function Write-Beep {
    param([string]$Pattern = "nav")
    try {
        switch ($Pattern) {
            "nav"     { [Console]::Beep(900, 60) }
            "select"  { [Console]::Beep(900, 60); Start-Sleep -Milliseconds 80; [Console]::Beep(1200, 80) }
            "error"   { [Console]::Beep(300, 150); Start-Sleep -Milliseconds 120; [Console]::Beep(200, 200); Start-Sleep -Milliseconds 120; [Console]::Beep(150, 300) }
            "success" { [Console]::Beep(600, 100); Start-Sleep -Milliseconds 80; [Console]::Beep(800, 100); Start-Sleep -Milliseconds 80; [Console]::Beep(1200, 200) }
        }
    } catch {}
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
    $padded = "  $Text".PadRight($Script:IW)
    "  │${BOLD}${CYAN}${padded}${RESET}│" | Write-Host
}

function Draw-Item {
    param([int]$Selected, [string]$Text)
    $innerWidth = $Script:IW - 4
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
        if ([string]::IsNullOrEmpty($Items[$i])) { Draw-Blank }
        elseif ($i -eq $Selected)               { Draw-Item -Selected 1 -Text $Items[$i] }
        else                                     { Draw-Item -Selected 0 -Text $Items[$i] }
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
        81  {                    return "q" }
        113 {                    return "q" }
    }
    return "other"
}

# ── GitHub API ─────────────────────────────────────────────────
$Script:REPO     = "yaso09/vault"
$Script:API_BASE = "https://api.github.com/repos/$($Script:REPO)"

function Invoke-GitHubAPI {
    param([string]$Url)
    $params = @{ Uri = $Url; UseBasicParsing = $true }
    if ($env:GITHUB_TOKEN) { $params.Headers = @{ Authorization = "Bearer $env:GITHUB_TOKEN" } }
    try { return Invoke-RestMethod @params -ErrorAction Stop } catch { return $null }
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
        $msg = if ($r.head_commit -and $r.head_commit.message) { $r.head_commit.message.Split("`n")[0] } else { "?" }
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
        $result += [PSCustomObject]@{ Name = $a.name; Size = [long]$a.size_in_bytes; Id = [long]$a.id }
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

function Format-Eta {
    param([double]$Seconds)
    if ($Seconds -le 0)   { return "" }
    if ($Seconds -lt 60)  { return "~$([int]$Seconds)s kaldı" }
    if ($Seconds -lt 3600){ return "~$([int]($Seconds/60))dk kaldı" }
    return "~$([int]($Seconds/3600))sa kaldı"
}

function Get-InstallBase { return "$env:APPDATA\Vault" }

# ── Install Progress Screen ────────────────────────────────────
#
#   ┌────────────────────────────────────────────────┐
#   │  ⚙  v1.2.3 — windows                          │
#   ├────────────────────────────────────────────────┤
#   │                                                │
#   │  ✓  [1/4]  Hedef dizin hazırlandı              │
#   │  ▶  [2/4]  İndiriliyor...                      │
#   │     [3/4]  Arşiv çıkartılıyor                  │
#   │     [4/4]  PATH & Kısayol                      │
#   │                                                │
#   └────────────────────────────────────────────────┘
#
#   ████████████████████░░░░░░░░░░░░  63%
#   26.4 MB / 41.8 MB  •  2.1 MB/s  •  ~7s kaldı

$Script:StepRows  = @()   # Her adımın console satır numarası
$Script:BarPrimed = $false # Progress bar ilk kez mi çiziliyor

function Draw-InstallScreen {
    param([string]$Title, [string[]]$Steps)

    Clear-Screen
    Draw-BoxTop
    Draw-Title -Text $Title
    Draw-Separator
    Draw-Blank

    $Script:StepRows  = @()
    $Script:BarPrimed = $false
    $n = $Steps.Length

    for ($i = 0; $i -lt $n; $i++) {
        $Script:StepRows += [Console]::CursorTop
        # "  │  ·  [x/n]  Step text                    │"
        $label  = "[$(($i+1))/$n]  $($Steps[$i])"
        $padded = ("  ${DIM}·${RESET}  " + $label).PadRight($Script:IW + 9)  # +9 ANSI offset
        "  │$padded│" | Write-Host
    }

    Draw-Blank
    Draw-BoxBottom
    Write-Host ""   # progress bar alanı (2 satır)
    Write-Host ""
}

function Set-StepStatus {
    # Adımın icon sütununu yerinde günceller (· → ▶ / ✓ / ✗)
    param([int]$Index, [string]$Status)   # Status: pending | running | done | error
    $savedLeft = [Console]::CursorLeft
    $savedTop  = [Console]::CursorTop

    [Console]::SetCursorPosition(5, $Script:StepRows[$Index])
    switch ($Status) {
        "pending" { "${DIM}·${RESET}" | Write-Host -NoNewline }
        "running" { "${CYAN}▶${RESET}" | Write-Host -NoNewline }
        "done"    { "${GREEN}✓${RESET}" | Write-Host -NoNewline }
        "error"   { "${RED}✗${RESET}"  | Write-Host -NoNewline }
    }

    [Console]::SetCursorPosition($savedLeft, $savedTop)
}

function Draw-ProgressBar {
    # Kutunun altındaki 2 satırı yerinde çizer/günceller
    param(
        [int]$Percent,           # -1 = belirsiz
        [string]$ReceivedStr,
        [string]$TotalStr,
        [string]$SpeedStr = "",
        [string]$EtaStr   = ""
    )

    $barWidth = 34

    if ($Percent -ge 0) {
        $filled  = [Math]::Floor($barWidth * $Percent / 100)
        $empty   = $barWidth - $filled
        $bar     = "${GREEN}$('█' * $filled)${DIM}$('░' * $empty)${RESET}"
        $pctStr  = "$Percent%".PadLeft(4)
    } else {
        # Belirsiz: akan animasyon
        $pos    = ([int]([DateTime]::Now.Millisecond / 80)) % $barWidth
        $chars  = @(' ') * $barWidth
        for ($k = 0; $k -lt 6; $k++) { $chars[($pos + $k) % $barWidth] = '█' }
        $bar    = "${CYAN}$($chars -join '')${RESET}"
        $pctStr = "  ···"
    }

    $line1 = "  $bar $pctStr"
    $meta  = "  ${DIM}${ReceivedStr} / ${TotalStr}${RESET}"
    if ($SpeedStr) { $meta += "  •  ${CYAN}${SpeedStr}${RESET}" }
    if ($EtaStr)   { $meta += "  ${DIM}${EtaStr}${RESET}" }

    if (-not $Script:BarPrimed) {
        # İlk çizim — kutunun hemen altında olması için
        $Script:BarPrimed = $true
        Write-Host ($line1.PadRight(72))
        Write-Host ($meta.PadRight(72))
    } else {
        # Yerinde güncelle: 2 satır yukarı çık, yeniden yaz
        "${ESC}[2A" | Write-Host -NoNewline
        Write-Host ($line1.PadRight(72))
        Write-Host ($meta.PadRight(72))
    }
}

function Invoke-Download {
    param([string]$Url, [string]$Dest, [int]$StepIndex)

    Set-StepStatus -Index $StepIndex -Status "running"

    try {
        # curl komutunu kur
        $args = @("-L", "--fail", "-o", $Dest)

        # token varsa ekle (opsiyonel)
        if (![string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
            $args += "-H"
            $args += "Authorization: Bearer $env:GITHUB_TOKEN"
        }

        $args += $Url

        & curl.exe @args

        # doğrulama
        if (Test-Path $Dest -and (Get-Item $Dest).Length -gt 0) {
            Set-StepStatus -Index $StepIndex -Status "done"
            return $true
        }

        Set-StepStatus -Index $StepIndex -Status "error"
        return $false
    }
    catch {
        Set-StepStatus -Index $StepIndex -Status "error"
        return $false
    }
}

# ── Extract (arka planda, spinner ile) ────────────────────────
function Invoke-Extract {
    param([string]$Archive, [string]$Dest, [int]$StepIndex)

    Set-StepStatus -Index $StepIndex -Status "running"

    $tmpDir = Join-Path $env:TEMP "vault-extract"
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }

    # Çıkartmayı arka plan job'ında başlat
    $job = Start-Job -ScriptBlock {
        param($src, $dst)
        Expand-Archive -Path $src -DestinationPath $dst -Force
    } -ArgumentList $Archive, $tmpDir

    # Job çalışırken spinner göster
    $spin = [char[]]@('⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏')
    $si   = 0
    $savedLeft = [Console]::CursorLeft
    $savedTop  = [Console]::CursorTop

    while ($job.State -eq "Running") {
        [Console]::SetCursorPosition(5, $Script:StepRows[$StepIndex])
        "${CYAN}$($spin[$si % $spin.Length])${RESET}" | Write-Host -NoNewline
        $si++
        Start-Sleep -Milliseconds 80
    }
    [Console]::SetCursorPosition($savedLeft, $savedTop)

    Receive-Job $job -ErrorAction SilentlyContinue | Out-Null
    $ok = ($job.State -eq "Completed")
    Remove-Job $job

    if (-not $ok) {
        Set-StepStatus -Index $StepIndex -Status "error"
        return $false
    }

    # Dosyaları hedefe taşı
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    $inner = Get-ChildItem -Directory -Path $tmpDir -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($inner) {
        Get-ChildItem -Path $inner.FullName | Move-Item -Destination $Dest -Force -ErrorAction SilentlyContinue
    } else {
        Get-ChildItem -Path $tmpDir | Move-Item -Destination $Dest -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue

    Set-StepStatus -Index $StepIndex -Status "done"
    return $true
}

# ── Install Orchestrator ────────────────────────────────────────
function Install-FromArchive {
    param([string]$Archive, [string]$VersionLabel, [string]$Platform)

    $baseDir = Get-InstallBase
    $dest    = Join-Path $baseDir $VersionLabel

    $steps = @(
        "Hedef dizin hazırlanıyor",
        "Dosyalar indiriliyor         ",   # trailing space — spinner için alan
        "Arşiv çıkartılıyor          ",
        "PATH & Kısayol güncelleniyor"
    )

    Draw-InstallScreen -Title "  ⚙  $VersionLabel — $Platform" -Steps $steps

    # ── Adım 1: Hedef dizin ──────────────────────────────
    Set-StepStatus -Index 0 -Status "running"
    Start-Sleep -Milliseconds 120    # gözle görülsün
    if (Test-Path $baseDir) { Remove-Item -Recurse -Force $baseDir -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Path $baseDir -Force | Out-Null
    Set-StepStatus -Index 0 -Status "done"

    # ── Adım 2: İndirme — Invoke-Download içinde yönetilir ──
    # (Archive zaten indirilmiş; bu fonksiyon sadece çıkartma yapıyor)
    # İndirme adımını tamamlanmış işaretle
    Set-StepStatus -Index 1 -Status "done"

    # ── Adım 3: Çıkartma ─────────────────────────────────
    $ok = Invoke-Extract -Archive $Archive -Dest $dest -StepIndex 2
    if (-not $ok) {
        Write-Beep error
        Write-Host ""
        Write-Host "  ${RED}Çıkarma başarısız.${RESET}"
        return $false
    }

    # ── Adım 4: PATH & Kısayol ────────────────────────────
    Set-StepStatus -Index 3 -Status "running"

    # PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$dest*") {
        [Environment]::SetEnvironmentVariable("Path", "$dest;$currentPath", "User")
    }

    # Kısayol
    $exe = Get-ChildItem -Path $dest -Filter "*.exe" -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -match "^[Vv]ault\.exe$" } |
           Select-Object -First 1
    if ($exe) {
        try {
            $wshell   = New-Object -ComObject WScript.Shell
            $shortcut = $wshell.CreateShortcut("$env:USERPROFILE\Desktop\Vault.lnk")
            $shortcut.TargetPath       = $exe.FullName
            $shortcut.WorkingDirectory = $dest
            $shortcut.Save()
        } catch {}
    }

    Set-StepStatus -Index 3 -Status "done"

    # ── Başarı kutusu ─────────────────────────────────────
    Write-Host ""
    Write-Host ""
    Write-Beep success
    Write-Host "  ┌──────────────────────────────────────────────┐"
    Write-Host "  │        ${GREEN}KURULUM BAŞARIYLA TAMAMLANDI${RESET}          │"
    Write-Host "  ├──────────────────────────────────────────────┤"
    Write-Host "  │  Konum  : $($dest.PadRight(35))│"
    Write-Host "  │  Kullanım: vault run --desktop               │"
    if ($exe) {
    Write-Host "  │  Kısayol: Masaüstü › Vault.lnk              │"
    }
    Write-Host "  └──────────────────────────────────────────────┘"
    Write-Host ""
    return $true
}

# ── Start-Install (akış başlatıcı) ────────────────────────────
function Start-Install {
    param(
        [string]$SourceType,
        [string]$VersionLabel,
        [string]$Platform,
        [long]$ArtifactId = 0
    )

    $archive = Join-Path $env:TEMP "vault-install.zip"
    $url     = if ($SourceType -eq "release") {
        "https://github.com/$($Script:REPO)/releases/download/$VersionLabel/${Platform}-build-artifact.zip"
    } else {
        "$($Script:API_BASE)/actions/artifacts/$ArtifactId/zip"
    }

    # İndirme ekranını hazırla
    $dlSteps = @(
        "Bağlantı kuruluyor  ",
        "Dosyalar indiriliyor",
        "Arşiv çıkartılıyor  ",
        "PATH & Kısayol      "
    )
    Draw-InstallScreen -Title "  ⚙  $VersionLabel — $Platform" -Steps $dlSteps
    Set-StepStatus -Index 0 -Status "done"   # bağlantı anında

    # İndir
    $ok = Invoke-Download -Url $url -Dest $archive -StepIndex 1
    if (-not $ok) {
        Write-Beep error
        Write-Host ""
        Write-Host "  ${RED}İndirme başarısız. URL veya token'ı kontrol edin.${RESET}"
        Start-Sleep -Milliseconds 2500
        return
    }

    if (-not (Test-Path $archive) -or (Get-Item $archive).Length -eq 0) {
        Write-Beep error
        Write-Host ""
        Write-Host "  ${RED}İndirilen dosya boş veya geçersiz.${RESET}"
        Remove-Item $archive -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 2500
        return
    }

    # Kurulum (çıkart + PATH + kısayol)
    $baseDir = Get-InstallBase
    $dest    = Join-Path $baseDir $VersionLabel

    Set-StepStatus -Index 0 -Status "done"  # bağlantı
    # adım 1 (indirme) zaten done — şimdi adım 2: çıkartma

    # Hedef hazırlık
    if (Test-Path $baseDir) { Remove-Item -Recurse -Force $baseDir -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Path $baseDir -Force | Out-Null

    # Çıkart
    $ok = Invoke-Extract -Archive $archive -Dest $dest -StepIndex 2
    Remove-Item $archive -ErrorAction SilentlyContinue
    if (-not $ok) {
        Write-Beep error
        Write-Host ""
        Write-Host "  ${RED}Çıkarma başarısız.${RESET}"
        Start-Sleep -Milliseconds 2500
        return
    }

    # PATH & Kısayol
    Set-StepStatus -Index 3 -Status "running"
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$dest*") {
        [Environment]::SetEnvironmentVariable("Path", "$dest;$currentPath", "User")
    }
    $exe = Get-ChildItem -Path $dest -Filter "*.exe" -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -match "^[Vv]ault\.exe$" } | Select-Object -First 1
    if ($exe) {
        try {
            $wshell   = New-Object -ComObject WScript.Shell
            $shortcut = $wshell.CreateShortcut("$env:USERPROFILE\Desktop\Vault.lnk")
            $shortcut.TargetPath       = $exe.FullName
            $shortcut.WorkingDirectory = $dest
            $shortcut.Save()
        } catch {}
    }
    Set-StepStatus -Index 3 -Status "done"

    # Başarı
    Write-Host ""
    Write-Host ""
    Write-Beep success
    Write-Host "  ┌──────────────────────────────────────────────┐"
    Write-Host "  │        ${GREEN}KURULUM BAŞARIYLA TAMAMLANDI${RESET}          │"
    Write-Host "  ├──────────────────────────────────────────────┤"
    Write-Host "  │  Konum   : $($dest.PadRight(34))│"
    Write-Host "  │  Kullanım: vault run --desktop               │"
    if ($exe) {
    Write-Host "  │  Kısayol : Masaüstü › Vault.lnk             │"
    }
    Write-Host "  └──────────────────────────────────────────────┘"
    Write-Host ""
    Write-Host "  Ana menüye dönmek için bir tuşa basın..."
    $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
}

# ── Flow Screens ────────────────────────────────────────────────
function Show-ReleaseFlow {
    Write-Host ""; Write-Host "  Sürümler alınıyor..."
    $releases = @(Get-Releases)
    if ($releases.Count -eq 0) {
        Write-Beep error
        Write-Host "  ${RED}Henüz bir sürüm yayınlanmamış.${RESET}"
        Start-Sleep -Milliseconds 1500; return
    }
    $display = @(); $tags = @()
    foreach ($r in $releases) { $display += "$($r.Tag)  •  $($r.Date)"; $tags += $r.Tag }

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
    $platforms = @("windows","linux","macos","apk","aab")
    $display   = @(); $detectedIdx = 0
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
            "enter" { Start-Install -SourceType "release" -VersionLabel $Tag -Platform $platforms[$selected]; return }
            { $_ -in "esc","q" } { return }
        }
    }
}

function Show-CommitFlow {
    if (-not $env:GITHUB_TOKEN) {
        Write-Host ""; Write-Host "  Workflow artifact'leri için GitHub Token gerekli."
        Write-Host "  (https://github.com/settings/tokens adresinden oluşturabilirsiniz)"; Write-Host ""
        $secure = Read-Host "  GitHub Token" -AsSecureString
        $bstr   = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $token  = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        if ([string]::IsNullOrEmpty($token)) {
            Write-Beep error; Write-Host "  ${RED}Token gerekli.${RESET}"; Start-Sleep -Milliseconds 1500; return
        }
        $env:GITHUB_TOKEN = $token
    }

    Write-Host ""; Write-Host "  Workflow run'ları alınıyor..."
    $runs = @(Get-WorkflowRuns)
    if ($runs.Count -eq 0) {
        Write-Beep error; Write-Host "  ${RED}Hiç test yapısı bulunamadı.${RESET}"; Start-Sleep -Milliseconds 1500; return
    }

    $display = @(); $data = @()
    foreach ($r in $runs) {
        $maxMsg  = $Script:IW - 4 - 9
        $msgDisp = if ($r.Message.Length -gt $maxMsg) { $r.Message.Substring(0, $maxMsg - 3) + "..." } else { $r.Message }
        $maxBr   = $Script:IW - 4 - 23
        $brDisp  = if ($r.Branch.Length -gt $maxBr)  { $r.Branch.Substring(0, $maxBr - 3)   + "..." } else { $r.Branch }
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
                $di = [Math]::Floor($selected / 2)
                Show-ArtifactFlow -RunId $data[$di].RunId -Sha $data[$di].Sha; return
            }
            { $_ -in "esc","q" } { return }
        }
    }
}

function Show-ArtifactFlow {
    param([long]$RunId, [string]$Sha)
    Write-Host ""; Write-Host "  Yapıtlar alınıyor..."
    $artifacts = @(Get-RunArtifacts -RunId $RunId)
    if ($artifacts.Count -eq 0) {
        Write-Host "  ${RED}Seçilen commit için yapı bulunamadı.${RESET}"; Start-Sleep -Milliseconds 1500; return
    }
    $display = @(); $artNames = @(); $artIds = @()
    foreach ($a in $artifacts) {
        $dn = $a.Name -replace "-build-artifact$", ""
        $display  += "$dn ($(Format-FileSize -Bytes $a.Size))"
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
    $options  = @("📦  Kararlı sürüm kur","🔧  Test sürümü kur","","❌  Çıkış")
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
        while ($selected -lt $options.Length -and [string]::IsNullOrEmpty($options[$selected])) { $selected++ }
    }
}

# ── Entry Point ─────────────────────────────────────────────────
Hide-Cursor
try { Show-MainMenu } finally { Show-Cursor }