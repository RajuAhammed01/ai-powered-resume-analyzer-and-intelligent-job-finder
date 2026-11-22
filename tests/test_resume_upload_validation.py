import io
import unittest
from werkzeug.datastructures import FileStorage
from app import create_app
from app.extensions import db
from app.models import User, Resume
from app.routes.resume import ALLOWED_EXTENSIONS, allowed_file
from app.services.resume_parser import validate_upload, is_valid_pdf, is_valid_docx


class TestResumeUploadValidation(unittest.TestCase):
    def setUp(self):
        self.app = create_app(test_config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": "/tmp/test_uploads",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(name="Test Candidate", email="candidate@example.com")
            user.set_password("SecurePassword123!")
            db.session.add(user)
            db.session.commit()

    def test_allowed_extensions_set(self):
        """Verify that legacy .doc is strictly excluded and only pdf/docx are allowed."""
        self.assertIn("pdf", ALLOWED_EXTENSIONS)
        self.assertIn("docx", ALLOWED_EXTENSIONS)
        self.assertNotIn("doc", ALLOWED_EXTENSIONS)
        self.assertNotIn("txt", ALLOWED_EXTENSIONS)

    def test_allowed_file_helper(self):
        """Test the allowed_file helper function for various filenames."""
        self.assertTrue(allowed_file("resume.pdf"))
        self.assertTrue(allowed_file("RESUME.PDF"))
        self.assertTrue(allowed_file("my_cv.docx"))
        self.assertTrue(allowed_file("my_cv.DOCX"))

        # Legacy .doc and unsupported extensions must be rejected
        self.assertFalse(allowed_file("legacy_resume.doc"))
        self.assertFalse(allowed_file("legacy_resume.DOC"))
        self.assertFalse(allowed_file("malicious.exe"))
        self.assertFalse(allowed_file("script.py"))
        self.assertFalse(allowed_file("plain.txt"))
        self.assertFalse(allowed_file("no_extension"))

    def test_validate_upload_magic_bytes(self):
        """Test validate_upload and magic-byte checks for PDF, DOCX, and legacy DOC."""
        # Valid PDF stream (%PDF-1.4...)
        pdf_bytes = io.BytesIO(b"%PDF-1.4 \x00\x01\x02")
        pdf_file = FileStorage(stream=pdf_bytes, filename="resume.pdf")
        self.assertTrue(validate_upload(pdf_file, "resume.pdf"))

        # Valid DOCX stream (PK\x03\x04...)
        docx_bytes = io.BytesIO(b"PK\x03\x04\x14\x00\x06\x00")
        docx_file = FileStorage(stream=docx_bytes, filename="resume.docx")
        self.assertTrue(validate_upload(docx_file, "resume.docx"))

        # Legacy OLE2 .doc stream (\xd0\xcf\x11\xe0...) - must fail validation
        legacy_doc_bytes = io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        doc_file = FileStorage(stream=legacy_doc_bytes, filename="resume.doc")
        self.assertFalse(validate_upload(doc_file, "resume.doc"))

        # Corrupted or disguised file (e.g. plain text saved as .docx)
        fake_docx_bytes = io.BytesIO(b"This is just plain text, not a zip/docx archive")
        fake_file = FileStorage(stream=fake_docx_bytes, filename="fake.docx")
        self.assertFalse(validate_upload(fake_file, "fake.docx"))

    def test_upload_endpoint_rejects_legacy_doc(self):
        """Test that uploading a .doc file to /upload is rejected before parsing."""
        # Log in
        self.client.post("/login", data={
            "email": "candidate@example.com",
            "password": "SecurePassword123!"
        }, follow_redirects=True)

        # Attempt to upload a .doc file
        doc_data = {
            "resume": (io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"), "old_resume.doc")
        }
        res = self.client.post("/upload", data=doc_data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Only PDF and DOCX files are allowed", res.data)

        # Ensure no resume was saved
        with self.app.app_context():
            resumes = Resume.query.all()
            self.assertEqual(len(resumes), 0)

    def test_upload_endpoint_rejects_corrupted_docx(self):
        """Test that uploading a file with valid .docx extension but invalid magic bytes is rejected."""
        self.client.post("/login", data={
            "email": "candidate@example.com",
            "password": "SecurePassword123!"
        }, follow_redirects=True)

        fake_docx_data = {
            "resume": (io.BytesIO(b"NOT_A_VALID_DOCX_HEADER"), "corrupted.docx")
        }
        res = self.client.post("/upload", data=fake_docx_data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Corrupted or invalid file format", res.data)

        with self.app.app_context():
            resumes = Resume.query.all()
            self.assertEqual(len(resumes), 0)


if __name__ == "__main__":
    unittest.main()
