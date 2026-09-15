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

:: 4. Models de Català (Projecte AINA i UPC)
echo.
echo [+] Comprovant models en Català (AINA / UPC)...
if not exist "models\ca" mkdir "models\ca"

if not exist "models\ca\matxa_v2_multiaccent.onnx" (
    echo [!] Falta matxa_v2_multiaccent.onnx. Descarregant Matxa-TTS v2 (~270MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/BSC-LT/matxa-tts-v2-ca-multiaccent-graphemes/resolve/main/matxa_v2_multiaccent_graphemes_20_steps_wavenext.onnx' -OutFile 'models\ca\matxa_v2_multiaccent.onnx'"
    echo [^✓] Model Matxa-TTS v2 descarregat.
) else (
    echo [^✓] Model Matxa-TTS v2 ja present a l'SSD.
)

if not exist "models\ca\ca_ES-upc_ona-medium.onnx" (
    echo [!] Descarregant veu Piper Ona (~60MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/ca/ca_ES/upc_ona/medium/ca_ES-upc_ona-medium.onnx' -OutFile 'models\ca\ca_ES-upc_ona-medium.onnx'"
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/ca/ca_ES/upc_ona/medium/ca_ES-upc_ona-medium.onnx.json' -OutFile 'models\ca\ca_ES-upc_ona-medium.onnx.json'"
    echo [^✓] Veu Piper Ona descarregada.
) else (
    echo [^✓] Veu Piper Ona ja present.
)

if not exist "models\ca\ca_ES-upc_pau-x_low.onnx" (
    echo [!] Descarregant veu Piper Pau (~60MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/ca/ca_ES/upc_pau/x_low/ca_ES-upc_pau-x_low.onnx' -OutFile 'models\ca\ca_ES-upc_pau-x_low.onnx'"
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/ca/ca_ES/upc_pau/x_low/ca_ES-upc_pau-x_low.onnx.json' -OutFile 'models\ca\ca_ES-upc_pau-x_low.onnx.json'"
    echo [^✓] Veu Piper Pau descarregada.
) else (
    echo [^✓] Veu Piper Pau ja present.
)

echo.
echo ===================================================
echo   [OK] Entorn i models configurats correctament.
echo ===================================================
pause