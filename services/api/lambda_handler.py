from mangum import Mangum

from app.main import app

# AWS Lambda entrypoint:
# - handler: "lambda_handler.handler"
handler = Mangum(app)
