"""Text-level guards for play.yml; the workflow itself only runs on GitHub."""
import unittest
from pathlib import Path

TEXT = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "play.yml").read_text(encoding="utf-8")


class PlayWorkflow(unittest.TestCase):
    def test_checkout_uses_default_branch_tip(self):
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", TEXT)

    def test_failure_posts_fallback_comment(self):
        self.assertIn("if: failure()", TEXT)

    def test_ignores_non_play_issues(self):
        self.assertIn("if: startsWith(github.event.issue.title, 'play:')", TEXT)


if __name__ == "__main__":
    unittest.main()
