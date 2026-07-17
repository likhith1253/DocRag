import unittest
from ingestion.language_detect import detect_language

class TestLanguageDetect(unittest.TestCase):
    def test_extensions(self):
        self.assertEqual(detect_language("main.py"), "python")
        self.assertEqual(detect_language("src/index.js"), "javascript")
        self.assertEqual(detect_language("app/component.tsx"), "typescript")
        self.assertEqual(detect_language("README.md"), "markdown")
        self.assertEqual(detect_language("package.json"), "json")
        self.assertEqual(detect_language("config.YAML"), "yaml")
        self.assertEqual(detect_language("script.sh"), "bash")
        self.assertEqual(detect_language("unknown_file.xyz"), "unknown")
        self.assertEqual(detect_language("no_extension"), "unknown")

if __name__ == "__main__":
    unittest.main()
