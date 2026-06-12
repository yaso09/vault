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

# Hedef klasör
if [ "$PLATFORM" = "macos" ]; then
    DEST="$HOME/Library/Application Support/Vault"
else
    DEST="${XDG_DATA_HOME:-$HOME/.local/share}/Vault"
fi

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │       VAULT — $PLATFORM Kurulumu        │"
echo "  └──────────────────────────────────────┘"
echo ""
echo "  Hedef: $DEST"
echo ""

# 1. GitHub API ile en son release bilgisi
echo "  [1/4] Sürüm bilgisi alınıyor..."
TAG=$(curl -sL "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": "//;s/",//')
if [ -z "$TAG" ]; then
    echo "  Hata: Sürüm bilgisi alınamadı."
    exit 1
fi
echo "  Sürüm: $TAG"

# 2. Hedef klasörü hazırla
if [ -d "$DEST" ]; then
    echo "  [2/4] Eski kurulum kaldırılıyor..."
    rm -rf "$DEST"
fi
mkdir -p "$DEST"

# 3. Build'i indir
URL="https://github.com/$REPO/releases/download/$TAG/$PLATFORM"
ARCHIVE="/tmp/vault-$PLATFORM.zip"
echo "  [3/4] İndiriliyor: $URL"
curl -sL -o "$ARCHIVE" "$URL"

# 4. Çıkart
echo "  [4/4] $DEST klasörüne çıkartılıyor..."
unzip -o "$ARCHIVE" -d "$DEST" 2>/dev/null || tar -xf "$ARCHIVE" -C "$DEST" 2>/dev/null
rm -f "$ARCHIVE"

# macOS'te otomatik /Applications kopyası
if [ "$PLATFORM" = "macos" ] && [ -d "$DEST/Vault.app" ]; then
    cp -R "$DEST/Vault.app" "/Applications/Vault.app" 2>/dev/null && \
    echo "  /Applications/Vault.app kopyalandı."
fi

# Kısayol / PATH önerisi
if [ "$PLATFORM" = "linux" ] && [ -f "$DEST/vault" ]; then
    ln -sf "$DEST/vault" "$HOME/.local/bin/vault" 2>/dev/null && \
    echo "  ~/.local/bin/vault sembolik linki oluşturuldu."
fi

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │         KURULUM TAMAMLANDI           │"
echo "  └──────────────────────────────────────┘"
echo ""
echo "  Konum: $DEST"
echo "  Çalıştırmak için: $DEST/vault"
echo ""
