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
        echo "$(echo "scale=1; $bytes/1073741824" | bc) GB"
    elif [[ $bytes -ge 1048576 ]]; then
        echo "$(echo "scale=1; $bytes/1048576" | bc) MB"
    elif [[ $bytes -ge 1024 ]]; then
        echo "$(echo "scale=1; $bytes/1024" | bc) KB"
    else
        echo "${bytes}B"
    fi
}

# ── Download & Install ─────────────────────────────────────────
download_file() {
    local url=$1
    local dest=$2
    echo "  İndiriliyor..."
    curl -L --progress-bar -o "$dest" "$url"
    local rc=$?
    echo ""
    return $rc
}

install_artifact() {
    local archive=$1
    local version_label=$2
    local platform=$3

    local base_dir
    base_dir=$(get_base_dir "$platform")
    local dest="$base_dir/$version_label"

    echo "  [1/4] Hedef hazırlanıyor..."
    if [[ -d "$base_dir" ]]; then
        rm -rf "$base_dir" 2>/dev/null || true
    fi
    mkdir -p "$base_dir" 2>/dev/null || {
        echo "  ${RED}Hata: $base_dir yazılamıyor.${RESET}"
        return 1
    }

    echo "  [2/4] Çıkartılıyor..."
    local tmp_dir
    tmp_dir=$(mktemp -d 2>/dev/null) || tmp_dir="/tmp/vault-extract-$$"
    mkdir -p "$tmp_dir"

    if command -v unzip &>/dev/null; then
        unzip -o "$archive" -d "$tmp_dir" 2>/dev/null || true
    else
        tar -xf "$archive" -C "$tmp_dir" 2>/dev/null || true
    fi
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

    echo "  [3/4] PATH güncelleniyor..."
    update_path "$dest" "$platform"

    if [[ "$platform" == "macos" && -d "$dest/Vault.app" ]]; then
        cp -R "$dest/Vault.app" "/Applications/Vault.app" 2>/dev/null && \
        echo "  /Applications/Vault.app kopyalandı."
    fi

    if [[ "$platform" == "windows" ]]; then
        local exe
        exe=$(ls "$dest"/vault.exe "$dest"/Vault.exe 2>/dev/null | head -1) || true
        if [[ -n "$exe" && -n "${USERPROFILE:-}" ]]; then
            echo "  Masaüstü kısayolu: $USERPROFILE\\Desktop\\Vault.lnk"
        fi
    fi

    echo ""
    echo ""
    echo "  ┌──────────────────────────────────────┐"
    echo "  │         KURULUM TAMAMLANDI           │"
    echo "  └──────────────────────────────────────┘"
    beep success
    echo ""
    echo "  Konum: $dest"
    echo "  Kullanım: vault run --desktop"
    echo ""
}

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
            echo "  PATH'e eklendi: $dest"
            echo "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
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

    echo ""
    draw_box_top
    printf "  │${BOLD}%-${IW}s${RESET}│\n" "  $version_label Kuruluyor..."
    draw_box_bottom
    echo ""

    if [[ "$source_type" == "release" ]]; then
        url="https://github.com/$REPO/releases/download/$version_label/${platform}-build-artifact.zip"
    else
        url="$API_BASE/actions/artifacts/$art_id/zip"
    fi

    if ! download_file "$url" "$archive"; then
        beep error
        echo "  ${RED}İndirme başarısız.${RESET}"
        rm -f "$archive"
        sleep 2
        return
    fi

    if [[ ! -s "$archive" ]]; then
        beep error
        echo "  ${RED}İndirilen dosya boş veya geçersiz.${RESET}"
        rm -f "$archive"
        sleep 2
        return
    fi

    install_artifact "$archive" "$version_label" "$platform"
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