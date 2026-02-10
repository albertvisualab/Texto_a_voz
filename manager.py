import os
import json
import time
import re
import soundfile as sf
import numpy as np
from kokoro_onnx import Kokoro
import io
import threading

class BatchManager:
    def __init__(self, projects_dir, model_path, voices_path):
        self.projects_dir = projects_dir
        os.makedirs(self.projects_dir, exist_ok=True)
        self.lock = threading.Lock() # Lock para Kokoro (generación)
        self.status_lock = threading.Lock() # Lock para archivos de estado (json)
        self.project_states = {} # Caché en memoria para evitar lecturas de disco constantes
        
        # Inicializar Kokoro una sola vez
        print(f"Cargando modelo Kokoro desde {model_path}...")
        self.kokoro = Kokoro(model_path, voices_path)
        print("Modelo cargado.")

    def _update_project_status(self, project_id, update_func):
        """
        Helper para actualizar el estado de un proyecto de forma atómica y segura para hilos.
        Recarga el estado de disco si no está en caché o si se quiere forzar la frescura,
        aplica la función de actualización, y persiste el resultado.
        """
        project_path = os.path.join(self.projects_dir, project_id)
        status_path = os.path.join(project_path, "status.json")
        
        with self.status_lock:
            # Siempre intentamos leer de disco para asegurar que tenemos los cambios de otros métodos
            # (como update_last_chunk o rename_project) si no confiamos plenamente en la caché
            try:
                if not os.path.exists(status_path):
                    return False
                with open(status_path, "r", encoding="utf-8") as f:
                    status = json.load(f)
            except Exception as e:
                print(f"Error leyendo status para {project_id}: {e}")
                return False
            
            # Aplicar la actualización
            # update_func debe recibir el dict status y modificarlo in-place
            result = update_func(status)
            
            # Persistir
            try:
                with open(status_path, "w", encoding="utf-8") as f:
                    json.dump(status, f)
                # Sincronizar caché si existe
                self.project_states[project_id] = status
                return result if result is not None else True
            except Exception as e:
                print(f"Error guardando status para {project_id}: {e}")
                return False

    def _get_voice_style(self, voice_spec):
        """
        Obtiene el estilo de voz. Soporta:
        1. Nombre de voz simple: "af_bella"
        2. Mezcla de voces: "ef_dora:0.7,em_alex:0.3"
        """
        if "," in voice_spec or ":" in voice_spec:
            try:
                # Caso de mezcla: "v1:w1,v2:w2"
                parts = voice_spec.split(",")
                total_style = None
                total_weight = 0
                
                for part in parts:
                    if ":" in part:
                        v_name, weight_str = part.split(":")
                        weight = float(weight_str)
                    else:
                        v_name = part
                        weight = 1.0 # Default si no hay peso
                    
                    style = self.kokoro.get_voice_style(v_name.strip())
                    if total_style is None:
                        total_style = style * weight
                    else:
                        total_style += style * weight
                    total_weight += weight
                
                # Normalizar pesos
                if total_weight > 0:
                    total_style = total_style / total_weight
                return total_style
            except Exception as e:
                print(f"Error parseando mezcla de voz '{voice_spec}': {e}. Usando voz por defecto.")
                return "af_bella" # Fallback
        
        # Caso normal: solo el nombre de la voz
        return voice_spec

    def _generate_audio_safe(self, text, voice_spec, speed, lang, debug_id=""):
        """
        Genera audio dividiendo el texto en sub-chunks si es necesario para evitar 
        el límite de fonemas de Kokoro y limpia caracteres no soportados.
        """
        # 1. Pre-limpieza: Quitar caracteres no soportados (como script Tibetano)
        # Mantenemos caracteres latinos, puntuación común, CJK y símbolos básicos.
        clean_text = re.sub(r'[^\u0000-\u024F\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u3000-\u30FF\u4E00-\u9FFF\u2000-\u206F！？。，、；：]', ' ', text)
        
        # 2. Dividir texto en sub-chunks seguros (~250 caracteres max)
        max_chars = 250
        
        def split_text(t, limit):
            if len(t) <= limit:
                return [t]
            # Intentar por puntos
            parts = re.split(r'((?<=[.!?])\s+)', t)
            if len(parts) > 1:
                res = []
                curr = ""
                # Cada parte impar es el separador (\s+)
                for i in range(0, len(parts), 2):
                    p = parts[i]
                    sep = parts[i+1] if i+1 < len(parts) else ""
                    combined = p + sep
                    if len(curr) + len(combined) <= limit:
                        curr += combined
                    else:
                        if curr: res.append(curr.strip())
                        if len(combined) > limit:
                            # Si incluso una sola frase es larga, forzar subdivisión
                            if len(p) > limit:
                                res.extend(split_text(p, limit))
                                curr = sep # Ver si el separador cabe en el siguiente
                            else:
                                res.append(combined.strip())
                                curr = ""
                        else:
                            curr = combined
                if curr: res.append(curr.strip())
                return [r for r in res if r]

            # Intentar por comas, etc.
            parts = re.split(r'((?<=[,;:])\s+)', t)
            if len(parts) > 1:
                res = []
                curr = ""
                for i in range(0, len(parts), 2):
                    p = parts[i]
                    sep = parts[i+1] if i+1 < len(parts) else ""
                    combined = p + sep
                    if len(curr) + len(combined) <= limit:
                        curr += combined
                    else:
                        if curr: res.append(curr.strip())
                        if len(combined) > limit:
                            if len(p) > limit:
                                res.extend(split_text(p, limit))
                                curr = sep
                            else:
                                res.append(combined.strip())
                                curr = ""
                        else:
                            curr = combined
                if curr: res.append(curr.strip())
                return [r for r in res if r]
            
            # Hard cut
            return [t[i:i+limit] for i in range(0, len(t), limit)]

        sub_chunks = split_text(clean_text, max_chars)
        if debug_id:
            print(f"Generando {len(sub_chunks)} sub-partes para ID {debug_id}...")
        
        all_samples = []
        metadata = []
        sample_rate = 24000
        voice_obj = self._get_voice_style(voice_spec)

        for i, sub_text in enumerate(sub_chunks):
            if not sub_text.strip(): continue
            
            # Evitar logs excesivos en producción, solo debug si hay más de 1
            if len(sub_chunks) > 1:
                print(f"  > Sub-parte {i+1}/{len(sub_chunks)}...")
            
            samples, sr = self.kokoro.create(sub_text, voice=voice_obj, speed=speed, lang=lang)
            
            duration = len(samples) / sr
            metadata.append({"text": sub_text, "duration": duration})
            all_samples.append(samples)
            sample_rate = sr
            
        if not all_samples:
            # Fallback si no hay texto procesable (no debería pasar)
            return [], np.array([], dtype=np.float32), 24000
            
        return metadata, np.concatenate(all_samples), sample_rate

    def create_project(self, name, chunks, voice, speed, lang):
        # Sanitizar nombre para evitar errores en Windows
        # 1. Eliminar caracteres de control (como \n, \r, \t)
        clean_name = "".join(c for c in name if c.isprintable())
        # 2. Eliminar caracteres no permitidos en Windows: \ / : * ? " < > |
        clean_name = re.sub(r'[\\/:*?"<>|]', '', clean_name)
        # 3. Reemplazar espacios por guiones bajos y limpiar extremos
        clean_name = clean_name.replace(' ', '_').strip(' ._')
        # 4. Limitar longitud para evitar problemas de ruta larga
        clean_name = clean_name[:50]
        
        project_id = f"{int(time.time())}_{clean_name}"
        project_path = os.path.join(self.projects_dir, project_id)
        os.makedirs(project_path, exist_ok=True)
        os.makedirs(os.path.join(project_path, "audio_chunks"), exist_ok=True)

        status = {
            "name": name,
            "voice": voice,
            "speed": speed,
            "lang": lang,
            "total_chunks": len(chunks),
            "completed_chunks": 0,
            "last_chunk": 0,
            "is_finished": False,
            "chunks": [{"id": i, "text": text, "status": "pending"} for i, text in enumerate(chunks)]
        }

        with self.status_lock:
            with open(os.path.join(project_path, "status.json"), "w", encoding="utf-8") as f:
                json.dump(status, f) # Sin indentación para velocidad
        
        return project_id

    def get_projects(self):
        projects = []
        for pid in os.listdir(self.projects_dir):
            status_path = os.path.join(self.projects_dir, pid, "status.json")
            if os.path.exists(status_path):
                with self.status_lock:
                    try:
                        with open(status_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            data["id"] = pid
                            projects.append(data)
                    except Exception as e:
                        print(f"Error leyendo proyecto {pid}: {e}")
        return projects

    def get_project(self, project_id):
        status_path = os.path.join(self.projects_dir, project_id, "status.json")
        if os.path.exists(status_path):
            with self.status_lock:
                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["id"] = project_id
                        return data
                except Exception as e:
                    print(f"Error leyendo proyecto {project_id}: {e}")
        return None

    def process_chunk(self, project_id, chunk_id):
        project_path = os.path.join(self.projects_dir, project_id)
        chunk_filename = f"chunk_{chunk_id}.wav"
        chunk_path = os.path.join(project_path, "audio_chunks", chunk_filename)

        # FAST-PATH: Si el archivo ya existe en disco, no hacer nada más
        if os.path.exists(chunk_path):
            return chunk_id

        # 1. Obtener texto y parámetros bajo lock de Kokoro (solo uno genera a la vez)
        with self.lock:
            # Re-verificar si ya se generó mientras esperábamos el lock
            if os.path.exists(chunk_path):
                return chunk_id

            # Obtener datos del proyecto
            project = self.get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            if project.get("is_optimized"):
                return chunk_id

            chunk = next((c for c in project["chunks"] if c["id"] == chunk_id), None)
            if not chunk:
                raise ValueError(f"Chunk {chunk_id} not found in project {project_id}")

            if chunk["status"] == "completed":
                return chunk_id

            try:
                # Generar audio
                metadata, combined_samples, sample_rate = self._generate_audio_safe(
                    chunk["text"], 
                    project["voice"], 
                    project["speed"], 
                    project["lang"],
                    chunk_id
                )
                
                # Guardar el audio
                sf.write(chunk_path, combined_samples, sample_rate)
                
                # Guardar metadata para Karaoke
                meta_path = chunk_path.replace(".wav", ".json")
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f)
                
                # 2. Actualizar estado de forma atómica usando el helper
                def update_chunk_status(status):
                    # Encontrar el chunk en el nuevo status (que viene de disco)
                    c = next((ch for ch in status["chunks"] if ch["id"] == chunk_id), None)
                    if c:
                        c["status"] = "completed"
                    
                    status["completed_chunks"] = sum(1 for ch in status["chunks"] if ch["status"] == "completed")
                    
                    if status["completed_chunks"] == status["total_chunks"]:
                        # No llamamos a assemble_audio dentro del lock de status para evitar interbloqueos
                        # Lo haremos después de liberar el lock si es necesario
                        status["_needs_assembly"] = True
                    return True

                self._update_project_status(project_id, update_chunk_status)
                
                # Verificar si hace falta ensamblar (fuera del _update_project_status pero aún bajo self.lock)
                p_updated = self.get_project(project_id)
                if p_updated and p_updated.get("_needs_assembly"):
                    def clear_assembly_flag(status):
                        status.pop("_needs_assembly", None)
                        status["is_finished"] = True
                    self._update_project_status(project_id, clear_assembly_flag)
                    self.assemble_audio(project_id)

                return chunk_id
            except Exception as e:
                print(f"Error procesando chunk {chunk_id}: {e}")
                def mark_error(status):
                    c = next((ch for ch in status["chunks"] if ch["id"] == chunk_id), None)
                    if c: c["status"] = "error"
                self._update_project_status(project_id, mark_error)
                raise e

    def process_next_chunk(self, project_id):
        project = self.get_project(project_id)
        if not project or project["is_finished"]:
            return None

        # Buscar el primer chunk pendiente
        next_chunk = next((c for c in project["chunks"] if c["status"] == "pending"), None)
        
        if not next_chunk:
            def mark_finished(status):
                status["is_finished"] = True
            self._update_project_status(project_id, mark_finished)
            self.assemble_audio(project_id)
            return None

        try:
            # Generar audio de forma segura
            metadata, combined_samples, sample_rate = self._generate_audio_safe(
                next_chunk["text"], 
                project["voice"], 
                project["speed"], 
                project["lang"],
                next_chunk["id"]
            )
            
            project_path = os.path.join(self.projects_dir, project_id)
            chunk_filename = f"chunk_{next_chunk['id']}.wav"
            chunk_path = os.path.join(project_path, "audio_chunks", chunk_filename)
            sf.write(chunk_path, combined_samples, sample_rate)
            
            # También guardar metadatos si es posible
            meta_path = chunk_path.replace(".wav", ".json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f)
            
            # Actualizar estado
            def update_status(status):
                c = next((ch for ch in status["chunks"] if ch["id"] == next_chunk["id"]), None)
                if c: c["status"] = "completed"
                status["completed_chunks"] = sum(1 for ch in status["chunks"] if ch["status"] == "completed")
                if status["completed_chunks"] == status["total_chunks"]:
                    status["_needs_assembly"] = True
            
            self._update_project_status(project_id, update_status)
            
            p_updated = self.get_project(project_id)
            if p_updated and p_updated.get("_needs_assembly"):
                def clear_flag(status):
                    status.pop("_needs_assembly", None)
                    status["is_finished"] = True
                self._update_project_status(project_id, clear_flag)
                self.assemble_audio(project_id)
                
            return next_chunk["id"]
        except Exception as e:
            print(f"Error procesando chunk {next_chunk['id']}: {e}")
            def mark_err(status):
                c = next((ch for ch in status["chunks"] if ch["id"] == next_chunk["id"]), None)
                if c: c["status"] = "error"
            self._update_project_status(project_id, mark_err)
            raise e

    def assemble_audio(self, project_id):
        project_path = os.path.join(self.projects_dir, project_id)
        audio_chunks_dir = os.path.join(project_path, "audio_chunks")
        output_path = os.path.join(project_path, "final_output.wav")
        
        # Cargar el archivo de estado para saber el orden y los datos
        status = self.get_project(project_id)
        if not status:
            print(f"Error: No se encontró status para {project_id}")
            return

        print(f"Ensamblando audio para {project_id} ({status['total_chunks']} chunks)...")
        
        try:
            # Obtener propiedades del primer chunk para configurar el archivo de salida
            first_chunk_path = os.path.join(audio_chunks_dir, "chunk_0.wav")
            if not os.path.exists(first_chunk_path):
                # Buscar el primer chunk disponible si el 0 no está
                available_chunks = sorted([f for f in os.listdir(audio_chunks_dir) if f.endswith(".wav")])
                if not available_chunks:
                    print("No hay chunks de audio para ensamblar.")
                    return
                first_chunk_path = os.path.join(audio_chunks_dir, available_chunks[0])

            # Leer info del primer chunk
            info = sf.info(first_chunk_path)
            samplerate = info.samplerate
            channels = info.channels
            subtype = info.subtype

            # Abrir el archivo de salida para escritura incremental
            with sf.SoundFile(output_path, mode='w', samplerate=samplerate, channels=channels, subtype=subtype) as outfile:
                for chunk in status["chunks"]:
                    chunk_id = chunk["id"]
                    chunk_path = os.path.join(audio_chunks_dir, f"chunk_{chunk_id}.wav")
                    
                    if os.path.exists(chunk_path):
                        data, sr = sf.read(chunk_path)
                        outfile.write(data)
                    else:
                        print(f"Advertencia: Chunk {chunk_id} no encontrado durante el ensamblado.")

            print(f"Audio final ensamblado exitosamente en: {output_path}")
            
            # Actualizar estado final de forma atómica
            def mark_optimized(s):
                if s.get("completed_chunks", 0) >= s.get("total_chunks", 0):
                    s["is_finished"] = True
                    s["is_optimized"] = True
                    return True
                return False

            if self._update_project_status(project_id, mark_optimized):
                print(f"Proyecto {project_id} marcado como optimizado. Los chunks se mantienen para streaming/karaoke.")
                    
        except Exception as e:
            print(f"Error crítico durante el ensamblado de audio: {e}")
            raise e

    def delete_project(self, project_id):
        import shutil
        project_path = os.path.join(self.projects_dir, project_id)
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
            print(f"Proyecto {project_id} eliminado.")
            return True
    def rename_project(self, project_id, new_name):
        def update_name(status):
            status["name"] = "".join(c for c in new_name if c.isprintable())
        return self._update_project_status(project_id, update_name)

    def update_last_chunk(self, project_id, last_chunk):
        def update_lc(status):
            status["last_chunk"] = last_chunk
        return self._update_project_status(project_id, update_lc)

    def import_project(self, name, chunks, audio_path, voice, speed, lang):
        """
        Importa un archivo de audio externo y lo prepara para karaoke
        estimando los tiempos de sincronización basados en la longitud del texto.
        Mucho más rápido que generar audio IA para estimar.
        """
        import shutil
        import re
        
        # 1. Crear proyecto normal
        project_id = self.create_project(name, chunks, voice, speed, lang)
        project_path = os.path.join(self.projects_dir, project_id)
        final_output_path = os.path.join(project_path, "final_output.wav")
        
        # 2. Mover el audio original a final_output.wav
        shutil.copy(audio_path, final_output_path)
        
        # 3. Leer el audio original para obtener su duración real
        try:
            info = sf.info(final_output_path)
            sr_original = info.samplerate
            total_duration_real = info.duration
            channels = info.channels
            subtype = info.subtype
        except Exception as e:
            print(f"Error leyendo info de audio importado: {e}")
            return None

        # 4. Calcular pesos de cada chunk basados en longitud de caracteres
        all_text = "".join(chunks)
        total_chars = len(all_text)
        if total_chars == 0: return project_id
        
        audio_chunks_dir = os.path.join(project_path, "audio_chunks")
        current_pos_seconds = 0
        
        # Abrir el audio completo para ir troceándolo
        try:
            full_audio, _ = sf.read(final_output_path)
            if len(full_audio.shape) > 1:
                # Mantener canales originales si es posible para el troceado
                pass
        except Exception as e:
            print(f"Error cargando audio para troceo: {e}")
            return None

        print(f"Importando audio: {total_duration_real:.2f}s, {len(chunks)} fragmentos.")

        for i, chunk_text in enumerate(chunks):
            # Duración proporcional de este chunk
            chunk_ratio = len(chunk_text) / total_chars
            chunk_duration = chunk_ratio * total_duration_real
            
            # Extraer y guardar el chunk.wav
            start_sample = int(current_pos_seconds * sr_original)
            end_sample = int((current_pos_seconds + chunk_duration) * sr_original)
            
            if i == len(chunks) - 1:
                end_sample = len(full_audio)
                
            chunk_samples = full_audio[start_sample:end_sample]
            chunk_wav_path = os.path.join(audio_chunks_dir, f"chunk_{i}.wav")
            sf.write(chunk_wav_path, chunk_samples, sr_original)
            
            # Generar metadatos de Karaoke (Sub-chunks) basándose en oraciones
            # Dividimos el chunk en oraciones simples
            sub_texts = re.split(r'((?<=[.!?])\s+)', chunk_text)
            metadata = []
            
            # Limpiar y agrupar (re.split devuelve los separadores como elementos impares)
            actual_sub_texts = []
            for j in range(0, len(sub_texts), 2):
                t = sub_texts[j]
                sep = sub_texts[j+1] if j+1 < len(sub_texts) else ""
                combined = (t + sep).strip()
                if combined:
                    actual_sub_texts.append(combined)
            
            chunk_chars = sum(len(s) for s in actual_sub_texts)
            if chunk_chars > 0:
                for sub in actual_sub_texts:
                    sub_ratio = len(sub) / chunk_chars
                    sub_duration = sub_ratio * chunk_duration
                    metadata.append({
                        "text": sub,
                        "duration": sub_duration
                    })
            
            # Guardar chunk.json
            chunk_json_path = os.path.join(audio_chunks_dir, f"chunk_{i}.json")
            with open(chunk_json_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f)
            
            current_pos_seconds += chunk_duration

        # 5. Marcar como completado y optimizado
        def finalize(status):
            for c in status["chunks"]:
                c["status"] = "completed"
            status["completed_chunks"] = len(chunks)
            status["is_finished"] = True
            status["is_optimized"] = True
            return True
            
        self._update_project_status(project_id, finalize)
        print(f"Importación de '{name}' completada instantáneamente.")
        return project_id
