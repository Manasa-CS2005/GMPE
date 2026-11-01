import io
import re
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from backend.main import create_app
from backend.models import AccountSession, AccountUser
from backend.security import hash_token, utc_now


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "auth.sqlite"
        self.sent_emails = []
        self.app = create_app(
            database_url=f"sqlite:///{database_path.as_posix()}",
            email_sender=lambda recipient, subject, body: self.sent_emails.append(
                (recipient, subject, body)
            ),
            create_schema=True,
            secure_cookies=False,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.csrf_client(self.client)

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.app.state.engine.dispose()
        self.temporary_directory.cleanup()

    @staticmethod
    def csrf_client(client):
        response = client.get("/api/auth/csrf")
        if response.status_code != 200:
            raise AssertionError(response.text)
        client.headers.update(
            {"X-CSRF-Token": client.cookies.get("lifelog_csrf", "")}
        )

    def register(self, email="alex@example.com", full_name="Alex Morgan"):
        response = self.client.post(
            "/api/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": "StrongPassword!42",
                "confirm_password": "StrongPassword!42",
            },
        )
        return response

    def email_token(self, purpose):
        matching = [
            item for item in self.sent_emails
            if purpose in item[1].lower() or (
                purpose == "verify" and "verification" in item[1].lower()
            )
        ]
        if not matching:
            raise AssertionError(f"No {purpose} email was sent.")
        link_match = re.search(r"https?://\S+", matching[-1][2])
        if link_match is None:
            raise AssertionError("Account email did not contain a link.")
        link = link_match.group(0)
        query = parse_qs(urlparse(link).query)
        return query[purpose][0]

    def verify_account(self, client=None):
        target_client = client or self.client
        token = self.email_token("verify")
        response = target_client.post("/api/auth/verify-email", json={"token": token})
        self.assertEqual(response.status_code, 200, response.text)

    def login(self, client=None, email="alex@example.com", remember_me=False):
        target_client = client or self.client
        response = target_client.post(
            "/api/auth/login",
            json={
                "email": email,
                "password": "StrongPassword!42",
                "remember_me": remember_me,
            },
        )
        return response

    def test_registration_validates_strength_confirmation_and_duplicates(self):
        weak = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "Alex",
                "email": "weak@example.com",
                "password": "weak",
                "confirm_password": "weak",
            },
        )
        self.assertEqual(weak.status_code, 422)

        mismatch = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "Alex",
                "email": "mismatch@example.com",
                "password": "StrongPassword!42",
                "confirm_password": "StrongPassword!43",
            },
        )
        self.assertEqual(mismatch.status_code, 422)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 409)
        with self.app.state.session_maker() as db:
            user = db.scalar(
                select(AccountUser).where(AccountUser.email == "alex@example.com")
            )
            self.assertTrue(user.password_hash.startswith("$argon2"))
            self.assertNotEqual(user.password_hash, "StrongPassword!42")

    def test_verification_required_login_session_remember_me_and_logout(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.login().status_code, 403)
        self.verify_account()

        regular_login = self.login()
        self.assertEqual(regular_login.status_code, 200, regular_login.text)
        self.assertNotRegex(regular_login.headers["set-cookie"], r"max-age=")
        self.client.post("/api/auth/logout")

        login = self.login(remember_me=True)
        self.assertEqual(login.status_code, 200, login.text)
        cookie = self.client.cookies.get("lifelog_session")
        self.assertTrue(cookie)
        self.assertTrue(login.headers.get("set-cookie", "").lower().find("httponly") >= 0)
        max_age_match = re.search(
            r"max-age=(\d+)", login.headers["set-cookie"], re.I
        )
        if max_age_match is None:
            raise AssertionError("Remember-me cookie has no persistent expiry.")
        self.assertGreaterEqual(int(max_age_match.group(1)), 29 * 24 * 60 * 60)
        self.assertEqual(self.client.get("/api/auth/me").json()["email"], "alex@example.com")

        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_verification_tokens_are_single_use(self):
        self.assertEqual(self.register().status_code, 201)
        token = self.email_token("verify")
        first = self.client.post("/api/auth/verify-email", json={"token": token})
        second = self.client.post("/api/auth/verify-email", json={"token": token})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

    def test_password_reset_is_single_use_and_revokes_sessions(self):
        self.assertEqual(self.register().status_code, 201)
        self.verify_account()
        self.assertEqual(self.login().status_code, 200)

        forgotten = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "alex@example.com"},
        )
        self.assertEqual(forgotten.status_code, 200)
        token = self.email_token("reset")
        payload = {
            "token": token,
            "password": "NewStrongPassword!52",
            "confirm_password": "NewStrongPassword!52",
        }
        reset = self.client.post("/api/auth/reset-password", json=payload)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/reset-password", json=payload).status_code, 400)
        self.assertEqual(self.login().status_code, 401)
        updated_login = self.client.post(
            "/api/auth/login",
            json={"email": "alex@example.com", "password": payload["password"]},
        )
        self.assertEqual(updated_login.status_code, 200)

    def test_profile_updates_and_avatar_are_account_scoped(self):
        self.assertEqual(self.register().status_code, 201)
        self.verify_account()
        self.assertEqual(self.login().status_code, 200)

        second_client = TestClient(self.app)
        second_client.__enter__()
        self.csrf_client(second_client)
        self.sent_emails.clear()
        self.assertEqual(self.register_for(second_client, "sam@example.com").status_code, 201)
        self.verify_account(second_client)
        self.assertEqual(
            self.login(second_client, "sam@example.com").status_code,
            200,
        )

        update = self.client.patch(
            "/api/profile",
            json={
                "full_name": "Alex Updated",
                "preferred_language": "en-US",
                "timezone": "Asia/Kolkata",
                "writing_style": "Concise",
                "journal_tone": "Calm",
                "interests": "reading",
                "goals": "write every day",
                "reminder_time": "08:30",
                "email_notifications": False,
                "in_app_notifications": True,
            },
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["email"], "alex@example.com")
        self.assertEqual(
            self.client.get("/api/profile?user_id=2").json()["email"],
            "alex@example.com",
        )
        self.assertEqual(second_client.get("/api/profile").json()["full_name"], "Sam Morgan")
        self.assertEqual(second_client.get("/api/profile/avatar").status_code, 404)

        image_buffer = io.BytesIO()
        Image.new("RGB", (8, 8), color="purple").save(image_buffer, format="PNG")
        uploaded = self.client.put(
            "/api/profile/avatar",
            files={"file": ("profile.png", image_buffer.getvalue(), "image/png")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        self.assertTrue(uploaded.json()["has_profile_image"])
        self.assertEqual(second_client.get("/api/profile/avatar").status_code, 404)
        second_client.close()

    def register_for(self, client, email):
        return client.post(
            "/api/auth/register",
            json={
                "full_name": "Sam Morgan",
                "email": email,
                "password": "StrongPassword!42",
                "confirm_password": "StrongPassword!42",
            },
        )

    def test_csrf_required_for_state_changes(self):
        client = TestClient(self.app)
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": "Alex",
                "email": "alex@example.com",
                "password": "StrongPassword!42",
                "confirm_password": "StrongPassword!42",
            },
        )
        self.assertEqual(response.status_code, 403)
        client.close()

    def test_login_rate_limit_and_session_expiration(self):
        for _ in range(10):
            response = self.client.post(
                "/api/auth/login",
                json={"email": "unknown@example.com", "password": "incorrect"},
            )
            self.assertEqual(response.status_code, 401)
        limited = self.client.post(
            "/api/auth/login",
            json={"email": "unknown@example.com", "password": "incorrect"},
        )
        self.assertEqual(limited.status_code, 429)

        self.assertEqual(self.register().status_code, 201)
        self.verify_account()
        self.assertEqual(self.login().status_code, 200)
        with self.app.state.session_maker() as db:
            record = db.scalar(
                select(AccountSession).where(
                    AccountSession.token_hash
                    == hash_token(self.client.cookies["lifelog_session"])
                )
            )
            record.expires_at = utc_now() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
