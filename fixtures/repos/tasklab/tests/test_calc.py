from tasklab.calc import RunningTotal


def test_running_total() -> None:
    rt = RunningTotal()
    assert rt.add(3) == 3
    assert rt.add(10) == 13
