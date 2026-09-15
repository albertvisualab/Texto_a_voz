import os
import io
import wave
import numpy as np
import onnxruntime as ort

class CatalanEngine:
    """
    Motor de síntesi de veu en català 100% en local.
    Suporta tant Matxa-TTS v2 (Projecte AINA / BSC) amb 4 dialectes com Piper-TTS (UPC / AINA).
    """

    # Diccionari de grafemes per a Matxa-TTS v2
    _PAD = '_'
    _PUNCTUATION = ';:,.!?¡¿—…"«»“”()- '
    _LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    _LETTERS_IPA = (
        'ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞↓↑→↗↘\'̩\'ᵻ'
    )
    _LETTERS_ACCENTED = 'àáèéìíòóùú·üïöñ’#´'
    SYMBOLS_MATXA = [_PAD] + list(_PUNCTUATION) + list(_LETTERS) + list(_LETTERS_IPA) + list(_LETTERS_ACCENTED)
    MATXA_VOCAB_MAP = {s: i for i, s in enumerate(SYMBOLS_MATXA)}

    # Mapeig de veus Matxa a speaker IDs oficials
    MATXA_SPEAKERS = {
        "ca_matxa_olga": 0,   # Balear Femenina
        "ca_matxa_quim": 1,   # Balear Masculina
        "ca_matxa_elia": 2,   # Central Femenina
        "ca_matxa_grau": 3,   # Central Masculina
        "ca_matxa_emma": 4,   # Nord-occidental Femenina
        "ca_matxa_pere": 5,   # Nord-occidental Masculina
        "ca_matxa_gina": 6,   # Valencià Femenina
        "ca_matxa_lluc": 7,   # Valencià Masculina
    }

    # Mapeig de veus Piper
    PIPER_VOICES = {
        "ca_piper_ona": ("ca_ES-upc_ona-medium.onnx", "ca_ES-upc_ona-medium.onnx.json"),
        "ca_piper_pau": ("ca_ES-upc_pau-x_low.onnx", "ca_ES-upc_pau-x_low.onnx.json"),
    }

    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "ca")
        self.models_dir = models_dir

        self.matxa_session = None
        self.piper_voices = {}

        self.matxa_model_path = os.path.join(self.models_dir, "matxa_v2_multiaccent.onnx")

    def _get_matxa_session(self):
        if self.matxa_session is None:
            if not os.path.exists(self.matxa_model_path):
                raise FileNotFoundError(f"No s'ha trobat el model Matxa a {self.matxa_model_path}")
            # Configurar opcions d'ONNX per a CPU
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.matxa_session = ort.InferenceSession(self.matxa_model_path, sess_options=opts, providers=['CPUExecutionProvider'])
        return self.matxa_session

    def _get_piper_voice(self, voice_id):
        if voice_id not in self.piper_voices:
            if voice_id not in self.PIPER_VOICES:
                raise ValueError(f"Veu Piper desconeguda: {voice_id}")
            
            onnx_name, json_name = self.PIPER_VOICES[voice_id]
            onnx_path = os.path.join(self.models_dir, onnx_name)
            json_path = os.path.join(self.models_dir, json_name)

            if not os.path.exists(onnx_path):
                raise FileNotFoundError(f"No s'ha trobat el model Piper {onnx_name} a {self.models_dir}")

            from piper import PiperVoice
            self.piper_voices[voice_id] = PiperVoice.load(onnx_path, config_path=json_path if os.path.exists(json_path) else None)
        return self.piper_voices[voice_id]

    def is_catalan_voice(self, voice_id):
        if not voice_id:
            return False
        return voice_id.startswith("ca_") or voice_id in self.MATXA_SPEAKERS or voice_id in self.PIPER_VOICES

    def get_available_voices(self):
        voices = []
        # Matxa AINA voices
        matxa_labels = {
            "ca_matxa_elia": ("Catalan (Central - Èlia)", "ca", "Catalan (Central - AINA)"),
            "ca_matxa_grau": ("Catalan (Central - Grau)", "ca", "Catalan (Central - AINA)"),
            "ca_matxa_olga": ("Catalan (Balear - Olga)", "ca", "Catalan (Balear - AINA)"),
            "ca_matxa_quim": ("Catalan (Balear - Quim)", "ca", "Catalan (Balear - AINA)"),
            "ca_matxa_emma": ("Catalan (Nord-occidental - Emma)", "ca", "Catalan (Nord-occidental - AINA)"),
            "ca_matxa_pere": ("Catalan (Nord-occidental - Pere)", "ca", "Catalan (Nord-occidental - AINA)"),
            "ca_matxa_gina": ("Catalan (Valencià - Gina)", "ca", "Catalan (Valencià - AINA)"),
            "ca_matxa_lluc": ("Catalan (Valencià - Lluc)", "ca", "Catalan (Valencià - AINA)"),
        }
        for vid, (label, lang, grp) in matxa_labels.items():
            voices.append({"id": vid, "label": label, "lang": lang, "group": grp})

        # Piper UPC voices
        piper_labels = {
            "ca_piper_ona": ("Catalan (UPC - Ona)", "ca", "Catalan (UPC - Piper)"),
            "ca_piper_pau": ("Catalan (UPC - Pau)", "ca", "Catalan (UPC - Piper)"),
        }
        for vid, (label, lang, grp) in piper_labels.items():
            voices.append({"id": vid, "label": label, "lang": lang, "group": grp})

        return voices

    def generate(self, text, voice_id="ca_matxa_elia", speed=1.0):
        """
        Sintetitza text a àudio en català.
        Retorna (samples_np_float32, sample_rate).
        """
        text = text.strip()
        if not text:
            return np.array([], dtype=np.float32), 22050

        # Normalitzar velocitat
        speed = max(0.5, min(float(speed), 2.0))

        if voice_id in self.MATXA_SPEAKERS:
            return self._generate_matxa(text, voice_id, speed)
        elif voice_id in self.PIPER_VOICES:
            return self._generate_piper(text, voice_id, speed)
        else:
            # Fallback a Elia per defecte
            return self._generate_matxa(text, "ca_matxa_elia", speed)

    def _generate_matxa(self, text, voice_id, speed):
        session = self._get_matxa_session()
        speaker_id = self.MATXA_SPEAKERS.get(voice_id, 2) # 2 = Elia

        # Mapejar caràcters a IDs
        sequence = [self.MATXA_VOCAB_MAP[c] for c in text if c in self.MATXA_VOCAB_MAP]
        if not sequence:
            sequence = [self.MATXA_VOCAB_MAP.get(' ', 0)]

        x = np.array([sequence], dtype=np.int64)
        x_lengths = np.array([len(sequence)], dtype=np.int64)

        # Scales: [noise_scale / temperature, length_scale]
        # length_scale inversament proporcional a la velocitat
        length_scale = float(1.0 / speed)
        scales = np.array([0.667, length_scale], dtype=np.float32)
        spks = np.array([speaker_id], dtype=np.int64)

        outputs = session.run(None, {
            'x': x,
            'x_lengths': x_lengths,
            'scales': scales,
            'spks': spks
        })

        waveform = outputs[1][0]
        # El model Matxa produeix a 22050 Hz
        sample_rate = 22050
        return waveform.astype(np.float32), sample_rate

    def _generate_piper(self, text, voice_id, speed):
        voice = self._get_piper_voice(voice_id)
        from piper.config import SynthesisConfig

        length_scale = float(1.0 / speed)
        syn_config = SynthesisConfig(length_scale=length_scale)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            voice.synthesize_wav(text, w, syn_config=syn_config, set_wav_format=True)

        buf.seek(0)
        with wave.open(buf, 'rb') as r:
            sample_rate = r.getframerate()
            frames = r.readframes(r.getnframes())
            audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0

        return audio_np, sample_rate
