"""The Verifier's number match: rounding is allowed, a different small number is not."""

from backend.agents.verifier import close


def test_rounding_to_the_written_precision_passes() -> None:
    assert close(0.78, 0.781)  # xG to two decimals
    assert close(0.76, 0.762)
    assert close(22, 22.4)  # a whole number
    assert close(8.1, 8.06)  # km to one decimal
    assert close(42.1, 42.1)
    assert close(1080, 1095)  # big counts keep the two percent slack


def test_a_different_small_number_fails() -> None:
    assert not close(0.45, 0.02)  # passed under the old flat 0.51 tolerance
    assert not close(0.76, 0.30)
    assert not close(8.5, 8.06)
    assert not close(23, 22.4)


def test_written_ten_does_not_cover_ten_point_six() -> None:
    assert not close(10, 10.6)
    assert close(10.35, 10.35)


def test_a_moment_never_calls_the_result() -> None:
    from backend.agents.story import RESULT

    assert RESULT.search("Tobias Wragg scored, making Ashford Rovers win 1-0.")
    assert RESULT.search("A famous victory is in sight")
    assert not RESULT.search("Ashford won the ball back high up the pitch")
    assert not RESULT.search("Wragg won a penalty and scored to make it 1-0")
