@echo off
cd /d "%~dp0"
title AlbertVisuaLab - Requirements & Models Installer

echo ===================================================
echo   AlbertVisuaLab - Instal·lació de Dependències i Models
echo ===================================================
echo.

:: 1. Instal·lar llibreries de Python
echo [+] Instal·lant llibreries des de requirements.txt...
"C:\Users\alber\AppData\Local\Programs\Python\Python310\python.exe" -m pip install -r requirements.txt

:: 2. Blindatge de seguretat per al mòdul de PDF
echo.
echo [+] Executant blindatge per a mòduls de PDF...
"C:\Users\alber\AppData\Local\Programs\Python\Python310\python.exe" -m pip uninstall fitz -y >nul 2>&1
"C:\Users\alber\AppData\Local\Programs\Python\Python310\python.exe" -m pip install PyMuPDF

:: 3. Descàrrega automàtica de models si no existeixen
echo.
echo [+] Comprovant fitxers de models d'IA...

if not exist "kokoro-v1.0.onnx" (
    echo [!] Falta kokoro-v1.0.onnx. Descarregant des de la font oficial (310MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' -OutFile 'kokoro-v1.0.onnx'"
    echo [^✓] Model ONNX descarregat.
) else (
    echo [^✓] Fitxer kokoro-v1.0.onnx ja present a l'SSD.
)

if not exist "voices-v1.0.bin" (
    echo [!] Falta voices-v1.0.bin. Descarregant (27MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile 'voices-v1.0.bin'"
    echo [^✓] Fitxer de veus descarregat.
) else (
    echo [^✓] Fitxer voices-v1.0.bin ja present a l'SSD.
)

echo.
echo ===================================================
echo   [OK] Entorn i models configurats correctament.
echo ===================================================
pause