import unittest

from generation.heuristics import extract_completed_actions, extract_pending_tasks


class TaskExtractionTests(unittest.TestCase):
    def test_completed_action_does_not_hide_following_pending_task(self):
        note = "I finished class and need to email my teammate tomorrow."

        self.assertEqual(extract_completed_actions(note), ["Class"])
        self.assertEqual(
            extract_pending_tasks(note), ["Email my teammate tomorrow"]
        )

    def test_completed_action_is_not_added_as_a_pending_task(self):
        note = "I finished the assignment and went home."

        self.assertEqual(extract_completed_actions(note), ["The assignment and went home"])
        self.assertEqual(extract_pending_tasks(note), [])

    def test_pending_action_after_completed_clause_is_extracted(self):
        note = "I completed the report; I should call my teammate."

        self.assertEqual(extract_completed_actions(note), ["The report"])
        self.assertEqual(extract_pending_tasks(note), ["Call my teammate"])


if __name__ == "__main__":
    unittest.main()
