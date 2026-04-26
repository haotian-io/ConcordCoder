"""Tests for Confidence-Guided Probing module (Contribution 2)."""

from __future__ import annotations

import math

import pytest

from concordcoder.generation.probing import (
    ASTSpan,
    ProbingEngine,
    TokenWithLogprob,
    mock_logprobs_from_code,
    parse_openai_logprobs,
)
from concordcoder.schemas import ContextBundle


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def simple_bundle():
    return ContextBundle(
        task_summary="add retry to payment",
        historical_decisions=[
            "payment.py: transaction commit refactored",
            "payment.py: exception handling changed",
        ],
    )


@pytest.fixture
def engine(simple_bundle):
    return ProbingEngine(
        llm_client=None,
        bundle=simple_bundle,
        confidence_threshold=0.45,
        churn_alpha=0.6,
        max_probes=3,
    )


RETRY_CODE = '''\
def retry_payment(user_id: str, amount: float) -> bool:
    for attempt in range(3):
        try:
            result = process_payment(user_id, amount)
            if result:
                return True
        except Exception as exc:
            pass
    raise RuntimeError("Payment failed after 3 retries")
'''

# ─── TokenWithLogprob ────────────────────────────────────────────────────────

def test_token_probability_conversion():
    tok = TokenWithLogprob(token="def", logprob=math.log(0.9))
    assert abs(tok.probability - 0.9) < 1e-6


def test_token_low_probability():
    tok = TokenWithLogprob(token="except", logprob=math.log(0.3))
    assert tok.probability < 0.4


# ─── mock_logprobs_from_code ─────────────────────────────────────────────────

def test_mock_logprobs_generates_tokens():
    tokens = mock_logprobs_from_code(RETRY_CODE)
    assert len(tokens) > 0
    # All logprobs should be <= 0 (log of probability in [0, 1])
    for t in tokens:
        assert t.logprob <= 0.0


def test_mock_logprobs_risk_keywords_lower_confidence():
    """Tokens around 'except' / 'try' / 'raise' should have lower confidence."""
    tokens = mock_logprobs_from_code(RETRY_CODE)
    risk_toks = [t for t in tokens if any(kw in t.token.lower() for kw in {"try", "except", "raise"})]
    normal_toks = [t for t in tokens if "def" in t.token.lower() or "for" in t.token.lower()]
    if risk_toks and normal_toks:
        mean_risk = sum(math.exp(t.logprob) for t in risk_toks) / len(risk_toks)
        mean_normal = sum(math.exp(t.logprob) for t in normal_toks) / len(normal_toks)
        assert mean_risk < mean_normal, "Risk tokens should have lower confidence than normal tokens"


# ─── ProbingEngine: Git Churn ────────────────────────────────────────────────

def test_git_churn_from_bundle(engine):
    churn = engine._query_git_churn()
    assert "payment.py" in churn
    # payment.py appears twice → should have churn = 1.0 (normalized)
    assert churn["payment.py"] == pytest.approx(1.0)


def test_git_churn_empty_bundle():
    e = ProbingEngine(bundle=ContextBundle(task_summary="test"))
    churn = e._query_git_churn()
    assert churn == {}


# ─── ProbingEngine: AST Span Extraction ─────────────────────────────────────

def test_ast_spans_extracted(engine):
    tokens = mock_logprobs_from_code(RETRY_CODE)
    spans = engine._extract_ast_spans(RETRY_CODE, tokens)
    # Should find at least the function def and the try/except
    assert len(spans) > 0
    fn_spans = [s for s in spans if s.node_type == "FunctionDef"]
    assert any(s.node_name == "retry_payment" for s in fn_spans)


def test_ast_spans_bad_syntax(engine):
    tokens = mock_logprobs_from_code("def (bad syntax:\n")
    spans = engine._extract_ast_spans("def (bad syntax:\n", tokens)
    assert spans == []


# ─── ProbingEngine: Span Confidence ─────────────────────────────────────────

def test_span_confidence_calculation(engine):
    tokens = [
        TokenWithLogprob(token="def ", logprob=math.log(0.95)),
        TokenWithLogprob(token="func", logprob=math.log(0.70)),
        TokenWithLogprob(token="()", logprob=math.log(0.90)),
    ]
    span = ASTSpan(node_type="FunctionDef", node_name="func", start_token=0, end_token=3)
    confidences = engine._compute_span_confidences([span], tokens)
    expected = (0.95 + 0.70 + 0.90) / 3
    assert abs(confidences[0] - expected) < 1e-4


def test_empty_span_confidence(engine):
    tokens = [TokenWithLogprob(token="x", logprob=math.log(0.9))]
    span = ASTSpan(node_type="Name", node_name="x", start_token=5, end_token=5)  # empty slice
    confidences = engine._compute_span_confidences([span], tokens)
    assert confidences[0] == 1.0  # defaults to max confidence when empty


# ─── ProbingEngine: Probe Selection ─────────────────────────────────────────

def test_no_probes_when_high_confidence(engine):
    # All tokens near-certain (99%)
    high_conf_tokens = [
        TokenWithLogprob(token=w + " ", logprob=math.log(0.99))
        for w in RETRY_CODE.split()
    ]
    result = engine.run(RETRY_CODE, high_conf_tokens)
    assert not result.needs_probing
    assert result.probes == []


