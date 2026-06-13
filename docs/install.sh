#!/bin/bash

# ── TUI Constants ───────────────────────────────────────────────
RESET="\033[0m"
BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
MAGENTA="\033[35m"
BLUE="\033[34m"

IW=48  # interior width between ││ borders

# ── Retro Beep ─────────────────────────────────────────────────
beep() {
    local pattern=${1:-nav}
    local bel="printf '\a' >/dev/tty"
    case "$pattern" in
        nav)     eval "$bel" ;;
        select)  eval "$bel"; sleep 0.08; eval "$bel" ;;
        error)   eval "$bel"; sleep 0.12; eval "$bel"; sleep 0.12; eval "$bel" ;;
        success) eval "$bel"; sleep 0.1; eval "$bel"; sleep 0.1; eval "$bel" ;;
        *)       eval "$bel" ;;
    esac
}

# ── TUI Primitives ──────────────────────────────────────────────
clear_screen() {
    printf "\033[2J\033[H"
}

hide_cursor() {
    printf "\033[?25l"
}

show_cursor() {
    printf "\033[?25h"
}

draw_box_top() {
    printf "  ┌"
    printf -- "─%.0s" $(seq 1 $IW)
    printf "┐\n"
}

draw_box_bottom() {
    printf "  └"
    printf -- "─%.0s" $(seq 1 $IW)
    printf "┘\n"
}

draw_separator() {
    printf "  ├"
    printf -- "─%.0s" $(seq 1 $IW)
    printf "┤\n"
}

draw_title() {
    local text=$1
    local padded="  $text"
    padded=$(printf "%-${IW}s" "$padded")
    printf "  │${BOLD}${CYAN}%s${RESET}│\n" "$padded"
}

draw_blank() {
    printf "  │%${IW}s│\n" ""
}

draw_item() {
    local selected=$1
    local text=$2
    local padded
    if [[ $selected -eq 1 ]]; then
        padded=$(printf "%-$(($IW - 4))s" "$text")
        printf "  │  ${GREEN}>${RESET} %s│\n" "$padded"
    else
        padded=$(printf "%-$(($IW - 4))s" "$text")
        printf "  │    %s│\n" "$padded"
    fi
}

draw_footer() {
    local text=$1
    printf "${DIM}  %s${RESET}\n" "$text"
}

# ── Menu Renderer ──────────────────────────────────────────────
# Bash 3 uyumlu: local -n (nameref) yerine eval kullanır
render_menu() {
    local items_ref=$1
    local selected=$2
    local title=$3
    local footer=$4

    clear_screen
    draw_box_top
    draw_title "$title"
    draw_separator
    draw_blank

    local items_len
    eval "items_len=\${#${items_ref}[@]}"

    local i=0
    while [[ $i -lt $items_len ]]; do
        local item
        eval "item=\${${items_ref}[$i]}"
        if [[ -z "$item" ]]; then
            draw_blank
        elif [[ $i -eq $selected ]]; then
            draw_item 1 "$item"
        else
            draw_item 0 "$item"
        fi
        ((i++)) || true
    done

    draw_blank
    draw_box_bottom
    draw_footer "$footer"
}

# ── Key Reader ─────────────────────────────────────────────────
read_key() {
    local key seq
    local saved
    saved=$(stty -g 2>/dev/null) || true
    stty -echo 2>/dev/null || true
    IFS= read -r -n1 key 2>/dev/null || true
    stty "$saved" 2>/dev/null || true
    if [[ $key == $'\033' ]]; then
        IFS= read -r -n1 -t 0.1 seq 2>/dev/null || true
        if [[ $seq == "[" ]]; then
            IFS= read -r -n1 -t 0.1 key 2>/dev/null || true
            case "$key" in
                A) beep nav;    echo "up"    ;;
                B) beep nav;    echo "down"  ;;
                *)               echo "esc"   ;;
            esac
        else
            echo "esc"
        fi
    elif [[ -z "$key" ]]; then
        beep select
        echo "enter"
    elif [[ $key == "q" || $key == "Q" ]]; then
        echo "q"
    else
        echo "other"
    fi
}

# ── GitHub API ─────────────────────────────────────────────────
REPO="yaso09/vault"
API_BASE="https://api.github.com/repos/$REPO"

api_get() {
    local url=$1
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        curl -sL -H "Authorization: Bearer $GITHUB_TOKEN" "$url"
    else
        curl -sL "$url"
    fi
}

