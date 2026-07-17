import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, _PROJECT_ROOT)

from benchmark.report_generator import ReportGenerator

def test_report_generator():
    """Test report generator."""
    print("=== TESTING REPORT GENERATOR ===")
    
    generator = ReportGenerator()
    
    # Generate report for smalltest
    json_path = generator.generate_final_report(["smalltest"])
    print(f"✅ JSON report: {json_path}")
    
    # Generate markdown report
    md_path = generator.generate_markdown_report(["smalltest"])
    print(f"✅ Markdown report: {md_path}")

if __name__ == "__main__":
    test_report_generator()
