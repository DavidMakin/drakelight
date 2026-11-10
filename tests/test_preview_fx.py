import pytest

from drakelight import preview_fx as P

PAL = [(255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255), (255, 0, 255)]


@pytest.mark.parametrize("effect", range(1, 21))
@pytest.mark.parametrize("colourful", [False, True])
def test_every_effect_stays_in_colour_range(effect, colourful):
    look = P.Look((0, 255, 0), colourful, PAL)
    for t in (0.0, 0.7, 3.3, 11.9):
        for idx in range(0, 75, 7):
            rgb = P.key_colour(effect, look, (idx % 15) / 14, (idx // 15 + 0.5) / 5, idx, idx // 15, idx % 15, t)
            assert len(rgb) == 3 and all(-1e-6 <= c <= 1.0001 for c in rgb)


def test_static_effect_is_constant():
    look = P.Look((10, 20, 30), False, [])
    a = P.key_colour(1, look, 0.2, 0.2, 0, 0, 0, 0.0)
    b = P.key_colour(1, look, 0.2, 0.2, 0, 0, 0, 9.0)
    assert a == b
