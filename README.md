# Kokoro Pro AI TTS 🚀 (Alpha v0.2.0)

¡Un lector de documentos inteligente, persistente, local y gratuito con Karaoke sincronizado!

Esta aplicación utiliza el modelo de IA **Kokoro-82M** para convertir texto y documentos (PDF, Word, TXT) en voz humana de alta calidad. A diferencia de un simple conversor, esta versión permite **gestionar una biblioteca de lecturas**, **importar audios externos** y disfrutar de una experiencia visual sincronizada.

## ✨ Características Principales

- **Modo Lectura Surround (Karaoke) Sincronizado:** Visualiza el texto con resaltado dinámico. Ahora también compatible con audios importados.
- **Importación de Proyectos de Audio:** Sube tus propios archivos MP3/WAV junto con su texto para convertirlos en una experiencia de Karaoke instantánea.
- **Streaming Persistente:** Los fragmentos de audio (chunks) ya no se eliminan tras la conversión, permitiendo que la lectura fluida y el Karaoke continúen incluso después de generar el archivo completo.
- **Persistencia de Lectura (Last Chunk):** La aplicación ahora recuerda exactamente por qué parte del libro ibas, permitiéndote retomar la lectura donde la dejaste.
- **Motor de Karaoke Optimizado:** Estimación inteligente de tiempos basada en caracteres para importaciones ultrarrápidas.
- **100% Privado y Local:** Funciona totalmente offline, sin costes ni límites.

## 🛠️ Requisitos

1. **Python 3.10+** (Compatible con 3.13).
2. **eSpeak NG:** Necesario para la conversión de fonemas.
   - [Descargar eSpeak NG para Windows](https://github.com/espeak-ng/espeak-ng/releases).

## 🚀 Instalación y Uso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/0utKast666/Texto_a_voz.git
   cd Texto_a_voz
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuración de Modelos:**
   Asegúrate de tener `kokoro-v1.0.onnx` y `voices-v1.0.bin` en la raíz.

4. **Ejecutar:**
   Lanza `lanzar_app.bat` o `python app.py`. Abre `http://127.0.0.1:5000`.

## 📂 Estructura del Proyecto

- `app.py`: Servidor Flask (API REST) para gestión de sesiones y streaming.
- `manager.py`: Motor de procesamiento por lotes y gestión de estado con generación de metadatos para Karaoke.
- `processor.py`: Extracción de texto y segmentación inteligente.
- `templates/index.html`: UI moderna con feedback dinámico y Modo Lectura Surround.

## 📈 Historial de Versiones (Alpha)

- **v0.2.0 (Alpha):**
  - **Nueva Funcionalidad de Importación:** Soporte para subir archivos de audio externos (MP3/WAV) y sincronizarlos con texto para Karaoke.
  - **Streaming Persistente:** Los fragmentos de audio ya no se eliminan tras la conversión facilitando la lectura fluida post-procesado.
  - **Persistencia de Progreso:** La aplicación ahora recuerda el último fragmento leído por el usuario.
  - **Optimización de Karaoke:** Nuevo motor de estimación basado en longitud de texto para una sincronización instantánea en importaciones masivas.
  - **UI Refinada:** Integración de herramientas de importación y mejoras en la robustez del modo lectura.

- **v0.1.3 (Alpha):**
  - **Motor de Persistencia Atómica:** Solucionado problema de pérdida de progreso de lectura durante la generación de audio.
  - **Protección contra condiciones de carrera:** Implementado sistema de bloqueo y recarga de estado centralizado en el backend.
  - **Tests Automatizados:** Incluido script de prueba de concurrencia (`test_state_persistence.py`) para validación de estabilidad.

- **v0.1.2 (Alpha):**
  - **Nuevo: Modo Lectura (Karaoke)** con estética premium y resaltado sincronizado.
  - Implementación de metadatos de duración para cada fragmento de audio.
  - Nueva ruta API para metadatos de sincronización.
  - UI mejorada con controles de pausa en el modo lectura.

- **v0.1.1 (Alpha):**
  - Eliminado el límite de buffer: la conversión ahora es continua hasta el final del documento.
  - Disponibilidad inmediata de descarga: el botón WAV aparece en cuanto termina la conversión, aunque la lectura no haya acabado.

- **v0.1.0 (Alpha):** 
  - Añadida funcionalidad de renombrar sesiones.
  - Sincronización de nombre de archivo en descargas WAV.
  - Mejora drástica en el feedback del buffer (mensajes en tiempo real).
  - Corrección de bugs de autoplay y rutas de audio.
  - Voz "Em Alex" configurada por defecto.

---
Creado con ❤️ por **0utKast** para la comunidad de audiolibros offline.
