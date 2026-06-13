from benchmarks.scripts import gesture_false_trigger_sweep as sut


def test_false_trigger_count_changes_with_confidence_and_votes():
    events = [
        sut.GestureEvent("ok", 0.75),
        sut.GestureEvent("ok", 0.74),
        sut.GestureEvent("ok", 0.73),
        sut.GestureEvent("thumbs_up", 0.55),
    ]

    assert sut.count_false_triggers(events, min_conf=0.7, min_votes=3, window=3) == 1
    assert sut.count_false_triggers(events, min_conf=0.8, min_votes=1, window=3) == 0
    assert sut.count_false_triggers(events, min_conf=0.5, min_votes=1, window=3) == 4


def test_false_trigger_count_delegates_to_majority_vote(monkeypatch):
    calls = []

    def fake_majority_vote(buffer, min_votes):
        calls.append((tuple(buffer), min_votes))
        return "ok" if len(calls) == 2 else None

    monkeypatch.setattr(sut.voting, "majority_vote", fake_majority_vote)
    events = [sut.GestureEvent("ok", 0.9), sut.GestureEvent("ok", 0.9)]

    count = sut.count_false_triggers(events, min_conf=0.7, min_votes=3, window=2)

    assert count == 1
    assert calls == [(("ok",), 3), (("ok", "ok"), 3)]
