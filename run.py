import os
import pathlib
import sys
import urllib.parse

# ── Ensure required directories exist if filesystem is writable ────────────────
try:
    pathlib.Path("models").mkdir(exist_ok=True)
    pathlib.Path("uploads").mkdir(exist_ok=True)
    pathlib.Path("instance").mkdir(exist_ok=True)
except Exception:
    pass

from app import create_app
from werkzeug.middleware.proxy_fix import ProxyFix


class VercelPathMiddleware:
    """WSGI middleware ensuring correct PATH_INFO, SCRIPT_NAME, and HTTPS scheme when invoked through Vercel serverless."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Ensure https scheme is reflected in serverless requests behind reverse proxies
        if "HTTP_X_FORWARDED_PROTO" in environ:
            environ["wsgi.url_scheme"] = environ["HTTP_X_FORWARDED_PROTO"]
        elif os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            environ["wsgi.url_scheme"] = "https"

        # 2. Reset SCRIPT_NAME to empty string so cookie path and url_for() are always root-relative
        environ["SCRIPT_NAME"] = ""

        # 3. Recover true client URL:
        # Check query string params (injected by Vercel rewrite with /:path*)
        qs = environ.get("QUERY_STRING", "")
        client_path = None

        if qs and ("path=" in qs or "__vercel_path=" in qs):
            params = urllib.parse.parse_qs(qs)

            if "__vercel_path" in params and params["__vercel_path"]:
                client_path = params["__vercel_path"][0]
            elif "path" in params and params["path"]:
                client_path = "/" + params["path"][0].lstrip("/")

            # Strip routing parameters from QUERY_STRING so application code sees clean query parameters
            cleaned_params = {
                k: v for k, v in params.items() if k not in ("path", "__vercel_path")
            }
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
        elif environ.get("PATH_INFO") in ("/api/index", "/api/index.py", "", None):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


# Vercel and WSGI entry point: exposes Flask application as 'app'
# x_prefix=0 ensures Vercel's internal lambda rewrite destination (/api/index) does not overwrite SCRIPT_NAME
app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)
app.wsgi_app = VercelPathMiddleware(app.wsgi_app)

if __name__ == "__main__":
    # Support dynamic PORT and HOST to prevent port collisions
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")

    # Command-line overrides
    use_prod = "--prod" in sys.argv or "--production" in sys.argv
    use_dev = "--dev" in sys.argv or "--debug" in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        elif arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]

    # Production mode is default unless FLASK_DEBUG=1 or --dev is passed
    env_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("true", "1")
    debug = use_dev or (env_debug and not use_prod)

    if not debug:
        try:
            from waitress import serve
            print(f"[*] Starting JobSnap on http://{host}:{port}", flush=True)
            print(f"[*] Production WSGI Server active (Waitress multi-threaded engine).", flush=True)
            print(f"[*] Development server warning resolved: ready for actual developments.", flush=True)
            serve(app, host=host, port=port, threads=8)
            sys.exit(0)
        except ImportError:
            print("[!] Waitress not installed; falling back to Werkzeug development server.", flush=True)

    print(f"[*] Starting JobSnap development server on http://{host}:{port} (debug={debug})", flush=True)
    app.run(host=host, port=port, debug=debug)
