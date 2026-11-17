import base64
import io
import os
import re
import shutil
import tempfile
import unittest
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import JobPreference, LoginHistory, Resume, User


class TestProfileSettings(unittest.TestCase):
    def setUp(self):
        self.temp_upload_dir = tempfile.mkdtemp()
        avatar_dir = os.path.join(self.temp_upload_dir, "avatars")
        os.makedirs(avatar_dir, exist_ok=True)

        self.app = create_app(test_config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": self.temp_upload_dir,
            "AVATAR_FOLDER": avatar_dir,
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(
                name="Raju Ahammed",
                email="raju@example.com",
                phone="+8801700000000",
                location="Dhaka, Bangladesh",
                title_role="Backend Developer",
                linkedin_url="https://linkedin.com/in/raju-test",
            )
            user.set_password("OldPass123!")
            db.session.add(user)
            db.session.commit()

            resume = Resume(
                user_id=user.id,
                filename="Raju_Resume.pdf",
                extracted_skills='["Python", "Django", "Flask", "PostgreSQL"]',
                extracted_text="Experienced Backend Developer with Python, Django, Flask, PostgreSQL.",
                education="B.Sc. in Computer Science & Engineering",
                experience="Backend Engineer at TechCorp (2022 - Present)",
                ats_score=88,
            )
            db.session.add(resume)
            pref = JobPreference(
                user_id=user.id,
                target_role="Backend Developer",
                location="Dhaka, Bangladesh",
                location_preference="Hybrid",
                experience_level="Mid Level",
                job_type="Full-time",
            )
            db.session.add(pref)
            db.session.commit()

    def login(self):
        return self.client.post(
            "/login",
            data={"email": "raju@example.com", "password": "OldPass123!"},
            follow_redirects=True,
        )

    def test_profile_page_renders_redesigned_ui(self):
        """Verify the profile page renders modern tabs, hero cards, password inputs, and strength indicators."""
        self.login()
        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        # Top hero card & completion meter
        self.assertIn("Profile & Security Settings", html)
        self.assertIn("Profile Strength", html)
        self.assertIn("Raju Ahammed", html)
        self.assertIn("Backend Developer", html)

        # Tab navigation
        self.assertIn("Personal Information", html)
        self.assertIn("Security & Password", html)
        self.assertIn("Resume & Career Profile", html)
        self.assertIn("Account Preferences", html)

        # Password management section
        self.assertIn("current_password", html)
        self.assertIn("new_password", html)
        self.assertIn("confirm_password", html)
        self.assertIn("togglePasswordVisibility", html)
        self.assertIn("strengthLabel", html)
        self.assertIn("strengthSegment", html)
        self.assertIn("ruleLength", html)
        self.assertIn("ruleUppercase", html)
        self.assertIn("ruleLowercase", html)
        self.assertIn("ruleNumberOrSymbol", html)
        self.assertIn("ruleDifferent", html)
        self.assertIn("matchStatusBadge", html)

    def test_update_profile_details(self):
        """Test updating profile information via the personal details form."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "update_profile",
                "name": "Raju Updated",
                "phone": "+8801999999999",
                "location": "Remote, Global",
                "title_role": "Senior Python Architect",
                "date_of_birth": "1998-05-15",
                "linkedin_url": "https://linkedin.com/in/raju-updated",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Profile information updated successfully", html)

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertEqual(user.name, "Raju Updated")
            self.assertEqual(user.phone, "+8801999999999")
            self.assertEqual(user.location, "Remote, Global")
            self.assertEqual(user.title_role, "Senior Python Architect")
            self.assertEqual(user.linkedin_url, "https://linkedin.com/in/raju-updated")

    def test_change_password_success(self):
        """Test successfully changing the password with a strong, secure new password."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "NewStrongPass456#",
                "confirm_password": "NewStrongPass456#",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Password updated successfully", html)

        # Verify old password no longer works and new password works
        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertFalse(user.check_password("OldPass123!"))
            self.assertTrue(user.check_password("NewStrongPass456#"))

            # Verify security audit login history record
            history = LoginHistory.query.filter_by(user_id=user.id).all()
            self.assertTrue(any("Password changed" in (h.failure_reason or "") for h in history))

        # Verify login with new password
        self.client.get("/logout", follow_redirects=True)
        login_res = self.client.post(
            "/login",
            data={"email": "raju@example.com", "password": "NewStrongPass456#"},
            follow_redirects=True,
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("Dashboard", login_res.data.decode("utf-8"))

    def test_change_password_incorrect_current_password(self):
        """Test failure when current password provided is incorrect."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "WrongPassword123!",
                "new_password": "NewStrongPass456#",
                "confirm_password": "NewStrongPass456#",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Current password is incorrect", html)

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertTrue(user.check_password("OldPass123!"))

    def test_change_password_reusing_current_password(self):
        """Test failure when user tries to reuse their existing current password."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "OldPass123!",
                "confirm_password": "OldPass123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("New password cannot be the same as your current password", html)

    def test_change_password_mismatched_confirmation(self):
        """Test failure when new password and confirmation password do not match."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "NewStrongPass456#",
                "confirm_password": "DifferentPass789#",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("do not match", html)

    def test_change_password_too_short(self):
        """Test failure when new password is fewer than 8 characters."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "Short1!",
                "confirm_password": "Short1!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("at least 8 characters", html)

    def test_change_password_missing_complexity(self):
        """Test failure when new password lacks uppercase, lowercase, or digits/symbols."""
        self.login()
        # Missing uppercase
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "nouppercase123!",
                "confirm_password": "nouppercase123!",
            },
            follow_redirects=True,
        )
        self.assertIn("uppercase letter", res.data.decode("utf-8"))

        # Missing lowercase
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "NOLOWERCASE123!",
                "confirm_password": "NOLOWERCASE123!",
            },
            follow_redirects=True,
        )
        self.assertIn("lowercase letter", res.data.decode("utf-8"))

        # Missing number or symbol
        res = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "OldPass123!",
                "new_password": "NoDigitsOrSpecialChars",
                "confirm_password": "NoDigitsOrSpecialChars",
            },
            follow_redirects=True,
        )
        self.assertIn("number or special character", res.data.decode("utf-8"))

    def test_update_settings_preferences(self):
        """Test updating language, theme, and notification preferences."""
        self.login()
        res = self.client.post(
            "/profile",
            data={
                "action": "update_settings",
                "theme": "Dark",
                "language": "French",
                "notifications_enabled": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("settings updated successfully", html.lower())

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertEqual(user.theme, "Dark")
            self.assertEqual(user.language, "French")
            self.assertTrue(user.notifications_enabled)

    def tearDown(self):
        if hasattr(self, "temp_upload_dir") and os.path.exists(self.temp_upload_dir):
            shutil.rmtree(self.temp_upload_dir, ignore_errors=True)

    def _create_test_image(self, width=120, height=120, format="PNG"):
        img = Image.new("RGB", (width, height), color=(26, 109, 247))
        buf = io.BytesIO()
        img.save(buf, format=format)
        buf.seek(0)
        return buf

    def test_avatar_upload_direct_file(self):
        """Test uploading a profile picture via direct image file submission."""
        self.login()
        img_buf = self._create_test_image(format="JPEG")
        res = self.client.post(
            "/profile",
            data={
                "action": "upload_avatar",
                "avatar_file": (img_buf, "my_avatar.jpg", "image/jpeg"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("profile picture updated successfully", html.lower())

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertTrue(user.profile_image)
            self.assertTrue(user.profile_image.endswith(".jpg"))
            self.assertIn("/avatar/", user.avatar_url)

            # Verify file exists on disk in avatar folder
            avatar_path = os.path.join(self.app.config["AVATAR_FOLDER"], user.profile_image)
            self.assertTrue(os.path.isfile(avatar_path))

    def test_avatar_upload_cropped_base64(self):
        """Test uploading avatar via interactive cropper base64 payload."""
        self.login()
        img_buf = self._create_test_image(format="PNG")
        b64_str = base64.b64encode(img_buf.getvalue()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_str}"

        res = self.client.post(
            "/profile",
            data={
                "action": "upload_avatar",
                "avatar_cropped_data": data_url,
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("profile picture updated successfully", html.lower())

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertTrue(user.profile_image)
            self.assertTrue(user.profile_image.endswith(".png"))

    def test_avatar_remove(self):
        """Test removing a custom profile picture restores default avatar."""
        self.login()
        # First set an avatar
        img_buf = self._create_test_image()
        self.client.post(
            "/profile",
            data={"action": "upload_avatar", "avatar_file": (img_buf, "test.png")},
            content_type="multipart/form-data",
        )

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            old_filename = user.profile_image
            self.assertTrue(old_filename)

        # Now remove avatar
        res = self.client.post(
            "/profile",
            data={"action": "remove_avatar"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("profile picture removed successfully", html.lower())

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertEqual(user.profile_image, "")
            self.assertIsNone(user.avatar_url)

            # Verify file was cleaned up from disk
            old_path = os.path.join(self.app.config["AVATAR_FOLDER"], old_filename)
            self.assertFalse(os.path.exists(old_path))

    def test_avatar_validation_invalid_format(self):
        """Test rejecting non-image files such as .txt or .exe."""
        self.login()
        fake_file = io.BytesIO(b"not an image file")
        res = self.client.post(
            "/profile",
            data={"action": "upload_avatar", "avatar_file": (fake_file, "script.sh")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("invalid file format", html.lower())

    def test_avatar_validation_oversized(self):
        """Test rejecting oversized images exceeding 5MB."""
        self.login()
        # Direct file exceeding MAX_CONTENT_LENGTH returns 413 Payload Too Large
        huge_bytes = io.BytesIO(b"0" * (5 * 1024 * 1024 + 1024))
        res = self.client.post(
            "/profile",
            data={"action": "upload_avatar", "avatar_file": (huge_bytes, "huge.png")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 413)

        # Cropped base64 string exceeding 5MB within custom handler
        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            self.assertEqual(user.profile_image, "")

    def test_avatar_serving_and_traversal_protection(self):
        """Test /avatar/<filename> endpoint and security traversal defenses."""
        self.login()
        img_buf = self._create_test_image(format="PNG")
        self.client.post(
            "/profile",
            data={"action": "upload_avatar", "avatar_file": (img_buf, "user_avatar.png")},
            content_type="multipart/form-data",
        )

        with self.app.app_context():
            user = User.query.filter_by(email="raju@example.com").first()
            valid_name = user.profile_image

        # Serving valid avatar
        res = self.client.get(f"/avatar/{valid_name}")
        self.assertEqual(res.status_code, 200)

        # Path traversal should fail with 404
        bad_res = self.client.get("/avatar/../../config.py")
        self.assertEqual(bad_res.status_code, 404)

        # Missing file should 404
        missing_res = self.client.get("/avatar/non_existent_avatar.png")
        self.assertEqual(missing_res.status_code, 404)

    def test_avatar_renders_across_app_without_relogin(self):
        """Verify the avatar instantly updates across profile, dashboard, and topbar without re-logging in."""
        self.login()
        # Check initial state renders initial initials
        res_prof = self.client.get("/profile")
        self.assertIn("heroAvatarInitial", res_prof.data.decode("utf-8"))

        res_dash = self.client.get("/dashboard")
        self.assertIn("dashboard-avatar-placeholder", res_dash.data.decode("utf-8"))

        # Upload avatar
        img_buf = self._create_test_image(format="JPEG")
        self.client.post(
            "/profile",
            data={"action": "upload_avatar", "avatar_file": (img_buf, "avatar.jpg")},
            content_type="multipart/form-data",
        )

        # Without re-logging in, check profile page
        res_prof_after = self.client.get("/profile")
        html_prof = res_prof_after.data.decode("utf-8")
        self.assertIn("profile-avatar-img", html_prof)
        self.assertIn("/avatar/avatar_", html_prof)

        # Without re-logging in, check dashboard page
        res_dash_after = self.client.get("/dashboard")
        html_dash = res_dash_after.data.decode("utf-8")
        self.assertIn("dashboard-avatar-img", html_dash)
        self.assertIn("/avatar/avatar_", html_dash)

        # Check base topbar avatar
        self.assertIn("topbar-avatar-img", html_dash)

if __name__ == "__main__":
    unittest.main()
