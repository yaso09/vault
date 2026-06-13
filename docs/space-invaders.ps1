#!/usr/bin/env pwsh

# =========================
# CONFIG
# =========================
$ESC = [char]27
$RST = "$ESC[0m"
$R   = "$ESC[31m"
$G   = "$ESC[32m"
$Y   = "$ESC[33m"
$C   = "$ESC[36m"
$D   = "$ESC[2m"

$W = 40
$H = 18
$SAVE = "$env:APPDATA\PSInvaders.json"

# =========================
# STATE
# =========================
$state = @{
    px = 20
    py = 16
    bullets = @()
    ebullets = @()
    enemies = @()
    barriers = @()
    dir = 1
    frame = 0
    score = 0
    lives = 3
    wave = 1
    running = $true
}

# =========================
# INIT
# =========================
function Init-Game {
    $state.px = [int]($W/2)
    $state.bullets = @()
    $state.ebullets = @()
    $state.score = 0
    $state.lives = 3
    $state.wave = 1
    $state.dir = 1
    Spawn-Wave
    Spawn-Barriers
}

function Spawn-Wave {
    $state.enemies = @()
    for ($y=2; $y -lt 6; $y++) {
        for ($x=5; $x -lt $W-5; $x+=4) {
            $state.enemies += [pscustomobject]@{ x=$x; y=$y }
        }
    }
}

function Spawn-Barriers {
    $state.barriers = @()
    for ($i=0; $i -lt 4; $i++) {
        for ($y=0; $y -lt 2; $y++) {
            for ($x=0; $x -lt 6; $x++) {
                $state.barriers += [pscustomobject]@{
                    x = 6 + $i*9 + $x
                    y = 13 + $y
                    hp = 2
                }
            }
        }
    }
}

# =========================
# INPUT
# =========================
function Read-Input {
    if (-not [Console]::KeyAvailable) { return }

    $k = [Console]::ReadKey($true).Key
    switch ($k) {
        "LeftArrow"  { if ($state.px -gt 2) { $state.px-- } }
        "RightArrow" { if ($state.px -lt $W-2) { $state.px++ } }
        "Spacebar"   {
            $state.bullets += [pscustomobject]@{ x=$state.px; y=$state.py-1 }
            [console]::beep(1200,30)
        }
        "Q" { $state.running = $false }
    }
}

# =========================
# UPDATE
# =========================
function Update-Bullets {

    # player bullets
    foreach ($b in $state.bullets) { $b.y-- }

    $state.bullets = $state.bullets | Where-Object { $_.y -gt 0 }

    # enemy bullets
    foreach ($b in $state.ebullets) { $b.y++ }
    $state.ebullets = $state.ebullets | Where-Object { $_.y -lt $H }

}

function Enemy-Shoot {
    if ((Get-Random -Max 100) -lt 8 -and $state.enemies.Count -gt 0) {
        $e = Get-Random $state.enemies
        $state.ebullets += [pscustomobject]@{ x=$e.x; y=$e.y+1 }
    }
}

function Move-Enemies {

    $edge = ($state.enemies | Measure-Object x -Maximum).Maximum -gt ($W-3) -or
            ($state.enemies | Measure-Object x -Minimum).Minimum -lt 2

    if ($edge) {
        $state.dir *= -1
        foreach ($e in $state.enemies) { $e.y++ }
    }

    foreach ($e in $state.enemies) {
        $e.x += $state.dir
    }

}

function Collisions {

    # bullet vs enemy
    foreach ($b in $state.bullets) {
        foreach ($e in $state.enemies) {
            if ($b.x -eq $e.x -and $b.y -eq $e.y) {
                $state.enemies = $state.enemies | Where-Object { $_ -ne $e }
                $b.y = -999
                $state.score += 10
                [console]::beep(900,20)
            }
        }
    }

    # enemy bullet vs player
    foreach ($b in $state.ebullets) {
        if ($b.x -eq $state.px -and $b.y -eq $state.py) {
            $state.lives--
            [console]::beep(300,150)
        }
    }

    # enemies reach bottom
    foreach ($e in $state.enemies) {
        if ($e.y -ge $state.py) {
            $state.lives = 0
        }
    }

    # barrier damage
    foreach ($b in $state.bullets) {
        foreach ($br in $state.barriers) {
            if ($b.x -eq $br.x -and $b.y -eq $br.y) {
                $br.hp--
                $b.y = -999
            }
        }
    }

    $state.barriers = $state.barriers | Where-Object { $_.hp -gt 0 }
}

# =========================
# RENDER (FAST)
# =========================
function Render {

    [Console]::SetCursorPosition(0,0)

    $screen = New-Object "char[,]" $H,$W

    # fill
    for ($y=0; $y -lt $H; $y++) {
        for ($x=0; $x -lt $W; $x++) {
            $screen[$y,$x] = ' '
        }
    }

    # player
    $screen[$state.py,$state.px] = 'A'

    # bullets
    foreach ($b in $state.bullets) {
        if ($b.y -ge 0 -and $b.y -lt $H) {
            $screen[$b.y,$b.x] = '|'
        }
    }

    foreach ($b in $state.ebullets) {
        if ($b.y -ge 0 -and $b.y -lt $H) {
            $screen[$b.y,$b.x] = 'v'
        }
    }

    # enemies
    foreach ($e in $state.enemies) {
        if ($e.y -ge 0 -and $e.y -lt $H) {
            $screen[$e.y,$e.x] = 'W'
        }
    }

    # barriers
    foreach ($b in $state.barriers) {
        if ($b.y -ge 0 -and $b.y -lt $H) {
            $screen[$b.y,$b.x] = '#'
        }
    }

    # UI
    Write-Host "Score: $($state.score)  Lives: $($state.lives)  Wave: $($state.wave)"
    Write-Host ("-" * $W)

    for ($y=0; $y -lt $H; $y++) {
        $line = ""
        for ($x=0; $x -lt $W; $x++) {
            $line += $screen[$y,$x]
        }
        Write-Host $line
    }

    Write-Host ("-" * $W)
    Write-Host "← → hareket | Space ateş | Q çıkış"
}

# =========================
# SAVE
# =========================
function Save-Game {
    $state | ConvertTo-Json | Set-Content $SAVE
}

function Load-Game {
    if (Test-Path $SAVE) {
        $global:state = Get-Content $SAVE | ConvertFrom-Json
    }
}

# =========================
# GAME LOOP
# =========================
function GameLoop {

    [Console]::CursorVisible = $false
    Init-Game

    while ($state.running -and $state.lives -gt 0) {

        Read-Input
        Update-Bullets
        Move-Enemies
        Enemy-Shoot
        Collisions

        if ($state.enemies.Count -eq 0) {
            $state.wave++
            Spawn-Wave
        }

        Render
        Start-Sleep -Milliseconds 60
    }

    [Console]::CursorVisible = $true
    Write-Host "`nGAME OVER - Score: $($state.score)"
    Save-Game
}

GameLoop