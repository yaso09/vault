#!/usr/bin/env pwsh

$ESC = [char]27
$RST = "${ESC}[0m"
$B   = "${ESC}[1m"
$G   = "${ESC}[32m"
$C   = "${ESC}[36m"
$R   = "${ESC}[31m"
$Y   = "${ESC}[33m"
$D   = "${ESC}[2m"

$Script:W = 30
$Script:H = 14

function Clear-Screen { "${ESC}[2J${ESC}[H" | Write-Host -NoNewline }

function Init {
    $Script:px = [Math]::Floor($Script:W/2)
    $Script:py = $Script:H - 3
    $Script:score = 0
    $Script:lives = 3
    $Script:bx = -1
    $Script:by = -1
    $Script:frame = 0
    $Script:enemies = @()
    Spawn-Wave
}

function Spawn-Wave {
    $Script:enemies = @()
    for ($i = 0; $i -lt 6; $i++) {
        $Script:enemies += [PSCustomObject]@{ X = $i*4+3; Y = 2 }
    }
}

function Get-Hearts {
    $out = ""
    for ($i = 0; $i -lt $Script:lives; $i++) { $out += "${R}❤${RST}" }
    for ($i = $Script:lives; $i -lt 3; $i++) { $out += "${D}·${RST}" }
    return $out
}

function Render {
    $border = "─" * $Script:W
    Clear-Screen

    "  ┌$border┐" | Write-Host
    "  │${B}Score:${RST} $($Script:score.ToString('00'))  $(Get-Hearts)$(' ' * ($Script:W-10))│" | Write-Host
    "  │$(' ' * $Script:W)│" | Write-Host

    for ($y = 2; $y -le $Script:H-2; $y++) {
        $line = "  │"
        for ($x = 1; $x -le $Script:W; $x++) {
            $ch = " "
            if ($Script:bx -eq $x -and $Script:by -eq $y) { $ch = "${Y}│${RST}" }
            foreach ($e in $Script:enemies) {
                if ($e.X -eq $x -and $e.Y -eq $y) { $ch = "${R}▼${RST}"; break }
            }
            if ($Script:px -eq $x -and $Script:py -eq $y) { $ch = "${G}▲${RST}" }
            $line += $ch
        }
        "$line│" | Write-Host
    }

    "  │$(' ' * $Script:W)│" | Write-Host
    "  └$border┘" | Write-Host
    "  ${D}← → hareket  BOŞLUK ateş  Q çıkış${RST}" | Write-Host
}

function Play-Beep {
    param([int]$Freq, [int]$Dur)
    $null = [System.Threading.ThreadPool]::QueueUserWorkItem({
        try { [Console]::Beep($Freq, $Dur) } catch {}
    })
}

function Show-StartMenu {
    $selected = 0
    $options = @("  O Y U N A  B A Ş L A  ", "      Ç I K I Ş        ")
    while ($true) {
        Clear-Screen
        $border = "─" * $Script:W
        "  ┌$border┐" | Write-Host
        "  │$(' ' * $Script:W)│" | Write-Host
        "  │      ${B}${G}S P A C E  I N V A D E R S${RST}      │" | Write-Host
        "  │$(' ' * $Script:W)│" | Write-Host
        "  ├$border┤" | Write-Host
        "  │$(' ' * $Script:W)│" | Write-Host
        
        for ($i = 0; $i -lt $options.Length; $i++) {
            $opt = $options[$i]
            $pad = [Math]::Floor(($Script:W - $opt.Length)/2)
            $padded = " " * $pad + $opt + " " * ($Script:W - $opt.Length - $pad)
            if ($i -eq $selected) {
                "  │${B}${Y}> $padded${RST}│" | Write-Host
            } else {
                "  │  $padded  │" | Write-Host
            }
        }
        
        "  │$(' ' * $Script:W)│" | Write-Host
        "  └$border┘" | Write-Host
        "  ${D}↑/↓: Gezin  Enter: Seç  Q: Çıkış${RST}" | Write-Host
        
        $key = $host.UI.RawUI.ReadKey("NoEcho, IncludeKeyDown")
        switch ($key.VirtualKeyCode) {
            38 { if ($selected -gt 0) { $selected-- } } # Up
            40 { if ($selected -lt ($options.Length - 1)) { $selected++ } } # Down
            13 {
                if ($selected -eq 0) { return $true } # Start
                if ($selected -eq 1) { return $false } # Exit
            }
            81 { return $false } # Q
        }
    }
}

