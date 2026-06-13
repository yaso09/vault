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

play_beep() {
    printf "\a" >/dev/tty 2>/dev/null &
}

set_raw_blocking() {
    stty -echo -icanon time 10 min 1 2>/dev/null || true
}

set_raw_nonblocking() {
    stty -echo -icanon time 0 min 0 2>/dev/null || true
}

restore_terminal() {
    stty "$saved_stty" 2>/dev/null || true
    show_cursor
}

show_start_menu() {
    set_raw_blocking
    local selected=0
    local options=("  O Y U N A  B A Ş L A  " "      Ç I K I Ş        ")
    while true; do
        clear_screen
        local border=$(printf -- '─%.0s' $(seq 1 $W))
        echo "  ┌$border┐"
        echo "  │$(printf ' %.0s' $(seq 1 $W))│"
        echo "  │      ${B}${G}S P A C E  I N V A D E R S${RST}      │"
        echo "  │$(printf ' %.0s' $(seq 1 $W))│"
        echo "  ├$border┤"
        echo "  │$(printf ' %.0s' $(seq 1 $W))│"
        
        for i in "${!options[@]}"; do
            local opt="${options[$i]}"
            local pad=$(( (W - ${#opt}) / 2 ))
            local pad_str=$(printf "%${pad}s" "")
            local right_pad=$(( W - ${#opt} - pad ))
            local right_pad_str=$(printf "%${right_pad}s" "")
            if [[ $i -eq $selected ]]; then
                echo -e "  │${B}${Y}> ${pad_str}${opt}${right_pad_str}${RST}│"
            else
                echo -e "  │  ${pad_str}${opt}${right_pad_str}  │"
            fi
        done
        
        echo "  │$(printf ' %.0s' $(seq 1 $W))│"
        echo "  └$border┘"
        echo "  ${D}↑/↓: Gezin  Enter: Seç  Q: Çıkış${RST}"
        
        local key
        IFS= read -r -n1 key 2>/dev/null || true
        if [[ $key == $'\033' ]]; then
            local seq=""
            IFS= read -r -n1 -t 0.05 seq 2>/dev/null || true
            if [[ $seq == "[" ]]; then
                IFS= read -r -n1 -t 0.05 seq 2>/dev/null || true
                case "$seq" in
                    A) [[ $selected -gt 0 ]] && ((selected--)) ;;
                    B) [[ $selected -lt $((${#options[@]} - 1)) ]] && ((selected++)) ;;
                esac
            fi
        elif [[ -z "$key" ]]; then
            if [[ $selected -eq 0 ]]; then return 0; fi
            if [[ $selected -eq 1 ]]; then return 1; fi
        elif [[ $key == "q" || $key == "Q" ]]; then
            return 1
        fi
    done
}

read_input() {
    local key=""
    IFS= read -r -n1 key 2>/dev/null || true
    case "$key" in
        $'\033')
            local seq=""
            IFS= read -r -n1 -t 0.01 seq 2>/dev/null || true
            if [[ $seq == "[" ]]; then
                IFS= read -r -n1 -t 0.01 seq 2>/dev/null || true
                [[ $seq == "D" && px -gt 2 ]] && ((px--))
                [[ $seq == "C" && px -lt $W-1 ]] && ((px++))
            fi
            ;;
        " ") 
            if [[ bx -eq -1 ]]; then
                bx=$px
                by=$((py-1))
                play_beep
            fi
            ;;
        [qQ]) return 1 ;;
    esac
    return 0
}

update() {
    local hit=-1
    if (( by >= 0 )); then
        # Step 1
        ((by--))
        for i in "${!enemies[@]}"; do
            local e="${enemies[$i]}"; ex="${e%,*}"; ey="${e#*,}"
            if (( bx == ex && by == ey )); then
                hit=$i; bx=-1; by=-1; ((score++))
                play_beep
                break
            fi
        done
        if [[ $hit -ge 0 ]]; then
            unset 'enemies[$hit]'
        else
            # Step 2
            if (( by >= 0 )); then
                ((by--))
                for i in "${!enemies[@]}"; do
                    local e="${enemies[$i]}"; ex="${e%,*}"; ey="${e#*,}"
                    if (( bx == ex && by == ey )); then
                        hit=$i; bx=-1; by=-1; ((score++))
                        play_beep
                        break
                    fi
                done
                if [[ $hit -ge 0 ]]; then
                    unset 'enemies[$hit]'
                fi
            fi
            (( by < 0 )) && bx=-1
        fi
    fi

    ((frame++))
    if (( frame % 15 == 0 )); then
        local died=0
        for i in "${!enemies[@]}"; do
            local e="${enemies[$i]}"; ex="${e%,*}"; ey="${e#*,}"
            ((ey++))
            (( ey >= py )) && died=1
            enemies[$i]="$ex,$ey"
        done
        if (( died )); then
            ((lives--))
            play_beep
            spawn_wave
        fi
    fi

    if (( ${#enemies[@]} == 0 )); then spawn_wave; fi
}

game_loop() {
    set_raw_nonblocking
    while (( lives > 0 )); do
        read_input || break
        update
        render
        sleep 0.04
    done
}

game_over() {
    restore_terminal
    clear_screen
    play_beep
    echo ""
    echo "  ┌──────────────────────────────┐"
    printf "  │      ${B}${R}G A M E  O V E R${RST}      │\n"
    echo "  ├──────────────────────────────┤"
    printf "  │  ${B}Score:${RST} %02d                       │\n" $score
    echo "  └──────────────────────────────┘"
    echo ""
    echo "  Bir tuşa basın..."
    read -n1 -s
    clear_screen
}

main() {
    hide_cursor
    saved_stty=$(stty -g 2>/dev/null) || true
    trap 'restore_terminal; exit' INT TERM EXIT

    if show_start_menu; then
        init
        render
        game_loop
        game_over
    else
        restore_terminal
        clear_screen
    fi
}

main "$@"
