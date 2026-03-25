from app.api.routers.health import health


def test_health_unit_returns_expected_payload() -> None:
    """Directly validate the health handler function payload."""
    assert health() == {"status": "ok"}
