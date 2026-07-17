import os
import tempfile
import unittest
import zipfile
from ingestion.loader import load_repository

class TestLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.dir_path = self.test_dir.name

        # Create files
        self.py_path = os.path.join(self.dir_path, "main.py")
        with open(self.py_path, "w", encoding="utf-8") as f:
            f.write("def hello():\n    print('Hello World')")

        self.md_path = os.path.join(self.dir_path, "README.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write("# Hello\nThis is a readme.")

        self.json_path = os.path.join(self.dir_path, "config.json")
        with open(self.json_path, "w", encoding="utf-8") as f:
            f.write('{"debug": true}')

        self.png_path = os.path.join(self.dir_path, "image.png")
        with open(self.png_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_load_directory(self):
        loaded = list(load_repository(self.dir_path))
        file_paths = {f["file_path"] for f in loaded}
        
        self.assertIn("main.py", file_paths)
        self.assertIn("README.md", file_paths)
        self.assertIn("config.json", file_paths)
        self.assertNotIn("image.png", file_paths)

        # Check content of main.py
        py_file = next(f for f in loaded if f["file_path"] == "main.py")
        self.assertEqual(py_file["content"], "def hello():\n    print('Hello World')")
        self.assertEqual(py_file["repo_name"], os.path.basename(self.dir_path))
        self.assertEqual(py_file["branch"], "main")

    def test_load_zip(self):
        # Create a zip archive
        zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(zip_fd)
        try:
            with zipfile.ZipFile(zip_path, "w") as z:
                # Add files under a single top-level folder
                z.writestr("myrepo/main.py", "def hello():\n    pass")
                z.writestr("myrepo/README.md", "# README")
                z.writestr("myrepo/image.png", b"\x89PNG\r\n\x1a\n")

            loaded = list(load_repository(zip_path))
            file_paths = {f["file_path"] for f in loaded}
            
            # The top-level single directory 'myrepo/' should be stripped
            self.assertIn("main.py", file_paths)
            self.assertIn("README.md", file_paths)
            self.assertNotIn("image.png", file_paths)

            py_file = next(f for f in loaded if f["file_path"] == "main.py")
            self.assertEqual(py_file["content"], "def hello():\n    pass")
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

if __name__ == "__main__":
    unittest.main()
