import json
from pathlib import Path

def save_results(results, out_dir='eval/results'):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    name = Path(out_dir) / 'run_results.json'
    with open(name, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return str(name)