fetch_releases() {
    local json
    json=$(api_get "$API_BASE/releases?per_page=10") || return 1
    if [[ -z "$json" ]]; then
        return 1
    fi
    if command -v python3 &>/dev/null; then
        echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data:
    tag = r.get('tag_name', '?')
    pub = r.get('published_at', '') or r.get('created_at', '')
    date = pub[:10] if len(pub) >= 10 else '?'
    print(f'{tag}|{date}')
" 2>/dev/null
    else
        echo "$json" | grep -o '"tag_name":"[^"]*"' | sed 's/"tag_name":"//;s/"//' | \
        while IFS= read -r tag; do
            echo "${tag}|?"
        done
    fi
}

fetch_workflow_runs() {
    local json
    json=$(api_get "$API_BASE/actions/workflows/release.yml/runs?per_page=10&status=success") || return 1
    if [[ -z "$json" ]]; then
        return 1
    fi
    if command -v python3 &>/dev/null; then
        echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
for r in runs:
    sha = r.get('head_sha', '?')[:7]
    commit = r.get('head_commit') or {}
    msg = (commit.get('message', '?') or '?').split('\n')[0][:50]
    branch = r.get('head_branch', '?')
    date = (r.get('created_at', '') or '?')[:10]
    run_id = r.get('id', 0)
    print(f'{sha}|{msg}|{branch}|{date}|{run_id}')
" 2>/dev/null
    fi
}

fetch_artifacts() {
    local run_id=$1
    local json
    json=$(api_get "$API_BASE/actions/runs/$run_id/artifacts") || return 1
    if [[ -z "$json" ]]; then
        return 1
    fi
    if command -v python3 &>/dev/null; then
        echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
arts = data.get('artifacts', [])
for a in arts:
    name = a.get('name', '?')
    size = a.get('size_in_bytes', 0)
    art_id = a.get('id', 0)
    print(f'{name}|{size}|{art_id}')
" 2>/dev/null
    fi
}

# ── Helpers ────────────────────────────────────────────────────
detect_platform() {
    case "$(uname -s)" in
        Darwin) echo "macos"  ;;
        Linux)  echo "linux"  ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)      echo "unknown" ;;
    esac
}

get_base_dir() {
    local platform=$1
    case "$platform" in
        macos)   echo "$HOME/Library/Application Support/Vault" ;;
        linux)   echo "${XDG_DATA_HOME:-$HOME/.local/share}/Vault" ;;
        windows) echo "$APPDATA/Vault" ;;
        *)       echo "" ;;
    esac
}

format_size() {
    local bytes=$1
    if [[ $bytes -ge 1073741824 ]]; then
        awk -v b="$bytes" 'BEGIN { printf "%.1f GB\n", b/1073741824 }' 2>/dev/null || echo "$((bytes/1073741824)) GB"
    elif [[ $bytes -ge 1048576 ]]; then
        awk -v b="$bytes" 'BEGIN { printf "%.1f MB\n", b/1048576 }' 2>/dev/null || echo "$((bytes/1048576)) MB"
    elif [[ $bytes -ge 1024 ]]; then
        awk -v b="$bytes" 'BEGIN { printf "%.1f KB\n", b/1024 }' 2>/dev/null || echo "$((bytes/1024)) KB"
    else
        echo "${bytes} B"
    fi
}

format_eta() {
    local seconds=$1
    if (( seconds <= 0 )); then
        echo ""
    elif (( seconds < 60 )); then
        echo "~${seconds}s kaldı"
    elif (( seconds < 3600 )); then
        echo "~$((seconds / 60))dk kaldı"
    else
        echo "~$((seconds / 3600))sa kaldı"
    fi
}

draw_install_screen() {
    local title=$1
    shift
    local steps=("$@")
    N_STEPS=${#steps[@]}

    clear_screen
    draw_box_top
    draw_title "$title"
    draw_separator
    draw_blank

    for ((i=0; i<N_STEPS; i++)); do
        local label="[$(($i+1))/$N_STEPS]  ${steps[$i]}"
        local step_text
        step_text=$(printf "%-43s" "$label")
        printf "  │  ${DIM}·${RESET}  %s│\n" "$step_text"
    done

    draw_blank
    draw_box_bottom
    # Print two blank lines for progress bar and return to anchor line
    printf "\n\n\033[2A"
}

set_step_status() {
    local index=$1
    local status=$2
    local spinner_char=${3:-}

    # Save cursor (anchor line)
    printf "\033[s"

    # Go to step line: from the anchor line, we go up $((N_STEPS - index + 2)) lines
    local up_lines=$((N_STEPS - index + 2))
    printf "\033[%dA" "$up_lines"

    # Go to column 6 (where the dot is)
    printf "\r\033[5C"

    # Print status icon
    case "$status" in
        pending) printf "${DIM}·${RESET}" ;;
        running) printf "${CYAN}▶${RESET}" ;;
        done)    printf "${GREEN}✓${RESET}" ;;
        error)   printf "${RED}✗${RESET}" ;;
        spinner) printf "${CYAN}%s${RESET}" "$spinner_char" ;;
    esac

    # Restore cursor (back to anchor line)
    printf "\033[u"
}

