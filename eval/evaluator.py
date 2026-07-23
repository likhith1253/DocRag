import json
import time
from typing import List, Dict

from agents.orchestrator import Orchestrator
from storage.registry import get_registry
from storage.vector_store import VectorStoreManager

from eval.metrics import compute_metrics

class Evaluator:
    def __init__(self, dataset_path: str):
        with open(dataset_path, 'r', encoding='utf-8') as f:
            self.dataset = json.load(f)
        # attempt to load canonical expected answers mapping if present
        self.expected_map = {}
        try:
            with open('eval/ai_papers_expected_answers.json', 'r', encoding='utf-8') as f:
                expected_list = json.load(f)
                for item in expected_list:
                    # key by id if present, else by (paper, question)
                    if item.get('id'):
                        self.expected_map[item['id']] = item
                    else:
                        key = (item.get('paper',''), item.get('question',''))
                        self.expected_map[key] = item
        except Exception:
            # no expected mapping available
            self.expected_map = {}

        self.orch = Orchestrator()

    def _lookup_expected(self, it: Dict) -> str:
        # prefer explicit expected in dataset
        if it.get('expected_answer'):
            return it.get('expected_answer')
        if it.get('expected'):
            return it.get('expected')
        # try by id
        if it.get('id') and it['id'] in self.expected_map:
            return self.expected_map[it['id']].get('expected_answer','')
        # try by (paper, question)
        key = (it.get('paper',''), it.get('question',''))
        if key in self.expected_map:
            return self.expected_map[key].get('expected_answer','')
        # no expected found
        return ''

    def _find_repo_for_file(self, file_name: str):
        # Scan registry and check collections for a matching file in chunk metadata
        registry = get_registry()
        for rid, repo in registry.repositories.items():
            try:
                vman = VectorStoreManager(collection_name=repo.vector_collection)
                all_chunks = vman.get_all_chunks()
                for c in all_chunks:
                    if c.get('metadata', {}).get('file') == file_name:
                        return rid
            except Exception:
                continue
        return None

    def run(self, limit: int = None, dry_run: bool = False) -> List[Dict]:
        results = []
        items = self.dataset if limit is None else self.dataset[:limit]
        for it in items:
            q = it.get('question')
            expected = self._lookup_expected(it)
            start = time.time()
            # Orchestrator.answer returns a dict with keys including 'answer'
            try:
                # Prefer to find the repository/collection holding this file and call orchestrator with repo_id
                repo_id = self._find_repo_for_file(it.get('paper')) if it.get('paper') else None
                if repo_id:
                    res_dict = self.orch.answer(q, repo_id=repo_id)
                else:
                    # Fallback: use file metadata filter (best-effort) and search corpus-wide
                    res_dict = self.orch.answer(q, repo_id=None, filters={"file": it.get('paper')}, retrieval_mode='corpus')
                if isinstance(res_dict, dict):
                    answer_text = res_dict.get('answer', '')
                else:
                    answer_text = str(res_dict)
            except Exception:
                answer_text = ''
            elapsed = time.time() - start
            # get key concepts if present in expected_map
            key_concepts = []
            if it.get('id') and it.get('id') in self.expected_map:
                key_concepts = self.expected_map[it.get('id')].get('key_concepts', [])
            elif (it.get('paper',''), it.get('question','')) in self.expected_map:
                key_concepts = self.expected_map[(it.get('paper',''), it.get('question',''))].get('key_concepts', [])

            # retrieve the last logged retrieved_chunks for this question to compute grounding
            retrieved_text = self._get_retrieved_text_from_logs(q)
            # compute grounding: proportion of answer tokens found in retrieved_text
            grounding_score = 0.0
            if answer_text and retrieved_text:
                answer_tokens = [t for t in answer_text.lower().split() if len(t) > 3]
                matches = sum(1 for t in answer_tokens if t in retrieved_text.lower())
                grounding_score = round((matches / max(1, len(answer_tokens))) * 100, 2)

            metrics = compute_metrics(expected, answer_text, key_concepts)
            # override grounding score with retrieval-grounded score (more accurate)
            metrics['grounding_score_percent'] = grounding_score

            metrics.update({'latency': round(elapsed,4)})
            results.append({
                'id': it.get('id', None),
                'paper': it.get('paper'),
                'question': q,
                'expected': expected,
                'answer': answer_text,
                'metrics': metrics
            })
        # end for

        return results

    def _get_retrieved_text_from_logs(self, question: str) -> str:
        import os
        logs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'query_logs.jsonl')
        if not os.path.exists(logs_path):
            return ''
        retrieved_texts = []
        try:
            with open(logs_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get('question') == question:
                            chunks = entry.get('retrieved_chunks', [])
                            for c in chunks:
                                retrieved_texts.append(c.get('content',''))
                    except Exception:
                        continue
        except Exception:
            return ''
        return ' '.join(retrieved_texts)
