import pytest
from pydantic import ValidationError

from essaygen.models.stance import Stance


def test_stance_holds_thesis_and_angle():
    stance = Stance(
        thesis="Rome's fall was self-inflicted, not barbarian conquest.",
        angle="Contrarian: blames institutional rot over external invasion.",
    )

    assert stance.thesis.startswith("Rome's fall")
    assert "Contrarian" in stance.angle


def test_stance_missing_angle_raises():
    with pytest.raises(ValidationError):
        Stance(thesis="Some thesis")
