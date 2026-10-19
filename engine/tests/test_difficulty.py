from engine.difficulty import PassContext, pass_difficulty, with_changes

BASE = PassContext(distance=15.0, lane_gaps=[6.0], pressers=[], receiver_marker_dist=8.0)


def score(c: PassContext) -> float:
    return pass_difficulty(c)[0]


def test_range() -> None:
    assert 0 <= score(BASE) <= 100
    worst = PassContext(
        distance=60,
        lane_gaps=[0.2],
        pressers=[(0.5, 6)] * 3,
        receiver_marker_dist=0.5,
        forward_component=1,
        lateral_component=1,
        height="high",
        weak_foot=True,
        first_time=True,
    )
    assert score(worst) > 90


def test_longer_is_harder() -> None:
    assert score(with_changes(BASE, distance=35.0)) > score(BASE)


def test_more_pressure_never_easier() -> None:
    one = with_changes(BASE, pressers=[(2.0, 2.0)])
    two = with_changes(BASE, pressers=[(2.0, 2.0), (2.5, 2.0)])
    assert score(BASE) <= score(one) <= score(two)
    near = with_changes(BASE, pressers=[(1.0, 2.0)])
    far = with_changes(BASE, pressers=[(2.8, 2.0)])
    assert score(near) >= score(far)
    assert score(with_changes(BASE, pressers=[(2.0, 5.0)])) >= score(one)


def test_closer_blocker_is_harder() -> None:
    assert score(with_changes(BASE, lane_gaps=[1.0])) > score(with_changes(BASE, lane_gaps=[5.0]))


def test_tighter_marking_is_harder() -> None:
    assert score(with_changes(BASE, receiver_marker_dist=1.0)) > score(BASE)


def test_forward_harder_than_backward() -> None:
    fwd = with_changes(BASE, forward_component=1.0)
    back = with_changes(BASE, forward_component=-1.0)
    assert score(fwd) > score(back)


def test_factors_explain_the_score() -> None:
    c = with_changes(BASE, pressers=[(1.5, 3.0)], weak_foot=True, height="high")
    s, factors = pass_difficulty(c)
    names = {f.name for f in factors}
    assert {"pressure_on_passer", "weak_foot", "height"} <= names
    assert factors == sorted(factors, key=lambda f: -f.points)
    assert all(f.points > 0 for f in factors if f.name in ("pressure_on_passer", "weak_foot"))
    assert s > score(BASE)
