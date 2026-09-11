"""Negative controls for the narrowly reviewed historical ceremony exceptions."""
import json
import unittest

from ingest_council_archive_decisions_build020 import NO_MOTION_PATH, reviewed_no_motion


class NoMotionBoundary(unittest.TestCase):
    def setUp(self):
        self.reviews = json.loads(NO_MOTION_PATH.read_text(encoding="utf-8"))["sources"]
        self.lines = [{"text": "Ceremony proceedings"} for _ in range(30)]

    def classify(self, source, lines=None, records=None, diagnostics=None):
        return reviewed_no_motion(source, self.lines if lines is None else lines,
                                  source["pdf_pages"], records or [],
                                  {"unpaired_result_lines": 0} if diagnostics is None else diagnostics)

    def test_exact_reviews(self):
        for source in self.reviews:
            self.assertEqual(self.classify(source), source)

    def test_changed_identity_remains_gap(self):
        for key in ("meeting_date", "minutes_url", "source_sha256", "pdf_pages"):
            with self.subTest(key=key):
                source = dict(self.reviews[0])
                source[key] = 99 if key == "pdf_pages" else "changed"
                self.assertIsNone(self.classify(source))

    def test_unreadable_unknown_or_motion_bearing_source_remains_gap(self):
        source = self.reviews[0]
        self.assertIsNone(self.classify(source, lines=[]))
        for text in ("MOTION PUT AND PASSED", "MOVED by A", "seconded by B"):
            self.assertIsNone(self.classify(source, lines=self.lines + [{"text": text}]))
        self.assertIsNone(self.classify(source, records=[{"decision_id": "observed"}]))
        self.assertIsNone(self.classify(source, diagnostics={"unpaired_result_lines": 1}))
        self.assertIsNone(self.classify(source, diagnostics={}))


if __name__ == "__main__":
    unittest.main()
