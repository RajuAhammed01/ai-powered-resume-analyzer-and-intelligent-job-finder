import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import time
import unittest
from app import create_app
from app.models import db, User

class TestAuthLifecycle(unittest.TestCase):
    def setUp(self):
        self.test_email = f"auth_test_{int(time.time())}@jobsnap.test"
        self.test_pass = "TestPassword123!"

    def test_local_authentication_persistence(self):
        # 1. Local environment (COOKIE_SECURE = False)
        os.environ.pop("VERCEL", None)
        os.environ.pop("SESSION_COOKIE_SECURE", None)
        app = create_app()
        client = app.test_client()

        # Check unauthenticated access redirects to /login
        r_unauth = client.get("/results")
        self.assertEqual(r_unauth.status_code, 302)
        self.assertTrue("/login" in r_unauth.headers.get("Location", ""))

        # GET /register to obtain CSRF token
        r_get_reg = client.get("/register")
        self.assertEqual(r_get_reg.status_code, 200)
        html = r_get_reg.get_data(as_text=True)
        match = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
        self.assertIsNotNone(match, "CSRF token must be present in HTML")
        csrf_token = match.group(1)

        # POST /register
        r_reg = client.post(
            "/register",
            data={
                "name": "Auth Tester",
                "email": self.test_email,
                "password": self.test_pass,
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        self.assertEqual(r_reg.status_code, 302)
        self.assertEqual(r_reg.headers.get("Location"), "/dashboard")
        self.assertEqual(r_reg.headers.get("Cache-Control"), "no-cache, no-store, must-revalidate, max-age=0")

        # In local mode, cookie does not have Secure=True
        cookies = r_reg.headers.getlist("Set-Cookie")
        self.assertTrue(len(cookies) >= 1)
        session_cookie = [c for c in cookies if "jobsnap_session" in c][0]
        self.assertNotIn("Secure", session_cookie)

        # Check authenticated navigation across multiple protected endpoints
        r_dash = client.get("/dashboard")
        self.assertEqual(r_dash.status_code, 200)

        # /results without resume redirects to /upload (NOT /login)
        r_results = client.get("/results")
        self.assertEqual(r_results.status_code, 302)
        self.assertTrue("/upload" in r_results.headers.get("Location", ""))

        r_upload = client.get("/upload")
        self.assertEqual(r_upload.status_code, 200)

        r_saved = client.get("/saved-jobs")
        self.assertEqual(r_saved.status_code, 200)
        print("[PASS] Local authentication lifecycle verified!")

    def test_vercel_authentication_persistence(self):
        # 2. Production Vercel environment (COOKIE_SECURE = True)
        os.environ["VERCEL"] = "1"
        app_vercel = create_app()
        self.assertTrue(app_vercel.config["SESSION_COOKIE_SECURE"], "SESSION_COOKIE_SECURE must be True when VERCEL=1")

        client_vercel = app_vercel.test_client()

        # GET /register with HTTPS scheme
        r_get = client_vercel.get("/register", base_url="https://jobsnap.vercel.app")
        self.assertEqual(r_get.status_code, 200)
        html = r_get.get_data(as_text=True)
        match = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
        self.assertIsNotNone(match)
        csrf_token = match.group(1)

        # POST /register over HTTPS
        r_reg = client_vercel.post(
            "/register",
            base_url="https://jobsnap.vercel.app",
            data={
                "name": "Vercel Tester",
                "email": self.test_email,
                "password": self.test_pass,
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        self.assertEqual(r_reg.status_code, 302)
        self.assertEqual(r_reg.headers.get("Location"), "/dashboard")
        self.assertEqual(r_reg.headers.get("Cache-Control"), "no-cache, no-store, must-revalidate, max-age=0")

        # Verify cookie includes Secure attribute for HTTPS delivery
        cookies = r_reg.headers.getlist("Set-Cookie")
        session_cookie = [c for c in cookies if "jobsnap_session" in c][0]
        self.assertIn("Secure", session_cookie, "jobsnap_session MUST have Secure attribute on Vercel")
        self.assertIn("HttpOnly", session_cookie)
        self.assertIn("SameSite=Lax", session_cookie)

        # Access protected routes with session cookie on HTTPS
        r_dash = client_vercel.get("/dashboard", base_url="https://jobsnap.vercel.app")
        self.assertEqual(r_dash.status_code, 200)

        # /results without resume safely redirects to /upload (NOT /login)
        r_results = client_vercel.get("/results", base_url="https://jobsnap.vercel.app")
        self.assertEqual(r_results.status_code, 302)
        self.assertTrue("/upload" in r_results.headers.get("Location", ""))

        r_upload = client_vercel.get("/upload", base_url="https://jobsnap.vercel.app")
        self.assertEqual(r_upload.status_code, 200)

        r_saved = client_vercel.get("/saved-jobs", base_url="https://jobsnap.vercel.app")
        self.assertEqual(r_saved.status_code, 200)
        print("[PASS] Vercel HTTPS authentication lifecycle verified!")

if __name__ == "__main__":
    unittest.main()

