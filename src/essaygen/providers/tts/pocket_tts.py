from pathlib import Path
from typing import Any, Callable

_BUILTIN_VOICES = {
    "alba", "anna", "azelma", "bill_boerst", "caro_davy", "charles", "cosette",
    "eponine", "eve", "fantine", "george", "jane", "jean", "javert", "marius",
    "mary", "michael", "paul", "peter_yearsley", "stuart_bell", "vera",
    "giovanni", "lola", "juergen", "rafael", "estelle",
}


def resolve_voice_cache_path(voice: str, cache_dir: Path) -> Path | None:
    if voice in _BUILTIN_VOICES:
        return None
    return cache_dir / f"{Path(voice).stem}.safetensors"


class PocketTTSProvider:
    name = "pocket_tts"

    def __init__(
        self,
        voice: str = "alba",
        model: Any = None,
        wav_writer: Callable | None = None,
        voice_cache_path: Path | None = None,
        export_model_state: Callable | None = None,
    ):
        self._voice = voice
        self._model = model
        self._voice_state = None
        self._wav_writer = wav_writer
        self._voice_cache_path = voice_cache_path
        self._export_model_state = export_model_state

    @property
    def model(self) -> Any:
        if self._model is None:
            from pocket_tts import TTSModel

            self._model = TTSModel.load_model()
        return self._model

    @property
    def wav_writer(self) -> Callable:
        if self._wav_writer is None:
            import scipy.io.wavfile

            self._wav_writer = scipy.io.wavfile.write
        return self._wav_writer

    @property
    def export_model_state(self) -> Callable:
        if self._export_model_state is None:
            from pocket_tts import export_model_state

            self._export_model_state = export_model_state
        return self._export_model_state

    def _get_voice_state(self) -> Any:
        if self._voice_state is not None:
            return self._voice_state

        if self._voice_cache_path is not None and self._voice_cache_path.exists():
            self._voice_state = self.model.get_state_for_audio_prompt(str(self._voice_cache_path))
        else:
            self._voice_state = self.model.get_state_for_audio_prompt(self._voice)
            if self._voice_cache_path is not None:
                self._voice_cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.export_model_state(self._voice_state, self._voice_cache_path)

        return self._voice_state

    def synthesize(self, text: str, output_path: Path) -> None:
        voice_state = self._get_voice_state()
        audio = self.model.generate_audio(voice_state, text)
        self.wav_writer(str(output_path), self.model.sample_rate, audio.numpy())
