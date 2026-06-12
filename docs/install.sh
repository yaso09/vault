#!/bin/bash
set -e

REPO="yaso09/vault"

# Platform tespiti
OS="$(uname -s)"
case "$OS" in
    Darwin)  PLATFORM="macos";;
    Linux)   PLATFORM="linux";;
    *)       echo "Desteklenmeyen işletim sistemi: $OS"; exit 1;;
esac

# Hedef ana klasör
if [ "$PLATFORM" = "macos" ]; then
    BASE="$HOME/Library/Application Support/Vault"
else
    BASE="${XDG_DATA_HOME:-$HOME/.local/share}/Vault"
fi

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │       VAULT — $PLATFORM Kurulumu        │"
echo "  └──────────────────────────────────────┘"
echo ""
echo "  Hedef: $BASE"
echo ""

# 1. GitHub API ile en son release bilgisi
echo "  [1/4] Sürüm bilgisi alınıyor..."
TAG=$(curl -sL "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": "//;s/",//')
if [ -z "$TAG" ]; then
    echo "  Hata: Sürüm bilgisi alınamadı."
    exit 1
fi
echo "  Sürüm: $TAG"

DEST="$BASE/$TAG"

# 2. Hedef klasörü hazırla
if [ -d "$BASE" ]; then
    echo "  [2/4] Eski kurulum kaldırılıyor..."
    rm -rf "$BASE"
fi
mkdir -p "$BASE"

# 3. Build'i indir
URL="https://github.com/$REPO/releases/download/$TAG/${PLATFORM}-build-artifact.zip"
ARCHIVE="/tmp/vault-$PLATFORM.zip"
echo "  [3/4] İndiriliyor: $URL"
curl -sL -o "$ARCHIVE" "$URL"

# 4. Çıkart — zip içinden ${PLATFORM}-build-artifact/ klasörü çıkar,
#    onu sürüm adıyla $BASE altına taşı
echo "  [4/4] Çıkartılıyor..."
TMPDIR="/tmp/vault-extract"
rm -rf "$TMPDIR"
mkdir -p "$TMPDIR"
unzip -o "$ARCHIVE" -d "$TMPDIR" 2>/dev/null || tar -xf "$ARCHIVE" -C "$TMPDIR" 2>/dev/null
rm -f "$ARCHIVE"

INNER=$(ls -d "$TMPDIR"/*/ 2>/dev/null | head -1)
if [ -n "$INNER" ]; then
    mv "$INNER" "$DEST"
else
    mkdir -p "$DEST"
    mv "$TMPDIR"/* "$DEST"/ 2>/dev/null || true
fi
rm -rf "$TMPDIR"

# macOS'te otomatik /Applications kopyası
if [ "$PLATFORM" = "macos" ] && [ -d "$DEST/Vault.app" ]; then
    cp -R "$DEST/Vault.app" "/Applications/Vault.app" 2>/dev/null && \
    echo "  /Applications/Vault.app kopyalandı."
fi

# PATH'e ekle (kabuk konfigürasyonuna yaz)
if [ "$PLATFORM" = "linux" ]; then
    PROFILE_FILE="$HOME/.bashrc"
    if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
        PROFILE_FILE="$HOME/.zshrc"
    fi
    if ! grep -qxF "export PATH=\"$DEST:\$PATH\"" "$PROFILE_FILE" 2>/dev/null; then
        echo "" >> "$PROFILE_FILE"
        echo "# Vault" >> "$PROFILE_FILE"
        echo "export PATH=\"$DEST:\$PATH\"" >> "$PROFILE_FILE"
        echo "  PATH'e eklendi: $DEST"
        echo "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
    else
        echo "  $DEST zaten PATH'te mevcut."
    fi
fi

# macOS PATH
if [ "$PLATFORM" = "macos" ]; then
    PROFILE_FILE="$HOME/.zshrc"
    if ! grep -qxF "export PATH=\"$DEST:\$PATH\"" "$PROFILE_FILE" 2>/dev/null; then
        echo "" >> "$PROFILE_FILE"
        echo "# Vault" >> "$PROFILE_FILE"
        echo "export PATH=\"$DEST:\$PATH\"" >> "$PROFILE_FILE"
        echo "  PATH'e eklendi: $DEST"
        echo "  (Değişiklik yeni terminal pencerelerinde geçerli olacaktır.)"
    else
        echo "  $DEST zaten PATH'te mevcut."
    fi
fi

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │         KURULUM TAMAMLANDI           │"
echo "  └──────────────────────────────────────┘"
echo ""
echo "  Konum: $DEST"
echo "  Çalıştırmak için: vault run --desktop"
echo ""

# Mevcut oturumda geçerli olsun diye
export PATH="$DEST:$PATH"
