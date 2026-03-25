from mangum import Mangum

from lambda_handler import handler as lambda_handler


def test_lambda_handler_is_mangum_adapter() -> None:
    """Ensure the Lambda entrypoint wraps the FastAPI app with Mangum."""
    assert isinstance(lambda_handler, Mangum)