function Read-Input {
    if (-not [Console]::KeyAvailable) { return $true }
    $key = [Console]::ReadKey($true)
    switch ($key.Key) {
        "LeftArrow"  { if ($Script:px -gt 2) { $Script:px-- } }
        "RightArrow" { if ($Script:px -lt $Script:W-1) { $Script:px++ } }
        "SpaceBar"   { if ($Script:bx -eq -1) { $Script:bx = $Script:px; $Script:by = $Script:py-1; Play-Beep 800 40 } }
        "Q"          { return $false }
    }
    return $true
}

function Update {
    $hit = $null
    if ($Script:by -ge 0) {
        # Step 1
        $Script:by--
        foreach ($e in $Script:enemies) {
            if ($Script:bx -eq $e.X -and $Script:by -eq $e.Y) {
                $hit = $e; break
            }
        }
        if ($hit) {
            $Script:enemies = $Script:enemies | Where-Object { $_ -ne $hit }
            $Script:bx = -1; $Script:by = -1
            $Script:score++
            Play-Beep 1200 60
        } else {
            # Step 2
            if ($Script:by -ge 0) {
                $Script:by--
                foreach ($e in $Script:enemies) {
                    if ($Script:bx -eq $e.X -and $Script:by -eq $e.Y) {
                        $hit = $e; break
                    }
                }
                if ($hit) {
                    $Script:enemies = $Script:enemies | Where-Object { $_ -ne $hit }
                    $Script:bx = -1; $Script:by = -1
                    $Script:score++
                    Play-Beep 1200 60
                }
            }
            if ($Script:by -lt 0) { $Script:bx = -1 }
        }
    }

    $Script:frame++
    if ($Script:frame % 15 -eq 0) {
        $died = $false
        for ($i = 0; $i -lt $Script:enemies.Count; $i++) {
            $Script:enemies[$i].Y++
            if ($Script:enemies[$i].Y -ge $Script:py) { $died = $true }
        }
        if ($died) {
            $Script:lives--
            Play-Beep 300 150
            Spawn-Wave
        }
    }

    if ($Script:enemies.Count -eq 0) { Spawn-Wave }
}

function Game-Over {
    Clear-Screen
    Play-Beep 200 350
    "" | Write-Host
    "  ┌──────────────────────────────┐" | Write-Host
    "  │      ${B}${R}G A M E  O V E R${RST}      │" | Write-Host
    "  ├──────────────────────────────┤" | Write-Host
    "  │  ${B}Score:${RST} $($Script:score.ToString('00'))                       │" | Write-Host
    "  └──────────────────────────────┘" | Write-Host
    "" | Write-Host
    "  Bir tuşa basın..." | Write-Host
    $null = $host.UI.RawUI.ReadKey("NoEcho, IncludeKeyDown")
}

function Start-SpaceInvaders {
    [Console]::CursorVisible = $false
    $start = Show-StartMenu
    if (-not $start) {
        [Console]::CursorVisible = $true
        Clear-Screen
        return
    }

    Init
    Render
    $running = $true
    while ($Script:lives -gt 0 -and $running) {
        $running = Read-Input
        Update
        Render
        Start-Sleep -Milliseconds 40
    }
    Game-Over
    [Console]::CursorVisible = $true
    Clear-Screen
}

Start-SpaceInvaders
