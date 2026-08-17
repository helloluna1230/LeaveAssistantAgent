from agents.leave_assistant.observability import current_trace_id, mask_user, redact, traced


def test_mask_user():
    assert mask_user("E1001") == "E1***"
    assert mask_user(None) == "anon"


def test_redact_bearer_and_ids():
    text = redact("token Bearer abc.def-123 for E1002 and M1001")
    assert "abc.def-123" not in text
    assert "E1002" not in text and "E10***" in text
    assert "M1001" not in text and "M10***" in text


def test_traced_noop_without_otel():
    # No OTel SDK configured: traced is a no-op context manager that still runs.
    with traced("test.span", user_id="E1001", **{"tool.name": "x"}) as span:
        span.set_attribute("k", "v")
    assert current_trace_id() is None