draw_progress_bar() {
    local percent=$1
    local received=$2
    local total=$3
    local speed=$4
    local eta=$5

    local bar_width=34
    local line1=""
    local line2=""

    if (( percent >= 0 )); then
        local filled=$(( bar_width * percent / 100 ))
        local empty=$(( bar_width - filled ))
        local filled_bar=""
        local empty_bar=""
        if (( filled > 0 )); then filled_bar=$(printf '█%.0s' $(seq 1 $filled 2>/dev/null)); fi
        if (( empty > 0 )); then empty_bar=$(printf '░%.0s' $(seq 1 $empty 2>/dev/null)); fi
        line1="  ${GREEN}${filled_bar}${RESET}${DIM}${empty_bar}${RESET} $(printf "%3d" $percent)%"
    else
        # Indeterminate animation
        local pos=$(( ( $(date +%s%N 2>/dev/null || date +%s) / 80000000 ) % bar_width ))
        local chars=()
        for ((k=0; k<bar_width; k++)); do chars+=(" "); done
        for ((k=0; k<6; k++)); do chars[$(( (pos + k) % bar_width ))]="█"; done
        local bar_str=""
        for c in "${chars[@]}"; do bar_str+="$c"; done
        line1="  ${CYAN}${bar_str}${RESET}  ···"
    fi

    local rec_str
    local tot_str
    rec_str=$(format_size "$received")
    if (( total > 0 )); then
        tot_str=$(format_size "$total")
    else
        tot_str="?"
    fi

    line2="  ${DIM}${rec_str} / ${tot_str}${RESET}"
    if [[ -n "$speed" && "$speed" -gt 0 ]]; then
        local speed_str
        speed_str=$(format_size "$speed")
        line2+="  •  ${CYAN}${speed_str}/s${RESET}"
    fi
    if [[ -n "$eta" ]]; then
        line2+="  ${DIM}${eta}${RESET}"
    fi

    # Save cursor, move down, print line 1, move down, print line 2, restore cursor
    printf "\033[s"
    printf "\033[1B\r%-72s\r%s" "" "$line1"
    printf "\033[1B\r%-72s\r%s" "" "$line2"
    printf "\033[u"
}


# ── Download & Install ─────────────────────────────────────────
update_path() {
    local dest=$1
    local platform=$2
    local profile=""

    case "$platform" in
        linux)
            if [[ -n "${ZSH_VERSION:-}" || -f "$HOME/.zshrc" ]]; then
                profile="$HOME/.zshrc"
            else
                profile="$HOME/.bashrc"
            fi
            ;;
        macos)
            profile="$HOME/.zshrc"
            ;;
        windows)
            return 0
            ;;
    esac

    if [[ -n "$profile" ]]; then
        local line="export PATH=\"$dest:\$PATH\""
        if ! grep -qxF "$line" "$profile" 2>/dev/null; then
            echo "" >> "$profile"
            echo "# Vault" >> "$profile"
            echo "$line" >> "$profile"
        fi
    fi

    export PATH="$dest:$PATH"
}

