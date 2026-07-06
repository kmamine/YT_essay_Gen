from pathlib import Path

from essaygen.providers.tts.pocket_tts import PocketTTSProvider, resolve_voice_cache_path


class FakeAudio:
    def __init__(self, values):
        self.values = values

    def numpy(self):
        return self.values


class FakeTTSModel:
    def __init__(self):
        self.sample_rate = 24000
        self.state_calls = []
        self.generate_calls = []

    def get_state_for_audio_prompt(self, voice):
        self.state_calls.append(voice)
        return f"state-for-{voice}"

    def generate_audio(self, state, text):
        self.generate_calls.append((state, text))
        return FakeAudio([0.1, 0.2, 0.3])


def test_synthesize_writes_wav_via_wav_writer(tmp_path):
    model = FakeTTSModel()
    writes = []
    provider = PocketTTSProvider(voice="alba", model=model, wav_writer=lambda *args: writes.append(args))
    output_path = tmp_path / "sec_01_sub_01.wav"

    provider.synthesize("Hello world", output_path)

    assert len(writes) == 1
    path_arg, sample_rate_arg, array_arg = writes[0]
    assert path_arg == str(output_path)
    assert sample_rate_arg == 24000
    assert array_arg == [0.1, 0.2, 0.3]


def test_synthesize_reuses_cached_voice_state_across_calls(tmp_path):
    model = FakeTTSModel()
    provider = PocketTTSProvider(voice="alba", model=model, wav_writer=lambda *args: None)

    provider.synthesize("First sentence.", tmp_path / "a.wav")
    provider.synthesize("Second sentence.", tmp_path / "b.wav")

    assert model.state_calls == ["alba"]
    assert [text for _, text in model.generate_calls] == ["First sentence.", "Second sentence."]


def test_provider_has_expected_name():
    provider = PocketTTSProvider(voice="alba", model=FakeTTSModel(), wav_writer=lambda *args: None)

    assert provider.name == "pocket_tts"


def test_resolve_voice_cache_path_returns_none_for_builtin_voice():
    assert resolve_voice_cache_path("alba", Path("./cache")) is None


def test_resolve_voice_cache_path_returns_none_for_builtin_voice_case_insensitive_names():
    assert resolve_voice_cache_path("giovanni", Path("./cache")) is None


def test_resolve_voice_cache_path_returns_safetensors_path_for_custom_reference_audio():
    result = resolve_voice_cache_path("./voices/my_reference.wav", Path("./cache"))

    assert result == Path("./cache/my_reference.safetensors")


def test_synthesize_exports_state_to_cache_when_cache_missing(tmp_path):
    model = FakeTTSModel()
    cache_path = tmp_path / "my_reference.safetensors"
    exports = []
    provider = PocketTTSProvider(
        voice="./voices/my_reference.wav",
        model=model,
        wav_writer=lambda *args: None,
        voice_cache_path=cache_path,
        export_model_state=lambda state, dest: exports.append((state, dest)),
    )

    provider.synthesize("Hello world", tmp_path / "out.wav")

    assert model.state_calls == ["./voices/my_reference.wav"]
    assert exports == [("state-for-./voices/my_reference.wav", cache_path)]


def test_synthesize_creates_cache_directory_if_missing(tmp_path):
    model = FakeTTSModel()
    cache_path = tmp_path / "nested" / "cache_dir" / "my_reference.safetensors"
    provider = PocketTTSProvider(
        voice="./voices/my_reference.wav",
        model=model,
        wav_writer=lambda *args: None,
        voice_cache_path=cache_path,
        export_model_state=lambda state, dest: dest.write_bytes(b"exported"),
    )

    provider.synthesize("Hello world", tmp_path / "out.wav")

    assert cache_path.parent.is_dir()


def test_synthesize_loads_from_cache_when_cache_file_already_exists(tmp_path):
    model = FakeTTSModel()
    cache_path = tmp_path / "my_reference.safetensors"
    cache_path.write_bytes(b"cached-state")
    exports = []
    provider = PocketTTSProvider(
        voice="./voices/my_reference.wav",
        model=model,
        wav_writer=lambda *args: None,
        voice_cache_path=cache_path,
        export_model_state=lambda state, dest: exports.append((state, dest)),
    )

    provider.synthesize("Hello world", tmp_path / "out.wav")

    assert model.state_calls == [str(cache_path)]
    assert exports == []
