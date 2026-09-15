import os
import time
import json
import uuid
import threading
import queue
import shutil
import subprocess
from werkzeug.utils import secure_filename

class ConverterManager:
    def __init__(self, conversions_dir="conversions"):
        self.conversions_dir = conversions_dir
        os.makedirs(self.conversions_dir, exist_ok=True)
        self.conversion_queue = queue.Queue()
        self.is_running = False
        
        # Recargar tareas pendientes al iniciar
        self._load_pending_tasks()
        
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _load_pending_tasks(self):
        for d in os.listdir(self.conversions_dir):
            status = self.get_status(d)
            if status and status["status"] in ["pending", "processing"]:
                status["status"] = "pending"
                status["progress"] = 0
                self._save_status(d, status)
                self.conversion_queue.put(d)

    def add_task(self, file_path, original_filename, output_format, bitrate):
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(self.conversions_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        ext = os.path.splitext(original_filename)[1]
        input_path = os.path.join(task_dir, f"input{ext}")
        shutil.move(file_path, input_path)
        
        status = {
            "id": task_id,
            "original_filename": original_filename,
            "input_path": input_path,
            "output_format": output_format,
            "bitrate": bitrate,
            "status": "pending", 
            "progress": 0,
            "error": None,
            "created_at": time.time(),
            "output_path": None
        }
        self._save_status(task_id, status)
        self.conversion_queue.put(task_id)
        return task_id

    def get_status(self, task_id):
        status_path = os.path.join(self.conversions_dir, task_id, "status.json")
        if os.path.exists(status_path):
            with open(status_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def get_all_tasks(self):
        tasks = []
        if not os.path.exists(self.conversions_dir):
            return tasks
            
        for d in os.listdir(self.conversions_dir):
            status = self.get_status(d)
            if status:
                tasks.append(status)
        tasks.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return tasks

    def delete_task(self, task_id):
        task_dir = os.path.join(self.conversions_dir, task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            return True
        return False

    def _save_status(self, task_id, status):
        status_path = os.path.join(self.conversions_dir, task_id, "status.json")
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=4)

    def _worker_loop(self):
        while True:
            if not self.is_running:
                time.sleep(1)
                continue
                
            try:
                task_id = self.conversion_queue.get(timeout=1)
            except queue.Empty:
                continue

            if not self.is_running:
                # Si se pausó mientras esperábamos, lo devolvemos a la cola
                self.conversion_queue.put(task_id)
                continue

            status = self.get_status(task_id)
            if not status or status["status"] == "completed":
                self.conversion_queue.task_done()
                continue
                
            status["status"] = "processing"
            status["progress"] = 0
            self._save_status(task_id, status)
            
            try:
                out_format = status["output_format"]
                ext_map = {"wav": ".wav", "mp3": ".mp3", "opus": ".ogg", "m4a": ".m4a"}
                target_ext = ext_map.get(out_format, ".wav")
                
                input_path = status["input_path"]
                task_dir = os.path.join(self.conversions_dir, task_id)
                base_name = os.path.splitext(status["original_filename"])[0]
                output_filename = f"{base_name}{target_ext}"
                output_path = os.path.join(task_dir, output_filename)
                
                # Obtener duración para porcentaje
                cmd_probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
                try:
                    duration_s = float(subprocess.check_output(cmd_probe).decode('utf-8').strip())
                    total_us = duration_s * 1000000
                except:
                    total_us = 1
                
                # Comando FFmpeg
                cmd = ["ffmpeg", "-y", "-i", input_path]
                if out_format == "mp3":
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", status["bitrate"]])
                elif out_format == "opus":
                    cmd.extend(["-c:a", "libopus", "-b:a", status["bitrate"]])
                elif out_format == "m4a":
                    cmd.extend(["-c:a", "aac", "-b:a", status["bitrate"]])
                
                cmd.extend(["-progress", "pipe:1", output_path])
                
                print(f"[Converter] Iniciando ffmpeg para {task_id}")
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                
                last_progress = 0
                for line in process.stdout:
                    # Pausa forzada: ffmpeg no se puede pausar fácilmente, pero si el usuario para la cola, 
                    # matamos el proceso para retomarlo después desde 0.
                    if not self.is_running:
                        process.kill()
                        raise Exception("Pausado por el usuario. Se reiniciará al continuar.")
                        
                    if "out_time_us=" in line:
                        time_us_str = line.split("=")[1].strip()
                        if time_us_str.lstrip('-').isdigit():
                            current_us = float(time_us_str)
                            if current_us > 0 and total_us > 0:
                                pct = min(99, int((current_us / total_us) * 100))
                                if pct > last_progress + 2: # Solo guardar cada 2% para no saturar I/O
                                    last_progress = pct
                                    status["progress"] = pct
                                    self._save_status(task_id, status)
                
                process.wait()
                if process.returncode != 0 and process.returncode is not None:
                    raise Exception(f"FFmpeg devolvió error {process.returncode}")
                
                status["status"] = "completed"
                status["progress"] = 100
                status["output_path"] = output_filename
                self._save_status(task_id, status)
                print(f"[Converter] Tarea {task_id} completada.")
                
            except Exception as e:
                print(f"[Converter] Error en tarea {task_id}: {e}")
                if "Pausado por el usuario" in str(e):
                    status["status"] = "pending"
                    status["progress"] = 0
                    self.conversion_queue.put(task_id)
                else:
                    status["status"] = "error"
                    status["error"] = str(e)
                self._save_status(task_id, status)
                
            finally:
                self.conversion_queue.task_done()
