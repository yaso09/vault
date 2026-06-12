@echo off
setlocal enabledelayedexpansion

title Vault Kurulumu — Windows
cd /d "%~dp0"

set "REPO=yaso09/vault"
set "DEST=%APPDATA%\Vault"

echo.
echo  ^|======================================^|
echo  ^|       VAULT — Windows Kurulumu        ^|
echo  ^|======================================^|
echo.
echo  Hedef: %DEST%
echo.

REM GitHub API ile en son release bilgisini al
echo  [1/4] Sürüm bilgisi alınıyor...
for /f "delims=" %%i in ('curl -sL "https://api.github.com/repos/%REPO%/releases/latest" ^| findstr /b "  \"tag_name\":"') do (
    set "line=%%i"
    set "line=!line:  \"tag_name\": "=!"
    set "line=!line:\",=!"
    set "TAG=!line!"
)
if "%TAG%"=="" (
    echo  Hata: Sürüm bilgisi alinamadi.
    pause
    exit /b 1
)
echo  Sürüm: %TAG%

REM Hedef klasörü hazırla
if exist "%DEST%" (
    echo  [2/4] Eski kurulum kaldiriliyor...
    rmdir /s /q "%DEST%" 2>nul
)
mkdir "%DEST%" 2>nul

REM Windows build'ini indir
set "URL=https://github.com/%REPO%/releases/download/%TAG%/windows-build-artifact.zip"
set "ARCHIVE=%TEMP%\vault-windows.zip"
echo  [3/4] Indiriliyor: %URL%
curl -sL -o "%ARCHIVE%" "%URL%"
if %ERRORLEVEL% neq 0 (
    echo  Hata: Indirme basarisiz.
    pause
    exit /b 1
)

REM Çıkart
echo  [4/4] %DEST% klasörüne çikartiliyor...
tar -xf "%ARCHIVE%" -C "%DEST%" 2>nul
if %ERRORLEVEL% neq 0 (
    powershell -command "Expand-Archive -Path '%ARCHIVE%' -DestinationPath '%DEST%' -Force" 2>nul
)
del "%ARCHIVE%" 2>nul

REM Kısayol oluştur (isteğe bağlı)
if exist "%DEST%\Vault.exe" (
    echo.
    powershell -command "$WS=New-Object -ComObject WScript.Shell; $SC=$WS.CreateShortcut('%USERPROFILE%\Desktop\Vault.lnk'); $SC.TargetPath='%DEST%\Vault.exe'; $SC.WorkingDirectory='%DEST%'; $SC.Save()" 2>nul
    echo  Masaustune kisa yol eklendi.
)
if exist "%DEST%\vault.exe" (
    echo.
    powershell -command "$WS=New-Object -ComObject WScript.Shell; $SC=$WS.CreateShortcut('%USERPROFILE%\Desktop\Vault.lnk'); $SC.TargetPath='%DEST%\vault.exe'; $SC.WorkingDirectory='%DEST%'; $SC.Save()" 2>nul
    echo  Masaustune kisa yol eklendi.
)

echo.
echo  ^|======================================^|
echo  ^|         KURULUM TAMAMLANDI           ^|
echo  ^|======================================^|
echo.
echo  Konum: %DEST%
echo.
pause
