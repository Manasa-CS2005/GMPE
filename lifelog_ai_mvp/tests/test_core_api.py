import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from backend.main import create_app


class CoreApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "core.sqlite"
        self.database_url = f"sqlite:///{database_path.as_posix()}"
        self.sent_emails = []
        self.app = create_app(
            database_url=self.database_url,
            email_sender=lambda recipient, subject, body: self.sent_emails.append(
                (recipient, subject, body)
            ),
            create_schema=True,
            secure_cookies=False,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.csrf_client(self.client)
        self.register_and_login(self.client, "alex@example.com")

    def test_account_endpoints_reject_unauthenticated_requests(self):
        client = TestClient(self.app)
        client.__enter__()
        self.csrf_client(client)

        for path in ("/api/auth/me", "/api/profile", "/api/memories", "/api/tasks"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 401)

        create_memory = client.post(
            "/api/memories",
            json={"title": "Private", "source_text": "Must require sign in."},
        )
        self.assertEqual(create_memory.status_code, 401)
        client.__exit__(None, None, None)

    def test_user_profile_memory_and_task_persist_across_app_restart(self):
        profile_update = self.client.patch(
            "/api/profile",
            json={
                "full_name": "Alex Persisted",
                "preferred_language": "en",
                "timezone": "Asia/Kolkata",
                "writing_style": "Concise",
                "journal_tone": "Calm",
                "interests": "reading",
                "goals": "write daily",
                "reminder_time": "08:30",
                "email_notifications": True,
                "in_app_notifications": False,
            },
        )
        self.assertEqual(profile_update.status_code, 200, profile_update.text)

        memory_response = self.client.post(
            "/api/memories",
            json={
                "title": "Persistent memory",
                "source_text": "This memory must survive an API restart.",
            },
        )
        self.assertEqual(memory_response.status_code, 201, memory_response.text)
        memory = memory_response.json()

        task_response = self.client.post(
            "/api/tasks",
            json={"title": "Persistent task", "memory_id": memory["id"]},
        )
        self.assertEqual(task_response.status_code, 201, task_response.text)
        task = task_response.json()

        restarted_app = create_app(
            database_url=self.database_url,
            email_sender=lambda *_args: None,
            create_schema=True,
            secure_cookies=False,
        )
        try:
            with TestClient(restarted_app) as restarted_client:
                restarted_client.cookies.set(
                    "lifelog_session",
                    self.client.cookies["lifelog_session"],
                )
                self.assertEqual(
                    restarted_client.get("/api/auth/me").json()["full_name"],
                    "Alex Persisted",
                )
                persisted_profile = restarted_client.get("/api/profile")
                self.assertEqual(persisted_profile.status_code, 200)
                self.assertEqual(persisted_profile.json()["timezone"], "Asia/Kolkata")
                self.assertEqual(
                    restarted_client.get("/api/memories").json()[0]["id"],
                    memory["id"],
                )
                self.assertEqual(
                    restarted_client.get("/api/tasks").json()[0]["id"],
                    task["id"],
                )
        finally:
            restarted_app.state.engine.dispose()

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

    def register_and_login(self, client, email):
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": email.split("@")[0],
                "email": email,
                "password": "StrongPassword!42",
                "confirm_password": "StrongPassword!42",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        link = self.sent_emails[-1][2]
        token = parse_qs(urlparse(re.search(r"https?://\S+", link).group(0)).query)[
            "verify"
        ][0]
        verified = client.post("/api/auth/verify-email", json={"token": token})
        self.assertEqual(verified.status_code, 200, verified.text)
        login = client.post(
            "/api/auth/login",
            json={"email": email, "password": "StrongPassword!42"},
        )
        self.assertEqual(login.status_code, 200, login.text)

    def other_account(self):
        client = TestClient(self.app)
        client.__enter__()
        self.csrf_client(client)
        self.register_and_login(client, "sam@example.com")
        return client

    def test_memory_crud_search_and_cross_user_isolation(self):
        created = self.client.post(
            "/api/memories",
            json={
                "title": "After class",
                "source_text": "I met Mina after class.",
                "result": {"journal": "We had a lovely afternoon."},
                "tags": "college, friends",
                "mood": "Sunny",
                "memory_date": "2026-10-30",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        memory = created.json()
        self.assertEqual(memory["source_text"], "I met Mina after class.")
        self.assertEqual(memory["result"], {"journal": "We had a lovely afternoon."})
        self.assertEqual(
            len(self.client.get("/api/memories", params={"search": "Mina"}).json()),
            1,
        )
        self.assertEqual(
            len(self.client.get("/api/memories", params={"search": "lovely afternoon"}).json()),
            1,
        )

        other = self.other_account()
        self.assertEqual(other.get("/api/memories").json(), [])
        self.assertEqual(
            other.patch(
                f"/api/memories/{memory['id']}",
                json={"title": "stolen"},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.delete(f"/api/memories/{memory['id']}").status_code,
            404,
        )

        updated = self.client.patch(
            f"/api/memories/{memory['id']}",
            json={"title": "A better title", "tags": "friends"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["title"], "A better title")
        self.assertEqual(
            self.client.delete(f"/api/memories/{memory['id']}").status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/memories").json(), [])
        other.__exit__(None, None, None)

    def test_task_crud_memory_ownership_and_cross_user_isolation(self):
        memory = self.client.post(
            "/api/memories",
            json={"title": "Day", "source_text": "I need to finish my report."},
        ).json()
        with patch("backend.main.email_delivery_configured", return_value=True):
            task_response = self.client.post(
                "/api/tasks",
                json={
                    "title": "Finish the report",
                    "memory_id": memory["id"],
                    "due_date": "2026-10-31",
                    "priority": "high",
                    "reminder_enabled": True,
                },
            )
        self.assertEqual(task_response.status_code, 201, task_response.text)
        task = task_response.json()
        self.assertEqual(task["memory_id"], memory["id"])
        self.assertEqual(task["priority"], "high")

        other = self.other_account()
        self.assertEqual(other.get("/api/tasks").json(), [])
        self.assertEqual(
            other.post(
                "/api/tasks",
                json={"title": "Invalid relation", "memory_id": memory["id"]},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.patch(
                f"/api/tasks/{task['id']}",
                json={"completed": True},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.delete(f"/api/tasks/{task['id']}").status_code,
            404,
        )

        completed = self.client.patch(
            f"/api/tasks/{task['id']}",
            json={"completed": True},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertTrue(completed.json()["completed"])
        self.assertEqual(
            self.client.delete(f"/api/tasks/{task['id']}").status_code,
            200,
        )
        other.__exit__(None, None, None)

    def test_reminder_requires_due_date_and_real_email_configuration(self):
        no_date = self.client.post(
            "/api/tasks",
            json={"title": "Task", "reminder_enabled": True},
        )
        self.assertEqual(no_date.status_code, 422)

        no_provider = self.client.post(
            "/api/tasks",
            json={
                "title": "Task",
                "due_date": "2026-10-31",
                "reminder_enabled": True,
            },
        )
        self.assertEqual(no_provider.status_code, 503)

    def test_mood_checkins_are_saved_per_account_and_day(self):
        first = self.client.put(
            "/api/moods",
            json={"mood": "Focused", "checkin_date": "2026-10-30"},
        )
        second = self.client.put(
            "/api/moods",
            json={"mood": "Soft", "checkin_date": "2026-10-30"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(self.client.get("/api/moods").json()), 1)
        self.assertEqual(self.client.get("/api/moods").json()[0]["mood"], "Soft")

        other = self.other_account()
        self.assertEqual(other.get("/api/moods").json(), [])
        other.__exit__(None, None, None)

    def test_generation_requires_a_configured_provider_and_returns_provider_output(self):
        request = {
            "source_text": "I finished the first page of my project.",
            "mode": "Simple Journal",
        }
        with patch("generation.client.api_key", return_value=""):
            unavailable = self.client.post("/api/generation", json=request)
        self.assertEqual(unavailable.status_code, 503)
        self.assertIn("LIFELOG_LLM_API_KEY", unavailable.json()["detail"])

        modes = (
            "Simple Journal",
            "Personal Persona",
            "Structured Day",
            "Reflection",
            "Explain Through an Analogy",
            "Vlog Creator",
            "Social Media",
            "Custom Prompt",
        )
        generated = {
            "journal": "I finished the first page of my project.",
            "structured_day": {"pending_tasks": []},
        }
        with patch("generation.client.api_key", return_value="configured"):
            for mode in modes:
                with self.subTest(mode=mode), patch(
                    "generation.pipeline.generate_lifelog",
                    return_value=(generated, "ai"),
                ) as generate:
                    response = self.client.post(
                        "/api/generation",
                        json={**request, "mode": mode},
                    )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), {"result": generated, "provider": "ai"})
                self.assertEqual(generate.call_args.args[1], mode)


if __name__ == "__main__":
    unittest.main()
