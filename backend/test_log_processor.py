import unittest

from log_processor import preprocess_logs


class PreprocessLogsTests(unittest.TestCase):
    def test_short_logs_are_returned_unchanged(self):
        logs = "\n".join(f"line {i}" for i in range(10))
        self.assertEqual(preprocess_logs(logs), logs)

    def test_long_logs_without_errors_keep_head_and_tail(self):
        lines = [f"info line {i}" for i in range(1200)]
        logs = "\n".join(lines)

        result = preprocess_logs(logs)

        self.assertIn("info line 0", result)
        self.assertIn("info line 1199", result)
        # nothing in the untouched middle should survive when there are no errors
        self.assertNotIn("info line 600", result)

    def test_error_context_is_captured_around_error_lines(self):
        lines = [f"info line {i}" for i in range(1000)]
        lines[500] = "ERROR something exploded"
        logs = "\n".join(lines)

        result = preprocess_logs(logs)

        self.assertIn("ERROR something exploded", result)
        # 10 lines of context before/after the error line should be preserved
        self.assertIn("info line 490", result)
        self.assertIn("info line 510", result)

    def test_duplicate_error_blocks_are_deduplicated(self):
        # Pad well past the head/tail window (500 lines each) so the
        # repeated error only survives through the dedup path, not head/tail.
        lines = [f"info line {i}" for i in range(600)]
        lines[550:560] = ["ERROR boom"] * 10
        lines += [f"info line {i}" for i in range(600, 1200)]
        logs = "\n".join(lines)

        result = preprocess_logs(logs)

        self.assertEqual(result.count("ERROR boom"), 1)

    def test_output_is_capped_at_max_chars(self):
        lines = [f"ERROR line {i} " + "x" * 100 for i in range(200)]
        logs = "\n".join(lines)

        result = preprocess_logs(logs, max_chars=500)

        self.assertLessEqual(len(result), 500)

    def test_case_insensitive_error_patterns_are_detected(self):
        lines = [f"info line {i}" for i in range(100)]
        lines[50] = "fatal: disk unmountable"
        logs = "\n".join(lines)

        result = preprocess_logs(logs)

        self.assertIn("fatal: disk unmountable", result)


if __name__ == "__main__":
    unittest.main()
