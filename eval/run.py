#!/usr/bin/env python3
import sys, os
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import argparse
from datetime import datetime
from eval.evaluator import Evaluator
from eval.compare import save_results

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', default='eval/dataset/ai_papers.json')
parser.add_argument('--limit', type=int, default=1)
parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run: exercise retrieval and pipeline without heavy reporting')

if __name__ == '__main__':
    args = parser.parse_args()
    ev = Evaluator(args.dataset)
    results = ev.run(limit=args.limit, dry_run=args.dry_run)
    out_dir = f"eval/results/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    saved = save_results(results, out_dir=out_dir)
    print('Saved results to', saved)
