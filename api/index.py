import os
import sys
import urllib.parse

# Ensure root workspace directory is in Python module search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from run import app


class VercelPathMiddleware:
    """WSGI middleware ensuring correct PATH_INFO, SCRIPT_NAME, and HTTPS scheme when invoked through Vercel serverless."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Ensure https scheme is reflected in serverless requests
        proto = environ.get("HTTP_X_FORWARDED_PROTO", "https")
        if proto:
            environ["wsgi.url_scheme"] = proto

        # 2. Reset SCRIPT_NAME to empty string so cookie path and url_for() are always root-relative
        environ["SCRIPT_NAME"] = ""

        # 3. Recover true client URL:
        # Check __vercel_path query param first (reliably injected by vercel.json rewrite)
        qs = environ.get("QUERY_STRING", "")
        client_path = None
        if "__vercel_path=" in qs:
            params = urllib.parse.parse_qs(qs)
            if "__vercel_path" in params and params["__vercel_path"]:
                client_path = params["__vercel_path"][0]
                # Strip internal __vercel_path from QUERY_STRING so application query params remain clean
                cleaned_params = {k: v for k, v in params.items() if k != "__vercel_path"}
                environ["QUERY_STRING"] = urllib.parse.urlencode(cleaned_params, doseq=True)

        # 4. Fallback: check headers if query param was not injected
        if not client_path:
            for header_key in (
                "HTTP_X_FORWARDED_URI",
                "HTTP_X_FORWARDED_URL",
                "HTTP_X_VERCEL_PATH",
                "HTTP_X_ORIGINAL_URL",
                "HTTP_RAW_URI",
                "RAW_URI",
                "REQUEST_URI",
            ):
                val = environ.get(header_key)
                if val:
                    clean = val.split("?")[0]
                    if clean and clean not in ("/api/index", "/api/index.py"):
                        client_path = clean
                        break

        # 5. Fallback: check HTTP_X_MATCHED_PATH only if it's not the internal rewrite destination
        if not client_path:
            mp = environ.get("HTTP_X_MATCHED_PATH")
            if mp:
                clean_mp = mp.split("?")[0]
                if clean_mp not in ("/api/index", "/api/index.py", ""):
                    client_path = clean_mp

        if client_path:
            if not client_path.startswith("/"):
                client_path = "/" + client_path
            environ["PATH_INFO"] = client_path
        elif environ.get("PATH_INFO") in ("/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


# Attach WSGI middleware for Vercel serverless request handling
# (Note: ProxyFix is already cleanly attached in run.py)
app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
