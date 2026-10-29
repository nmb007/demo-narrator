"""Unit tests for required_inputs."""

from src.narration.constants import NARRATION, SCRIPT, SOURCE, NarrationStep
from src.narration.service import required_inputs


def test_all_steps_need_only_source() -> None:
    assert required_inputs(list(NarrationStep)) == {SOURCE}


def test_voice_mux_needs_script_and_source() -> None:
    # SOURCE is not required by voice itself in STEP_READS; mux needs source.
    needed = required_inputs([NarrationStep.VOICE, NarrationStep.MUX])
    assert SCRIPT in needed
    assert SOURCE in needed
    assert NARRATION not in needed


def test_mux_only_needs_source_and_narration() -> None:
    assert required_inputs([NarrationStep.MUX]) == {SOURCE, NARRATION}


def test_rewrite_only_needs_script() -> None:
    assert required_inputs([NarrationStep.REWRITE]) == {SCRIPT}
