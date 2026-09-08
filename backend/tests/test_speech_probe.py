import runpy
from pathlib import Path


def test_probe_accepts_fraction_notation_but_not_wrong_fraction():
    scope = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/validate_speech_loop.py'))
    matches = scope['matches_fraction_speech']
    assert matches('平均分成两份，每份是二分之一')
    assert matches('平均分成两份，每份是1/2')
    assert not matches('平均分成两份，每份是1/3')
