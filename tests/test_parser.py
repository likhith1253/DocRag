import unittest
from ingestion.parser import parse_code

class TestParser(unittest.TestCase):
    def test_parse_python(self):
        code = """import os
from sys import path

class MyClass(BaseClass):
    def hello(self):
        other_function()
        self.helper()

def global_func():
    print("global")
"""
        parsed = parse_code(code, "python")
        
        # Check classes
        self.assertEqual(len(parsed["classes"]), 1)
        self.assertEqual(parsed["classes"][0]["name"], "MyClass")
        self.assertEqual(parsed["classes"][0]["inherits"], ["BaseClass"])
        
        # Check functions
        self.assertEqual(len(parsed["functions"]), 2)
        func_names = {f["name"] for f in parsed["functions"]}
        self.assertEqual(func_names, {"hello", "global_func"})
        
        # Check parent classes
        hello_func = next(f for f in parsed["functions"] if f["name"] == "hello")
        self.assertEqual(hello_func["class_name"], "MyClass")
        
        # Check imports
        self.assertEqual(len(parsed["imports"]), 2)
        
        # Check calls
        self.assertTrue(len(parsed["calls"]) >= 2)
        call_targets = {c["callee"] for c in parsed["calls"]}
        self.assertIn("other_function", call_targets)
        self.assertIn("self.helper", call_targets)

    def test_parse_javascript(self):
        code = """import { foo } from 'bar';
class Widget extends BaseWidget {
  render() {
    setup();
  }
}
"""
        parsed = parse_code(code, "javascript")
        self.assertEqual(len(parsed["classes"]), 1)
        self.assertEqual(parsed["classes"][0]["name"], "Widget")
        self.assertEqual(parsed["classes"][0]["inherits"], ["BaseWidget"])
        self.assertEqual(len(parsed["functions"]), 1)
        self.assertEqual(parsed["functions"][0]["name"], "render")
        self.assertEqual(parsed["functions"][0]["class_name"], "Widget")

if __name__ == "__main__":
    unittest.main()