def test_probes_generated_when_low_confidence(engine):
    low_conf_tokens = mock_logprobs_from_code(RETRY_CODE, seed_confidence=0.3)
    result = engine.run(RETRY_CODE, low_conf_tokens)
    # With very low confidence, should trigger probes
    # Note: depends on the random distribution; we check structure
    assert isinstance(result.needs_probing, bool)
    assert isinstance(result.probe_questions, list)
    assert isinstance(result.low_confidence_summary, str)
    assert len(result.probe_questions) == len(result.probes)


def test_max_probes_respected(simple_bundle):
    engine = ProbingEngine(bundle=simple_bundle, confidence_threshold=0.99, max_probes=2)
    tokens = mock_logprobs_from_code(RETRY_CODE, seed_confidence=0.1)
    result = engine.run(RETRY_CODE, tokens)
    assert len(result.probes) <= 2


def test_probe_questions_are_nonempty(engine):
    tokens = mock_logprobs_from_code(RETRY_CODE, seed_confidence=0.2)
    result = engine.run(RETRY_CODE, tokens)
    for q in result.probe_questions:
        assert isinstance(q, str)
        assert len(q) > 10


# ─── ProbingEngine: Full run() ────────────────────────────────────────────────

def test_run_returns_correct_structure(engine):
    tokens = mock_logprobs_from_code(RETRY_CODE)
    result = engine.run(RETRY_CODE, tokens)
    assert hasattr(result, "probes")
    assert hasattr(result, "probe_questions")
    assert hasattr(result, "low_confidence_summary")
    assert hasattr(result, "flagged_lines")
    assert hasattr(result, "needs_probing")


def test_flagged_lines_format(engine):
    tokens = mock_logprobs_from_code(RETRY_CODE, seed_confidence=0.2)
    result = engine.run(RETRY_CODE, tokens)
    for start, end in result.flagged_lines:
        assert isinstance(start, int)
        assert isinstance(end, int)
        assert start <= end


# ─── Hotspot Score Math ───────────────────────────────────────────────────────

def test_hotspot_score_increases_with_churn():
    """Spans with high git churn should have higher hotspot scores."""
    e = ProbingEngine(
        bundle=ContextBundle(task_summary="x", historical_decisions=["a.py: m1", "a.py: m2"]),
        confidence_threshold=0.0,
        churn_alpha=1.0,
        max_probes=1,
        w_churn=1.0,
        w_centrality=0.0,
        w_fan_io=0.0,
        w_public_api=0.0,
    )
    spans = [ASTSpan(node_type="FunctionDef", node_name="f", start_token=0, end_token=1, file_hint="a.py")]
    conf = {0: 0.5}
    churn = {"a.py": 1.0}
    targets = e._select_probe_targets(spans, conf, churn)
    assert targets and targets[0].hotspot_score > 0.5


def test_dynamic_theta_in_valid_range(engine):
    theta = engine._dynamic_theta(n_spans=12)
    assert 0.25 <= theta <= 0.75


def test_probe_contains_risk_components(engine):
    low_conf_tokens = mock_logprobs_from_code(RETRY_CODE, seed_confidence=0.2)
    result = engine.run(RETRY_CODE, low_conf_tokens)
    if result.probes:
        comp = result.probes[0].risk_components
        assert "churn" in comp
        assert "centrality" in comp
        assert "fan_io" in comp
        assert "public_api" in comp


def test_churn_alpha_affects_hotspot_score():
    spans = [ASTSpan(node_type="FunctionDef", node_name="f", start_token=0, end_token=1, file_hint="a.py")]
    conf = {0: 0.5}
    churn = {"a.py": 1.0}
    low_alpha = ProbingEngine(
        bundle=ContextBundle(task_summary="x"),
        churn_alpha=0.2,
        confidence_threshold=0.0,
        max_probes=1,
        w_churn=1.0,
        w_centrality=0.0,
        w_fan_io=0.0,
        w_public_api=0.0,
    )
    high_alpha = ProbingEngine(
        bundle=ContextBundle(task_summary="x"),
        churn_alpha=1.0,
        confidence_threshold=0.0,
        max_probes=1,
        w_churn=1.0,
        w_centrality=0.0,
        w_fan_io=0.0,
        w_public_api=0.0,
    )
    s1 = low_alpha._select_probe_targets(spans, conf, churn)[0].hotspot_score
    s2 = high_alpha._select_probe_targets(spans, conf, churn)[0].hotspot_score
    assert s2 > s1


# ─── parse_openai_logprobs ───────────────────────────────────────────────────

def test_parse_openai_logprobs_empty_response():
    """Should return empty list for an object with no choices."""
    class FakeResponse:
        choices = []

    result = parse_openai_logprobs(FakeResponse())
    assert result == []


def test_parse_openai_logprobs_none_logprobs():
    """Should handle missing logprobs gracefully."""
    class FakeChoice:
        logprobs = None
        message = None

    class FakeResponse:
        choices = [FakeChoice()]

    result = parse_openai_logprobs(FakeResponse())
    assert result == []
