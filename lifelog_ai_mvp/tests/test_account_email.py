import os
import unittest
from unittest.mock import Mock, patch

from backend.mail import send_account_email


class AccountEmailTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "LIFELOG_EMAIL_BACKEND": "brevo",
            "LIFELOG_BREVO_API_KEY": "test-key",
            "LIFELOG_SMTP_FROM_EMAIL": "verified@example.com",
            "LIFELOG_EMAIL_FROM_NAME": "LifeLog Tests",
        },
        clear=False,
    )
    @patch("backend.mail.httpx.post")
    def test_brevo_sends_transactional_text_email(self, post):
        response = Mock()
        response.is_error = False
        response.status_code = 201
        post.return_value = response

        send_account_email(
            "user@example.com",
            "Verify your account",
            "Open the verification link.",
        )

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(kwargs["headers"]["api-key"], "test-key")
        self.assertEqual(
            kwargs["json"],
            {
                "sender": {
                    "name": "LifeLog Tests",
                    "email": "verified@example.com",
                },
                "to": [{"email": "user@example.com"}],
                "subject": "Verify your account",
                "textContent": "Open the verification link.",
            },
        )

    @patch.dict(
        os.environ,
        {
            "LIFELOG_EMAIL_BACKEND": "brevo",
            "LIFELOG_BREVO_API_KEY": "test-key",
            "LIFELOG_SMTP_FROM_EMAIL": "verified@example.com",
        },
        clear=False,
    )
    @patch("backend.mail.httpx.post")
    def test_provider_rejection_is_reported_as_delivery_failure(self, post):
        response = Mock()
        response.is_error = True
        response.status_code = 401
        post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            send_account_email("user@example.com", "Subject", "Body")

    @patch.dict(
        os.environ,
        {
            "LIFELOG_EMAIL_BACKEND": "brevo",
            "LIFELOG_BREVO_API_KEY": "",
            "LIFELOG_SMTP_FROM_EMAIL": "",
        },
        clear=False,
    )
    def test_brevo_requires_a_real_key_and_verified_sender(self):
        with self.assertRaisesRegex(ValueError, "LIFELOG_BREVO_API_KEY"):
            send_account_email("user@example.com", "Subject", "Body")


if __name__ == "__main__":
    unittest.main()
