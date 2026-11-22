import unittest
from app import create_app
from app.extensions import db
from app.models import User, Resume, JobPreference, SavedJob

class TestResumeAIPages(unittest.TestCase):
    def setUp(self):
        self.app = create_app(test_config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(name="Raju Ahammed", email="raju@example.com")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()

            resume = Resume(
                user_id=user.id,
                filename="test_resume.pdf",
                extracted_skills='["Python", "SQL", "Flask"]',
                extracted_text="Experienced Python, SQL, and Flask developer.",
            )
            db.session.add(resume)
            pref = JobPreference(user_id=user.id, target_role="Python Developer", location="Remote")
            db.session.add(pref)
            db.session.commit()

    def test_public_pages(self):
        # 1. Landing Page
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        landing_html = res.get_data(as_text=True)
        self.assertIn("#features", landing_html)
        self.assertIn("https://opensource.org/licenses/MIT", landing_html)

        # 2. Login Page
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        login_html = res.get_data(as_text=True)
        self.assertIn("forgotPasswordModal", login_html)
        self.assertNotIn('href="#"', login_html)

        # 3. Register Page
        res = self.client.get("/register")
        self.assertEqual(res.status_code, 200)
        register_html = res.get_data(as_text=True)
        self.assertIn("legalModal", register_html)
        self.assertIn("openTermsModal", register_html)
        self.assertNotIn('href="#"', register_html)

    def test_auth_flow_and_protected_pages(self):
        # Login
        res = self.client.post("/login", data={"email": "raju@example.com", "password": "password123"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 4. Dashboard
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)

        # 5. Upload Resume Page
        res = self.client.get("/upload")
        self.assertEqual(res.status_code, 200)

        # 7. Job Preferences Page
        res = self.client.get("/preferences")
        self.assertEqual(res.status_code, 200)

        # 8. Job Recommendations Page
        res = self.client.get("/results")
        self.assertEqual(res.status_code, 200)

        # 9. Job Detail Page
        res = self.client.get("/job/0")
        self.assertEqual(res.status_code, 200)

        # 10. Saved Jobs Page
        res = self.client.get("/saved-jobs")
        self.assertEqual(res.status_code, 200)

        # 11. Profile & Settings Page
        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)

    def test_preferences_clearing_preferred_skills(self):
        self.client.post("/login", data={"email": "raju@example.com", "password": "password123"}, follow_redirects=True)
        # 1. Update preferences with skills
        self.client.post("/preferences", data={
            "target_role": "Python Developer",
            "preferred_skills": "Python, Django, FastAPI",
        }, follow_redirects=True)
        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertEqual(user.job_preference.skills_list, ["Python", "Django", "FastAPI"])

        # 2. Update preferences with empty skills string (must clear preferred_skills to "[]")
        self.client.post("/preferences", data={
            "target_role": "Python Developer",
            "preferred_skills": "",
        }, follow_redirects=True)
        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertEqual(user.job_preference.skills_list, [])
            self.assertEqual(user.job_preference.preferred_skills, "[]")

if __name__ == "__main__":
    unittest.main()
