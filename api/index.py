import sys
import os

# Ensure project root is on the path so `server.*` imports work on Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()  # no-op on Vercel where env vars are injected directly

from server.main import mcp
from mangum import Mangum

_asgi_app = mcp.streamable_http_app()

# Mangum adapts the ASGI app for AWS Lambda-style execution (Vercel's runtime).
# lifespan="off" because Vercel does not support ASGI lifespan events.
app = Mangum(_asgi_app, lifespan="off")
