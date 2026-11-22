import json
import os
import unittest
from app import create_app
from app.extensions import db
from app.models import Resume, User
from app.services.job_validator import GLOBAL_JOBS_REGISTRY


class TestVercelSessionAndIsolation(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-vercel-session-key",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            # User 1: Python/Backend developer with resume
            user1 = User(name="Alice Python", email="alice@test.com")
            user1.set_password("Secret123!")
            db.session.add(user1)
            db.session.commit()

            resume1 = Resume(
                user_id=user1.id,
                filename="alice_resume.pdf",
                extracted_text="Python Backend Engineer experienced in Flask, Django, PostgreSQL, and REST APIs.",
                extracted_skills=json.dumps(["Python", "Flask", "PostgreSQL", "REST APIs"]),
                ats_score=88,
            )
            db.session.add(resume1)

            # User 2: Brand new zero-state user with NO resume
            user2 = User(name="Bob Newbie", email="bob@test.com")
            user2.set_password("Secret123!")
            db.session.add(user2)

            # User 3: Frontend developer with resume
            user3 = User(name="Carol React", email="carol@test.com")
            user3.set_password("Secret123!")
            db.session.add(user3)
            db.session.commit()

            resume3 = Resume(
                user_id=user3.id,
                filename="carol_resume.pdf",
                extracted_text="Frontend Developer with React, JavaScript, TypeScript, CSS3, and HTML5.",
                extracted_skills=json.dumps(["React", "JavaScript", "TypeScript", "CSS3", "HTML5"]),
                ats_score=92,
            )
            db.session.add(resume3)
            db.session.commit()

            self.user1_id = user1.id
            self.user2_id = user2.id
            self.user3_id = user3.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_anticache_headers_on_authenticated_and_auth_routes(self):
        """Dynamic HTML and auth pages must contain anti-caching headers so Vercel CDN never caches sessions."""
        for path in ["/login", "/register", "/"]:
            r = self.client.get(path)
            cc = r.headers.get("Cache-Control", "")
            self.assertIn("no-cache", cc)
            self.assertIn("no-store", cc)
            self.assertIn("must-revalidate", cc)
            self.assertIn("max-age=0", cc)

    def test_job_cross_user_isolation(self):
        """Verify candidate-specific match data never bleeds from User A to User B or User C."""
        with self.app.app_context():
            GLOBAL_JOBS_REGISTRY["test_iso_job_1"] = {
                "job_id": "test_iso_job_1",
                "job_title": "Senior Python Backend Developer",
                "company": "PythonCorp",
                "job_description": "We need strong Python, Flask, PostgreSQL skills.",
                "job_skills": ["Python", "Flask", "PostgreSQL"],
                "job_apply_link": "https://example.com/apply/python",
                "location": "Remote",
            }

        # 1. User 1 (Python Dev) views job detail
        self.client.post("/login", data={"email": "alice@test.com", "password": "Secret123!"})
        r1 = self.client.get("/job/test_iso_job_1")
        self.assertEqual(r1.status_code, 200)
        html1 = r1.get_data(as_text=True)
        self.assertIn("Python", html1)
        # Alice should see match score
        self.assertIn("% Match", html1)
        self.client.get("/logout")

        # 2. User 2 (Bob, NO resume) views the same job
        self.client.post("/login", data={"email": "bob@test.com", "password": "Secret123!"})
        r2 = self.client.get("/job/test_iso_job_1")
        self.assertEqual(r2.status_code, 200)
        html2 = r2.get_data(as_text=True)
        # Must show No Resume Uploaded prompt, NOT Alice's score or skills!
        self.assertIn("No Resume Uploaded", html2)
        self.assertIn("Upload a resume", html2)

        # Bob queries the JSON API for the same job
        r2_api = self.client.get("/api/jobs/test_iso_job_1")
        self.assertEqual(r2_api.status_code, 200)
        data2 = r2_api.get_json()["data"]
        self.assertIsNone(data2["combined_score"])
        self.assertEqual(data2["matched_skills"], [])
        self.client.get("/logout")

        # 3. User 3 (Carol, React Dev) views the same Python job
        self.client.post("/login", data={"email": "carol@test.com", "password": "Secret123!"})
        r3_api = self.client.get("/api/jobs/test_iso_job_1")
        self.assertEqual(r3_api.status_code, 200)
        data3 = r3_api.get_json()["data"]
        # Carol has React skills, so Python is NOT in matched_skills
        self.assertNotIn("Python", data3["matched_skills"])
        self.client.get("/logout")

    def test_vercel_path_middleware_script_name(self):
        """VercelPathMiddleware must guarantee SCRIPT_NAME is clean and URL is root-relative."""
        from run import VercelPathMiddleware

        def dummy_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [json.dumps({
                "PATH_INFO": environ.get("PATH_INFO"),
                "SCRIPT_NAME": environ.get("SCRIPT_NAME"),
                "QUERY_STRING": environ.get("QUERY_STRING"),
                "wsgi.url_scheme": environ.get("wsgi.url_scheme"),
            }).encode("utf-8")]

        wrapped = VercelPathMiddleware(dummy_app)

        # Simulate Vercel rewrite with __vercel_path query parameter
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/index.py",
            "SCRIPT_NAME": "/api/index",
            "QUERY_STRING": "__vercel_path=/dashboard&filter=recent",
            "HTTP_X_FORWARDED_PROTO": "https",
            "wsgi.url_scheme": "http",
        }

        output = []
        def start_response(status, headers):
            output.append((status, headers))

        res = wrapped(environ, start_response)
        data = json.loads(b"".join(res).decode("utf-8"))

        self.assertEqual(data["SCRIPT_NAME"], "")
        self.assertEqual(data["PATH_INFO"], "/dashboard")
        self.assertEqual(data["QUERY_STRING"], "filter=recent")
        self.assertEqual(data["wsgi.url_scheme"], "https")


if __name__ == "__main__":
    unittest.main()
