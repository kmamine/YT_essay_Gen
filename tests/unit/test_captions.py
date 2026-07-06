import pytest

from essaygen.assembly.captions import (
    Cue,
    build_cues,
    format_srt_timestamp,
    render_srt,
    split_sentences,
    wrap_caption_text,
)


def test_format_srt_timestamp_at_zero():
    assert format_srt_timestamp(0.0) == "00:00:00,000"


def test_format_srt_timestamp_with_minutes_and_millis():
    assert format_srt_timestamp(65.5) == "00:01:05,500"


def test_format_srt_timestamp_with_hours():
    assert format_srt_timestamp(3661.25) == "01:01:01,250"


def test_build_cues_sequences_start_end_times_from_durations():
    cues = build_cues(["First line.", "Second line."], [2.0, 3.5])

    assert cues == [
        Cue(index=1, start_sec=0.0, end_sec=2.0, text="First line."),
        Cue(index=2, start_sec=2.0, end_sec=5.5, text="Second line."),
    ]


def test_split_sentences_splits_on_sentence_boundaries():
    assert split_sentences("Ok. This is fine. And this too.") == [
        "Ok.",
        "This is fine.",
        "And this too.",
    ]


def test_split_sentences_keeps_short_sentences_unlike_the_wikipedia_fact_splitter():
    # Captions need every spoken sentence, including short interjections —
    # unlike research-fact extraction, which filters short fragments as noise.
    assert split_sentences("No. Really?") == ["No.", "Really?"]


def test_build_cues_splits_multi_sentence_narration_into_separate_cues():
    # A subsection's full narration is several sentences; each should become
    # its own timed cue so viewers see short, changing captions instead of
    # one giant unbroken block of text sitting on screen for the whole
    # subsection's audio duration.
    narration = "Rome did not fall to barbarians. It rotted from within."
    cues = build_cues([narration], [10.0])

    assert len(cues) == 2
    assert cues[0].text == "Rome did not fall to barbarians."
    assert cues[1].text == "It rotted from within."
    assert cues[0].start_sec == 0.0
    assert cues[1].end_sec == pytest.approx(10.0)
    assert cues[0].end_sec == cues[1].start_sec


def test_build_cues_apportions_duration_by_sentence_character_length():
    # "AAAAAAAAAA" (10 chars) and "BBBBB" (5 chars) share a 15s duration
    # 2:1 by length, so the first sentence should get twice the on-screen time.
    narration = "AAAAAAAAAA. BBBBB."
    cues = build_cues([narration], [15.0])

    assert cues[0].end_sec - cues[0].start_sec == pytest.approx(10.0, abs=0.5)
    assert cues[1].end_sec - cues[1].start_sec == pytest.approx(5.0, abs=0.5)


def test_build_cues_indexes_sequentially_across_subsections():
    cues = build_cues(["One. Two.", "Three."], [4.0, 2.0])

    assert [c.index for c in cues] == [1, 2, 3]
    assert [c.text for c in cues] == ["One.", "Two.", "Three."]


def test_wrap_caption_text_wraps_long_text_at_word_boundaries():
    wrapped = wrap_caption_text("This is a fairly long caption line that needs wrapping", width=20)

    lines = wrapped.split("\n")
    assert all(len(line) <= 20 for line in lines)
    assert "\n" in wrapped


def test_wrap_caption_text_never_exceeds_max_lines():
    long_text = " ".join(["word"] * 60)  # would wrap to many lines by width alone

    wrapped = wrap_caption_text(long_text, width=20, max_lines=2)

    assert len(wrapped.split("\n")) <= 2


def test_wrap_caption_text_leaves_short_text_unwrapped():
    assert wrap_caption_text("Short line.", width=45) == "Short line."


def test_render_srt_produces_expected_block_format():
    cues = [Cue(index=1, start_sec=0.0, end_sec=2.0, text="Hello.")]

    srt = render_srt(cues)

    assert srt == "1\n00:00:00,000 --> 00:00:02,000\nHello.\n"


def test_render_srt_joins_multiple_cues_with_blank_line():
    cues = [
        Cue(index=1, start_sec=0.0, end_sec=2.0, text="First."),
        Cue(index=2, start_sec=2.0, end_sec=4.0, text="Second."),
    ]

    srt = render_srt(cues)

    assert srt == (
        "1\n00:00:00,000 --> 00:00:02,000\nFirst.\n"
        "\n"
        "2\n00:00:02,000 --> 00:00:04,000\nSecond.\n"
    )
