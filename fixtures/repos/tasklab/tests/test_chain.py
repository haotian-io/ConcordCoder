from tasklab.chain import pipeline_value


def test_pipeline() -> None:
    assert pipeline_value(4) == 9
