#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Vault — TUI Kurulum Aracı (PowerShell)
.DESCRIPTION
    Kararlı sürüm (Release) veya test sürümü (Commit artifact) kurar.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ── TUI Constants ───────────────────────────────────────────────
$ESC = [char]27
$RESET = "${ESC}[0m"
$BOLD = "${ESC}[1m"
$DIM = "${ESC}[2m"
$GREEN = "${ESC}[32m"
$CYAN = "${ESC}[36m"
$YELLOW = "${ESC}[33m"
$RED = "${ESC}[31m"

$Script:IW = 48  # interior width between ││ borders

# ── TUI Primitives ──────────────────────────────────────────────
function Clear-Screen {
    "${ESC}[2J${ESC}[H" | Write-Host -NoNewline
}

function Hide-Cursor {
    "${ESC}[?25l" | Write-Host -NoNewline
}

function Show-Cursor {
    "${ESC}[?25h" | Write-Host -NoNewline
}

function Draw-BoxTop {
    "  ┌$('─' * $Script:IW)┐" | Write-Host
}

function Draw-BoxBottom {
    "  └$('─' * $Script:IW)┘" | Write-Host
}

function Draw-Separator {
    "  ├$('─' * $Script:IW)┤" | Write-Host
}

function Draw-Title {
    param([string]$Text)
    $padded = "  $Text".PadRight($Script:IW)
    "  │${BOLD}${CYAN}$padded${RESET}│" | Write-Host
}

function Draw-Blank {
    "  │$(' ' * $Script:IW)│" | Write-Host
}

function Draw-Item {
    param([int]$Selected, [string]$Text)
    $innerWidth = $Script:IW - 5
    if ($Selected -eq 1) {
        $padded = $Text.PadRight($innerWidth)
        "  │  ${GREEN}>${RESET} $padded│" | Write-Host
    } else {
        $padded = $Text.PadRight($innerWidth)
        "  │    $padded│" | Write-Host
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
        $item = $Items[$i]
        if ([string]::IsNullOrEmpty($item)) {
            Draw-Blank
        } elseif ($i -eq $Selected) {
            Draw-Item -Selected 1 -Text $item
        } else {
            Draw-Item -Selected 0 -Text $item
        }
    }

    Draw-Blank
    Draw-BoxBottom
    "$DIM  $Footer$RESET" | Write-Host
}

# ── Key Reader ─────────────────────────────────────────────────
function Read-KeyPress {
    $key = $host.UI.RawUI.ReadKey("NoEcho, IncludeKeyDown")
    # Do not let the key echo to the display
    switch ($key.VirtualKeyCode) {
        38  { return "up" }      # Up arrow
        40  { return "down" }    # Down arrow
        13  { return "enter" }   # Enter
        27  { return "esc" }     # Escape
        81  { return "q" }       # Q
        113 { return "q" }       # q
    }
    return "other"
}

# ── GitHub API ─────────────────────────────────────────────────
$Script:REPO = "yaso09/vault"
$Script:API_BASE = "https://api.github.com/repos/$($Script:REPO)"

function Invoke-GitHubAPI {
    param([string]$Url)
    $params = @{
        Uri = $Url
        UseBasicParsing = $true
    }
    if ($env:GITHUB_TOKEN) {
        $params.Headers = @{ Authorization = "Bearer $env:GITHUB_TOKEN" }
    }
    try {
        return Invoke-RestMethod @params
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
            Date = if ($r.published_at) { $r.published_at.Substring(0,10) } else { "?" }
        }
    }
    return $result
}

function Get-WorkflowRuns {
    $data = Invoke-GitHubAPI -Url "$Script:API_BASE/actions/workflows/release.yml/runs?per_page=10&status=success"
    if (-not $data -or -not $data.workflow_runs) { return @() }
    $result = @()
    foreach ($r in $data.workflow_runs) {
        $msg = if ($r.head_commit.message) { $r.head_commit.message.Split("`n")[0] } else { "?" }
        if ($msg.Length -gt 50) { $msg = $msg.Substring(0, 50) }
        $sha = if ($r.head_sha.Length -ge 7) { $r.head_sha.Substring(0, 7) } else { $r.head_sha }
        $result += [PSCustomObject]@{
            Sha     = $sha
            Message = $msg
            Branch  = $r.head_branch
            Date    = if ($r.created_at) { $r.created_at.Substring(0,10) } else { "?" }
            RunId   = $r.id
        }
    }
    return $result
}

function Get-Artifacts {
    param([long]$RunId)
    $data = Invoke-GitHubAPI -Url "$Script:API_BASE/actions/runs/$RunId/artifacts"
    if (-not $data -or -not $data.artifacts) { return @() }
    $result = @()
    foreach ($a in $data.artifacts) {
        $result += [PSCustomObject]@{
            Name = $a.name
            Size = $a.size_in_bytes
            Id   = $a.id
        }
    }
    return $result
}

