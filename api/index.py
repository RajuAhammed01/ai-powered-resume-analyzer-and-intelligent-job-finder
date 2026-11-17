import os
import sys

# Ensure root workspace directory is in Python module search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from run import app


class VercelPathMiddleware:
    """WSGI middleware ensuring correct PATH_INFO when invoked through Vercel serverless."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Recover true client URL from Vercel edge proxy headers if present
        matched_path = (
            environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("HTTP_X_REAL_PATH")
        )
        if matched_path:
            clean_path = matched_path.split("?")[0]
            if clean_path and clean_path not in ("/api/index", "/api/index.py"):
                environ["PATH_INFO"] = clean_path

        # 2. Map /api/index root hits to /
        if environ.get("PATH_INFO") in ("/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


# Attach WSGI middleware and export callable for Vercel
app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
