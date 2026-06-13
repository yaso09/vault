#!/bin/bash

RST="\033[0m"; B="\033[1m"; G="\033[32m"; C="\033[36m"; R="\033[31m"; Y="\033[33m"; D="\033[2m"
W=30; H=14

hide_cursor() { printf "\033[?25l"; }
show_cursor() { printf "\033[?25h"; }
clear_screen() { printf "\033[2J\033[H"; }

init() {
    px=$((W/2)); py=$((H-3))
    score=0; lives=3; bx=-1; by=-1; frame=0
    enemies=(); spawn_wave
}

spawn_wave() {
    enemies=()
    for i in $(seq 0 5); do enemies+=("$((i*4+3)),2"); done
}

hearts() {
    local out=""
    for ((i=0; i<lives; i++)); do out+="${R}❤${RST}"; done
    for ((i=lives; i<3; i++)); do out+="${D}·${RST}"; done
    echo -n "$out"
}

render() {
    local border=$(printf -- '─%.0s' $(seq 1 $W))
    printf "\033[H"
    echo "  ┌$border┐"
    printf "  │${B}Score:${RST} %02d  %s%*s│\n" $score "$(hearts)" $((W-10)) ""
    echo "  │$(printf ' %.0s' $(seq 1 $W))│"

    for ((y=2; y<=H-2; y++)); do
        printf "  │"
        for ((x=1; x<=W; x++)); do
            local ch=" "
            if (( bx == x && by == y )); then ch="${Y}│${RST}"; fi
            for e in "${enemies[@]}"; do
                local ex="${e%,*}"; ey="${e#*,}"
                if (( x == ex && y == ey )); then ch="${R}▼${RST}"; break; fi
            done
            if (( x == px && y == py )); then ch="${G}▲${RST}"; fi
            echo -ne "$ch"
        done
        echo "│"
    done

    echo "  │$(printf ' %.0s' $(seq 1 $W))│"
    echo "  └$border┘"
    echo "  ${D}← → hareket  BOŞLUK ateş  Q çıkış${RST}"
}

read_input() {
    local key=""; saved=$(stty -g 2>/dev/null) || true
    stty -echo 2>/dev/null || true
    IFS= read -r -n1 -t 0.04 key 2>/dev/null || true
    stty "$saved" 2>/dev/null || true
    case "$key" in
        $'\033')
            local seq=""
            IFS= read -r -n1 -t 0.02 seq 2>/dev/null || true
            if [[ $seq == "[" ]]; then
                IFS= read -r -n1 -t 0.02 seq 2>/dev/null || true
                [[ $seq == "D" && px -gt 2 ]] && ((px--))
                [[ $seq == "C" && px -lt $W-1 ]] && ((px++))
            fi
            ;;
        " ") [[ bx -eq -1 ]] && { bx=$px; by=$((py-1)); } ;;
        [qQ]) return 1 ;;
    esac
    return 0
}

update() {
    if (( by >= 0 )); then
        ((by-=2))
        (( by < 0 )) && bx=-1
    fi

    local hit=-1
    for i in "${!enemies[@]}"; do
        local e="${enemies[$i]}"; ex="${e%,*}"; ey="${e#*,}"
        if (( bx == ex && by == ey )); then
            hit=$i; bx=-1; by=-1; ((score++))
            break
        fi
    done
    [[ $hit -ge 0 ]] && unset 'enemies[$hit]'

    ((frame++))
    if (( frame % 15 == 0 )); then
        local died=0
        for i in "${!enemies[@]}"; do
            local e="${enemies[$i]}"; ex="${e%,*}"; ey="${e#*,}"
            ((ey++))
            (( ey >= py )) && died=1
            enemies[$i]="$ex,$ey"
        done
        (( died )) && { ((lives--)); spawn_wave; }
    fi

    if (( ${#enemies[@]} == 0 )); then spawn_wave; fi
}

game_loop() {
    while (( lives > 0 )); do
        read_input || break
        update
        render
    done
}

game_over() {
    clear_screen
    echo ""
    echo "  ┌──────────────────────────────┐"
    printf "  │      ${B}${R}G A M E  O V E R${RST}      │\n"
    echo "  ├──────────────────────────────┤"
    printf "  │  ${B}Score:${RST} %02d                       │\n" $score
    echo "  └──────────────────────────────┘"
    echo ""
    echo "  Bir tuşa basın..."
    read -n1 -s
}

main() {
    hide_cursor
    init
    render
    game_loop
    game_over
    show_cursor
}

main "$@"