# ── Helpers ────────────────────────────────────────────────────
function Get-DetectedPlatform {
    return "windows"
}

function Format-FileSize {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N1} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N1} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Get-InstallBase {
    return "$env:APPDATA\Vault"
}

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
    $dest = "$baseDir\$VersionLabel"

    Write-Host "  [1/4] Hedef hazırlanıyor..."
    if (Test-Path $baseDir) {
        Remove-Item -Recurse -Force $baseDir -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $baseDir -Force | Out-Null

    Write-Host "  [2/4] Çıkartılıyor..."
    $tmpDir = "$env:TEMP\vault-extract"
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
    try {
        Expand-Archive -Path $Archive -DestinationPath $tmpDir -Force
    } catch {
        Write-Host "  ${RED}Çıkarma başarısız: $_${RESET}"
        return $false
    }

    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    $inner = Get-ChildItem -Directory -Path $tmpDir | Select-Object -First 1
    if ($inner) {
        Move-Item -Path $inner.FullName\* -Destination $dest -Force -ErrorAction SilentlyContinue
    } else {
        Get-ChildItem -Path $tmpDir | Move-Item -Destination $dest -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue

    Write-Host "  [3/4] PATH güncelleniyor..."
    Update-UserPath -Path $dest

    Write-Host "  [4/4] Kısayol oluşturuluyor..."
    $exe = Get-ChildItem -Path $dest -Include "vault.exe", "Vault.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exe) {
        try {
            $wshell = New-Object -ComObject WScript.Shell
            $shortcut = $wshell.CreateShortcut("$env:USERPROFILE\Desktop\Vault.lnk")
            $shortcut.TargetPath = $exe.FullName
            $shortcut.WorkingDirectory = $dest
            $shortcut.Save()
            Write-Host "  Masaüstü kısayolu: $env:USERPROFILE\Desktop\Vault.lnk"
        } catch {
            Write-Host "  ${DIM}(Kısayol oluşturulamadı)${RESET}"
        }
    }

    Write-Host ""
    Write-Host "  ┌======================================┐"
    Write-Host "  │         KURULUM TAMAMLANDI           │"
    Write-Host "  └======================================┘"
    Write-Host ""
    Write-Host "  Konum: $dest"
    Write-Host "  Kullanım: vault run --desktop"
    Write-Host ""
    return $true
}

function Update-UserPath {
    param([string]$Path)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$Path*") {
        $newPath = "$Path;$currentPath"
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "  PATH'e eklendi: $Path"
        Write-Host "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
    } else {
        Write-Host "  $Path zaten PATH'te mevcut."
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

    $url = ""
    $archive = "$env:TEMP\vault-install.zip"

    Write-Host ""
    Draw-BoxTop
    "  │${BOLD}$('  ' + $VersionLabel + ' Kuruluyor...').PadRight($Script:IW)${RESET}│" | Write-Host
    Draw-BoxBottom
    Write-Host ""

    if ($SourceType -eq "release") {
        $url = "https://github.com/$($Script:REPO)/releases/download/$VersionLabel/${Platform}-build-artifact.zip"
    } else {
        $url = "$($Script:API_BASE)/actions/artifacts/$ArtifactId/zip"
        if (-not $env:GITHUB_TOKEN) {
            Write-Host ""
            Write-Host "  ${YELLOW}Not: Workflow artifact'leri GitHub yetkilendirmesi gerektirebilir.${RESET}"
            Write-Host "  ${YELLOW}Hata alırsanız:${RESET}"
            Write-Host "  ${YELLOW}  `$env:GITHUB_TOKEN=ghp_... ; & docs\install.ps1${RESET}"
            Write-Host ""
        }
    }

    $ok = Invoke-Download -Url $url -Dest $archive
    if (-not $ok) {
        Write-Host "  ${RED}İndirme başarısız.${RESET}"
        Remove-Item $archive -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        return
    }

    if (-not (Test-Path $archive) -or (Get-Item $archive).Length -eq 0) {
        Write-Host "  ${RED}İndirilen dosya boş veya geçersiz.${RESET}"
        Remove-Item $archive -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        return
    }

    Install-Artifact -Archive $archive -VersionLabel $VersionLabel

    Write-Host ""
    Write-Host "  Ana menüye dönmek için bir tuşa basın..."
    $host.UI.RawUI.ReadKey("NoEcho, IncludeKeyDown") | Out-Null
}

