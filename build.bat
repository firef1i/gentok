@echo off
REM Build etoken app for Windows using PyInstaller
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo === etoken build (Windows) ===

echo [1/4] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo [2/4] Installing Playwright Chromium...
python -m playwright install chromium

echo [3/4] Running PyInstaller...
pyinstaller etoken.spec --clean --noconfirm

echo [4/4] Creating zip archive...
cd dist
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set ZIP_NAME=etoken-win-%datetime:~0,8%-%datetime:~8,6%.zip
powershell -Command "Compress-Archive -Path 'etoken' -DestinationPath '!ZIP_NAME!' -Force"
echo Archive created: dist\!ZIP_NAME!

cd ..
echo.
echo === Build complete ===
echo Output: dist\etoken\
echo Archive: dist\!ZIP_NAME!
echo.
echo To test: dist\etoken\etoken.exe

endlocal
