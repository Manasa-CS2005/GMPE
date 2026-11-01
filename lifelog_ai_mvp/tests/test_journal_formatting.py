import unittest

from generation.formatting import format_personal_journal


class PersonalJournalFormattingTests(unittest.TestCase):
    def test_formats_basic_personal_journal_sections_and_date(self):
        formatted = format_personal_journal(
            {
                "title": "Presentation day",
                "opening": "I presented my project.",
                "events": ["I met my classmates."],
                "achievements": ["I finished the presentation."],
                "challenges": ["I felt nervous beforehand."],
                "feelings": ["Nervous, then relieved."],
                "gratitude": ["My classmate helped me practice."],
                "reflection": "Preparation helped me feel ready.",
                "closing": "I am glad I finished.",
            },
            "2026-10-27",
            ["Email my teammate."],
        )

        self.assertIn("# Personal Journal — Presentation day", formatted)
        self.assertIn("**Date:** 2026-10-27", formatted)
        for heading in (
            "What happened today",
            "What went well",
            "Challenges",
            "How I felt",
            "Gratitude",
            "Reflection",
            "Looking ahead",
            "Closing",
        ):
            self.assertIn(f"## {heading}", formatted)
        self.assertIn("- I presented my project.", formatted)
        self.assertIn("- Email my teammate.", formatted)

    def test_empty_sections_are_labeled_without_inventing_content(self):
        formatted = format_personal_journal(
            {"title": "A quiet day"}, "2026-10-27"
        )

        self.assertEqual(formatted.count("Not mentioned in this note."), 8)
        self.assertNotIn("tomorrow will", formatted.lower())


if __name__ == "__main__":
    unittest.main()