# ── Flow Screens ────────────────────────────────────────────────
do_install() {
    local source_type=$1
    local version_label=$2
    local platform=$3
    local art_id=${4:-}

    local url=""
    local archive
    archive=$(mktemp 2>/dev/null) || archive="/tmp/vault-install-$$.zip"

    local steps=(
        "Bağlantı kuruluyor  "
        "Dosyalar indiriliyor"
        "Arşiv çıkartılıyor  "
        "PATH güncelleniyor  "
    )

    draw_install_screen "  ⚙  $version_label — $platform" "${steps[@]}"
    set_step_status 0 "running"

    if [[ "$source_type" == "release" ]]; then
        url="https://github.com/$REPO/releases/download/$version_label/${platform}-build-artifact.zip"
    else
        url="$API_BASE/actions/artifacts/$art_id/zip"
    fi

    # Connection test & size query
    local auth_header=()
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        auth_header=(-H "Authorization: Bearer $GITHUB_TOKEN")
    fi

    local total_bytes
    total_bytes=$(curl -sIL "${auth_header[@]}" "$url" | grep -i '^content-length:' | tail -n1 | awk '{print $2}' | tr -d '\r')

    set_step_status 0 "done"
    set_step_status 1 "running"

    # Start download in background
    curl -sL "${auth_header[@]}" "$url" -o "$archive" &
    local curl_pid=$!

    local received=0
    local last_received=0
    local last_time
    last_time=$(date +%s)
    local speed=0
    local start_time
    start_time=$(date +%s)

    while kill -0 "$curl_pid" 2>/dev/null; do
        if [[ -f "$archive" ]]; then
            received=$(wc -c < "$archive")
        else
            received=0
        fi
        local now
        now=$(date +%s)
        local elapsed=$((now - last_time))
        if (( elapsed >= 1 )); then
            speed=$(( (received - last_received) / elapsed ))
            last_received=$received
            last_time=$now
        fi

        local percent=-1
        if [[ -n "$total_bytes" && "$total_bytes" -gt 0 ]]; then
            percent=$(( received * 100 / total_bytes ))
        fi
        local eta=""
        if [[ $speed -gt 0 && -n "$total_bytes" && $received -lt $total_bytes ]]; then
            local remaining=$((total_bytes - received))
            local eta_seconds=$((remaining / speed))
            eta=$(format_eta "$eta_seconds")
        fi

        draw_progress_bar "$percent" "$received" "$total_bytes" "$speed" "$eta"
        sleep 0.2
    done
    wait "$curl_pid"
    local rc=$?

    if [[ $rc -ne 0 || ! -s "$archive" ]]; then
        set_step_status 1 "error"
        beep error
        # Go below the box & progress bar area
        printf "\033[3B\r"
        echo "  ${RED}İndirme başarısız. URL veya token'ı kontrol edin.${RESET}"
        rm -f "$archive"
        sleep 2.5
        return
    fi

    # Complete progress bar at 100%
    draw_progress_bar 100 "$received" "$received" "" "tamamlandı"
    set_step_status 1 "done"
    set_step_status 2 "running"

    # Extract Setup
    local base_dir
    base_dir=$(get_base_dir "$platform")
    local dest="$base_dir/$version_label"

    if [[ -d "$base_dir" ]]; then
        rm -rf "$base_dir" 2>/dev/null || true
    fi
    mkdir -p "$base_dir" 2>/dev/null || {
        set_step_status 2 "error"
        beep error
        printf "\033[3B\r"
        echo "  ${RED}Hata: $base_dir dizini oluşturulamıyor.${RESET}"
        rm -f "$archive"
        sleep 2.5
        return
    }

    local tmp_dir
    tmp_dir=$(mktemp -d 2>/dev/null) || tmp_dir="/tmp/vault-extract-$$"
    mkdir -p "$tmp_dir"

    # Background extraction with spinner
    (
        if command -v unzip &>/dev/null; then
            unzip -o "$archive" -d "$tmp_dir" 2>/dev/null || true
        else
            tar -xf "$archive" -C "$tmp_dir" 2>/dev/null || true
        fi
    ) &
    local extract_pid=$!

    local spin=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local si=0
    while kill -0 "$extract_pid" 2>/dev/null; do
        set_step_status 2 "spinner" "${spin[$((si % 10))]}"
        ((si++))
        sleep 0.08
    done
    wait "$extract_pid"
    rm -f "$archive"

    mkdir -p "$dest"
    local inner
    inner=$(ls -d "$tmp_dir"/*/ 2>/dev/null | head -1)
    if [[ -n "$inner" ]]; then
        mv "$inner"/* "$dest"/ 2>/dev/null || true
    else
        mv "$tmp_dir"/* "$dest"/ 2>/dev/null || true
    fi
    rm -rf "$tmp_dir"

    set_step_status 2 "done"
    set_step_status 3 "running"

    # PATH & Platform specific tasks
    update_path "$dest" "$platform"

    if [[ "$platform" == "macos" && -d "$dest/Vault.app" ]]; then
        cp -R "$dest/Vault.app" "/Applications/Vault.app" 2>/dev/null
    fi

    set_step_status 3 "done"
    beep success

    # Go below progress bar area and print success box
    printf "\033[3B\r"

    echo "  ┌──────────────────────────────────────────────┐"
    echo "  │        ${GREEN}KURULUM BAŞARIYLA TAMAMLANDI${RESET}          │"
    echo "  ├──────────────────────────────────────────────┤"
    
    local padded_dest
    padded_dest=$(printf "%-34s" "$dest")
    if [ ${#padded_dest} -gt 34 ]; then
        padded_dest="${padded_dest:0:31}..."
    fi
    echo "  │  Konum   : $padded_dest│"
    echo "  │  Kullanım: vault run --desktop               │"
    echo "  └──────────────────────────────────────────────┘"
    echo ""
}

release_flow() {
    local raw_lines
    echo ""
    echo "  Sürümler alınıyor..."
    raw_lines=$(fetch_releases) || raw_lines=""
    if [[ -z "$raw_lines" ]]; then
        beep error
        echo "  ${RED}Henüz bir sürüm yayınlanmamış.${RESET}"
        sleep 1
        return
    fi

    local display=()
    local tags=()
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        local tag="${line%%|*}"
        local date="${line#*|}"
        display+=("$tag  •  $date")
        tags+=("$tag")
    done <<< "$raw_lines"

    if [[ ${#display[@]} -eq 0 ]]; then
        beep error
        echo "  ${RED}Henüz bir sürüm yayınlanmamış.${RESET}"
        sleep 1
        return
    fi

    local selected=0
    while true; do
        render_menu display $selected "📦  Kararlı Sürüm Seçin" \
            "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        local key
        key=$(read_key)
        case "$key" in
            up)    [[ $selected -gt 0 ]] && ((selected--)) || true ;;
            down)  [[ $selected -lt $((${#display[@]} - 1)) ]] && ((selected++)) || true ;;
            enter)
                platform_flow "${tags[$selected]}"
                return
                ;;
            esc|q) return ;;
        esac
    done
}

platform_flow() {
    local tag=$1
    local detected
    detected=$(detect_platform)

    local platforms=("windows" "linux" "macos" "apk" "aab")
    local display=()
    local detected_idx=0

    local i=0
    for p in "${platforms[@]}"; do
        if [[ "$p" == "$detected" ]]; then
            display+=("$p (otomatik tespit)")
            detected_idx=$i
        elif [[ "$p" == "apk" ]]; then
            display+=("$p (Android APK)")
        elif [[ "$p" == "aab" ]]; then
            display+=("$p (Android AAB)")
        else
            display+=("$p")
        fi
        ((i++)) || true
    done

    local selected=$detected_idx
    while true; do
        render_menu display $selected "Platform Seçin — $tag" \
            "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        local key
        key=$(read_key)
        case "$key" in
            up)    [[ $selected -gt 0 ]] && ((selected--)) || true ;;
            down)  [[ $selected -lt $((${#display[@]} - 1)) ]] && ((selected++)) || true ;;
            enter)
                do_install "release" "$tag" "${platforms[$selected]}"
                echo ""
                echo "  Ana menüye dönmek için bir tuşa basın..."
                read -r -s -n1 || true
                return
                ;;
            esc|q) return ;;
        esac
    done
}

commit_flow() {
    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
        echo ""
        echo "  Workflow artifact'leri için GitHub Token gerekli."
        echo "  (https://github.com/settings/tokens adresinden oluşturabilirsiniz)"
        echo ""
        printf "  GitHub Token: "
        local saved
        saved=$(stty -g 2>/dev/null) || true
        stty -echo 2>/dev/null || true
        IFS= read -r GITHUB_TOKEN || true
        stty "$saved" 2>/dev/null || true
        echo ""
        if [[ -z "${GITHUB_TOKEN:-}" ]]; then
            beep error
            echo "  ${RED}Token gerekli. Ana menüye dönülüyor.${RESET}"
            sleep 1
            return
        fi
        export GITHUB_TOKEN
    fi

    local raw_lines
    echo ""
    echo "  Workflow run'ları alınıyor..."
    raw_lines=$(fetch_workflow_runs) || raw_lines=""
    if [[ -z "$raw_lines" ]]; then
        beep error
        echo "  ${RED}Hiç test yapısı bulunamadı.${RESET}"
        sleep 1
        return
    fi

    local display=()
    local data=()
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        local sha="${line%%|*}"
        local rest="${line#*|}"
        local msg="${rest%%|*}"
        rest="${rest#*|}"
        local branch="${rest%%|*}"
        rest="${rest#*|}"
        local date="${rest%%|*}"
        local run_id="${rest#*|}"

        local max_msg=$(($IW - 4 - 9))
        local msg_disp
        if [[ ${#msg} -gt $max_msg ]]; then
            msg_disp="${msg:0:$(($max_msg - 3))}..."
        else
            msg_disp="$msg"
        fi

        local max_br=$(($IW - 4 - 23))
        local br_disp
        if [[ ${#branch} -gt $max_br ]]; then
            br_disp="${branch:0:$(($max_br - 3))}..."
        else
            br_disp="$branch"
        fi

        display+=("$sha  $msg_disp")
        display+=("   branch: $br_disp  $date")
        data+=("$run_id|$sha")
    done <<< "$raw_lines"

    if [[ ${#display[@]} -eq 0 ]]; then
        beep error
        echo "  ${RED}Hiç test yapısı bulunamadı.${RESET}"
        sleep 1
        return
    fi

    local selected=0
    while true; do
        render_menu display $selected "🔧  Test Sürümü Seçin" \
            "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        local key
        key=$(read_key)
        case "$key" in
            up)    [[ $selected -gt 0 ]] && ((selected--)) || true ;;
            down)  [[ $selected -lt $((${#display[@]} - 1)) ]] && ((selected++)) || true ;;
            enter)
                local entry="${data[$selected]}"
                local run_id="${entry%%|*}"
                local sha="${entry#*|}"
                artifact_flow "$run_id" "$sha"
                return
                ;;
            esc|q) return ;;
        esac
    done
}

artifact_flow() {
    local run_id=$1
    local sha=$2
    local raw_lines

    echo ""
    echo "  Yapıtlar alınıyor..."
    raw_lines=$(fetch_artifacts "$run_id") || raw_lines=""
    if [[ -z "$raw_lines" ]]; then
        echo "  ${RED}Seçilen commit için yapı bulunamadı.${RESET}"
        sleep 1
        return
    fi

    local display=()
    local art_names=()
    local art_ids=()
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        local name="${line%%|*}"
        local rest="${line#*|}"
        local size="${rest%%|*}"
        local art_id="${rest#*|}"

        local display_name="${name%-build-artifact}"
        [[ "$display_name" == "$name" ]] && display_name="$name"
        display+=("$display_name ($(format_size $size))")
        art_names+=("$name")
        art_ids+=("$art_id")
    done <<< "$raw_lines"

    if [[ ${#display[@]} -eq 0 ]]; then
        echo "  ${RED}Seçilen commit için yapı bulunamadı.${RESET}"
        sleep 1
        return
    fi

    local selected=0
    while true; do
        render_menu display $selected "Yapı Seçin — $sha" \
            "↑/↓: Gezin  Enter: Seç  Esc: Geri"

        local key
        key=$(read_key)
        case "$key" in
            up)    [[ $selected -gt 0 ]] && ((selected--)) || true ;;
            down)  [[ $selected -lt $((${#display[@]} - 1)) ]] && ((selected++)) || true ;;
            enter)
                do_install "artifact" "$sha" \
                    "${art_names[$selected]%-build-artifact}" \
                    "${art_ids[$selected]}"
                echo ""
                echo "  Ana menüye dönmek için bir tuşa basın..."
                read -r -s -n1 || true
                return
                ;;
            esc|q) return ;;
        esac
    done
}

# ── Main Menu ──────────────────────────────────────────────────
main_menu() {
    local options=(
        "📦  Kararlı sürüm kur"
        "🔧  Test sürümü kur"
        ""
        "❌  Çıkış"
    )
    local selected=0

    while true; do
        render_menu options $selected "VAULT KURULUM — yaso09/vault" \
            "↑/↓: Gezin  Enter: Seç  Q: Çıkış"

        local key
        key=$(read_key)
        case "$key" in
            up)   [[ $selected -gt 0 ]] && ((selected--)) || true ;;
            down) [[ $selected -lt $((${#options[@]} - 1)) ]] && ((selected++)) || true ;;
            enter)
                case $selected in
                    0) release_flow ;;
                    1) commit_flow  ;;
                    3) clear_screen; show_cursor; exit 0 ;;
                esac
                ;;
            q|esc) clear_screen; show_cursor; exit 0 ;;
        esac

        # Boş satırları atla
        while [[ $selected -lt ${#options[@]} && -z "${options[$selected]}" ]]; do
            ((selected++)) || true
        done
    done
}

# ── Entry Point ─────────────────────────────────────────────────
hide_cursor
# EXIT trap'ten clear_screen kaldırıldı — hata olunca ekran silinmez
trap 'show_cursor; exit' INT TERM EXIT
main_menu