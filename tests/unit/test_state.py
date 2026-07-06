from essaygen.core.state import ProjectState, load_state, save_state


def test_load_state_returns_empty_state_when_file_missing(tmp_path):
    state = load_state(tmp_path / "state.json")

    assert state.stages == {}


def test_mark_stage_done_updates_status_and_artifact():
    state = ProjectState()

    state.mark_stage_done("research", artifact="research.json")

    assert state.is_stage_done("research") is True
    assert state.stages["research"].artifact == "research.json"


def test_is_stage_done_false_for_unstarted_or_in_progress_stage():
    state = ProjectState()

    assert state.is_stage_done("research") is False

    state.mark_stage_in_progress("research")

    assert state.is_stage_done("research") is False


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "state.json"
    state = ProjectState()
    state.mark_stage_done("research", artifact="research.json")

    save_state(path, state)
    restored = load_state(path)

    assert restored.is_stage_done("research") is True
    assert restored.stages["research"].artifact == "research.json"


def test_save_state_does_not_leave_tmp_file_behind(tmp_path):
    path = tmp_path / "state.json"
    state = ProjectState()

    save_state(path, state)

    assert path.exists()
    assert not (tmp_path / "state.json.tmp").exists()


def test_set_and_get_unit_status_for_subsection_stage():
    state = ProjectState()

    state.set_unit_status("subsections", "sec_01_sub_01", tts="done", image="failed", attempts=3)

    unit = state.get_unit_status("subsections", "sec_01_sub_01")
    assert unit == {"tts": "done", "image": "failed", "attempts": 3}


def test_get_unit_status_returns_empty_dict_for_unknown_unit():
    state = ProjectState()

    assert state.get_unit_status("subsections", "sec_99_sub_01") == {}


def test_topic_defaults_to_none():
    state = ProjectState()

    assert state.topic is None


def test_topic_round_trips_through_save_and_load(tmp_path):
    path = tmp_path / "state.json"
    state = ProjectState(topic="Fall of Rome")

    save_state(path, state)
    restored = load_state(path)

    assert restored.topic == "Fall of Rome"


def test_save_and_load_round_trip_handles_non_ascii_content(tmp_path):
    path = tmp_path / "state.json"
    state = ProjectState(topic="Zągrzębie ˈpronunciation café")

    save_state(path, state)
    restored = load_state(path)

    assert restored.topic == state.topic