function Show-ReleaseFlow {
    Write-Host ""
    Write-Host "  Sürümler alınıyor..."
    $releases = Get-Releases
    if ($releases.Count -eq 0) {
        Write-Host "  ${RED}Henüz bir sürüm yayınlanmamış.${RESET}"
        Start-Sleep -Seconds 1.5
        return
    }

    $display = @()
    $tags = @()
    foreach ($r in $releases) {
        $display += "$($r.Tag)  •  $($r.Date)"
        $tags += $r.Tag
    }

    $selected = 0
    while ($true) {
        Render-Menu -Items $display -Selected $selected -Title "📦  Kararlı Sürüm Seçin" `
            -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        $key = Read-KeyPress
        switch ($key) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                Show-PlatformFlow -Tag $tags[$selected]
                return
            }
            "esc"   { return }
        }
    }
}

function Show-PlatformFlow {
    param([string]$Tag)

    $detected = Get-DetectedPlatform
    $platforms = @("windows", "linux", "macos", "apk", "aab")
    $display = @()
    $detectedIdx = 0

    for ($i = 0; $i -lt $platforms.Length; $i++) {
        $p = $platforms[$i]
        if ($p -eq $detected) {
            $display += "$p (otomatik tespit)"
            $detectedIdx = $i
        } elseif ($p -eq "apk") {
            $display += "$p (Android APK)"
        } elseif ($p -eq "aab") {
            $display += "$p (Android AAB)"
        } else {
            $display += "$p"
        }
    }

    $selected = $detectedIdx
    while ($true) {
        Render-Menu -Items $display -Selected $selected -Title "Platform Seçin — $Tag" `
            -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        $key = Read-KeyPress
        switch ($key) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                Start-Install -SourceType "release" -VersionLabel $Tag -Platform $platforms[$selected]
                return
            }
            "esc"   { return }
        }
    }
}

function Show-CommitFlow {
    Write-Host ""
    Write-Host "  Workflow run'ları alınıyor..."
    $runs = Get-WorkflowRuns
    if ($runs.Count -eq 0) {
        Write-Host "  ${RED}Hiç test yapısı bulunamadı.${RESET}"
        Start-Sleep -Seconds 1.5
        return
    }

    $display = @()
    $data = @()
    foreach ($r in $runs) {
        $display += "$($r.Sha)  $($r.Message)"
        $display += "   branch: $($r.Branch)  $($r.Date)"
        $data += [PSCustomObject]@{ RunId = $r.RunId; Sha = $r.Sha }
    }

    $selected = 0
    while ($true) {
        Render-Menu -Items $display -Selected $selected -Title "🔧  Test Sürümü Seçin" `
            -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        $key = Read-KeyPress
        switch ($key) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                Show-ArtifactFlow -RunId $data[$selected].RunId -Sha $data[$selected].Sha
                return
            }
            "esc"   { return }
        }
    }
}

function Show-ArtifactFlow {
    param([long]$RunId, [string]$Sha)

    Write-Host ""
    Write-Host "  Yapıtlar alınıyor..."
    $artifacts = Get-Artifacts -RunId $RunId
    if ($artifacts.Count -eq 0) {
        Write-Host "  ${RED}Seçilen commit için yapı bulunamadı.${RESET}"
        Start-Sleep -Seconds 1.5
        return
    }

    $display = @()
    $artNames = @()
    $artIds = @()
    foreach ($a in $artifacts) {
        $displayName = $a.Name -replace "-build-artifact", ""
        $display += "$displayName ($(Format-FileSize -Bytes $a.Size))"
        $artNames += $a.Name
        $artIds += $a.Id
    }

    $selected = 0
    while ($true) {
        Render-Menu -Items $display -Selected $selected -Title "Yapı Seçin — $Sha" `
            -Footer "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        $key = Read-KeyPress
        switch ($key) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($display.Length - 1)) { $selected++ } }
            "enter" {
                $platform = $artNames[$selected] -replace "-build-artifact", ""
                Start-Install -SourceType "artifact" -VersionLabel $Sha `
                    -Platform $platform -ArtifactId $artIds[$selected]
                return
            }
            "esc"   { return }
        }
    }
}

# ── Main Menu ──────────────────────────────────────────────────
function Show-MainMenu {
    $options = @(
        "📦  Kararlı sürüm kur"
        "🔧  Test sürümü kur"
        ""
        "❌  Çıkış"
    )
    $selected = 0

    while ($true) {
        Render-Menu -Items $options -Selected $selected -Title "VAULT KURULUM — yaso09/vault" `
            -Footer "↑/↓: Gezin  Enter: Seç  Q: Çıkış"

        $key = Read-KeyPress
        switch ($key) {
            "up"    { if ($selected -gt 0) { $selected-- } }
            "down"  { if ($selected -lt ($options.Length - 1)) { $selected++ } }
            "enter" {
                switch ($selected) {
                    0 { Show-ReleaseFlow }
                    1 { Show-CommitFlow }
                    3 { Clear-Screen; Show-Cursor; exit 0 }
                }
            }
            "q" { Clear-Screen; Show-Cursor; exit 0 }
        }

        # Skip empty lines
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
