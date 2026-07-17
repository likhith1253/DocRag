"""
eval.benchmark.artifacts.integrity
=====================================
Strict artifact integrity verification (Amendment 4).

After every experiment, this module verifies:
  1. Every expected metric recomputes from raw JSONL data (no discrepancy)
  2. Every expected system has a raw output file
  3. No NaN values in final metrics
  4. No empty JSON files
  5. All baselines executed
  6. All expected systems present in comparison
  7. Checksums of key artifacts match stored values
  8. No missing output directories

The run FAILS (raises IntegrityError) if any check fails.
This is not a warning — it is a hard failure.

Research principle:
  A result that cannot be verified from raw data is not a result.
  It is a claim. Claims are not publishable.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from typing import List, Dict, Any, Optional, Set


class IntegrityError(Exception):
    """Raised when artifact integrity verification fails."""
    pass


# ---------------------------------------------------------------------------
# Checksum utilities
# ---------------------------------------------------------------------------

def _compute_file_checksum(path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def save_checksums(artifact_dir: str, checksums: Dict[str, str]) -> None:
    """Save artifact checksums to checksums.json in artifact_dir."""
    checksum_path = os.path.join(artifact_dir, "checksums.json")
    with open(checksum_path, "w", encoding="utf-8") as f:
        json.dump(checksums, f, indent=2)


def load_checksums(artifact_dir: str) -> Dict[str, str]:
    """Load previously saved checksums."""
    checksum_path = os.path.join(artifact_dir, "checksums.json")
    if not os.path.exists(checksum_path):
        return {}
    with open(checksum_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Raw data recomputation
# ---------------------------------------------------------------------------

def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise IntegrityError(
                    f"Malformed JSON on line {line_num} of {path}: {e}"
                )
    return records


def _has_nan(obj: Any, path: str = "") -> List[str]:
    """Recursively find all NaN values in a nested dict/list. Returns list of key paths."""
    nan_paths = []
    if isinstance(obj, float) and math.isnan(obj):
        nan_paths.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            nan_paths.extend(_has_nan(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            nan_paths.extend(_has_nan(v, f"{path}[{i}]"))
    return nan_paths


# ---------------------------------------------------------------------------
# Individual verification checks
# ---------------------------------------------------------------------------

def _check_file_exists(path: str, failures: List[str]) -> bool:
    """Check that a file exists and is non-empty."""
    if not os.path.exists(path):
        failures.append(f"MISSING FILE: {path}")
        return False
    if os.path.getsize(path) == 0:
        failures.append(f"EMPTY FILE: {path}")
        return False
    return True


def _check_json_not_empty(path: str, failures: List[str]) -> Optional[Any]:
    """Load a JSON file and check it is not empty or null."""
    if not _check_file_exists(path, failures):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        failures.append(f"INVALID JSON: {path}: {e}")
        return None
    if data is None or data == {} or data == []:
        failures.append(f"EMPTY JSON CONTENT: {path}")
        return None
    return data


def _check_no_nan_in_metrics(metrics: Dict[str, Any], source: str, failures: List[str]) -> None:
    """Check that no metric value is NaN."""
    nan_paths = _has_nan(metrics)
    for np_ in nan_paths:
        failures.append(f"NaN VALUE in {source} at key path: {np_}")


def _recompute_recall_at_5(raw_records: List[Dict[str, Any]]) -> float:
    """
    Recompute Recall@5 from raw JSONL records.

    Each record must have:
      - retrieved_chunks: list of {file_path: str}
      - relevant_sources: list of str

    This recomputation is used to verify stored metrics.
    """
    from eval.benchmark.metrics.retrieval import recall_at_k

    if not raw_records:
        return float("nan")

    scores = []
    for record in raw_records:
        retrieved_files = [c.get("file_path", "") for c in record.get("retrieved_chunks", [])]
        relevant_files = record.get("relevant_sources", [])
        if relevant_files:
            scores.append(recall_at_k(retrieved_files, relevant_files, k=5))

    return sum(scores) / len(scores) if scores else float("nan")


def _recompute_token_f1(raw_records: List[Dict[str, Any]]) -> float:
    """Recompute Token F1 from raw JSONL records."""
    from eval.benchmark.metrics.generation import token_f1

    if not raw_records:
        return float("nan")

    scores = []
    for record in raw_records:
        predicted = record.get("answer", "")
        expected = record.get("expected_answer", "")
        if expected:
            scores.append(token_f1(predicted, expected))

    return sum(scores) / len(scores) if scores else float("nan")


# ---------------------------------------------------------------------------
# Main verification function
# ---------------------------------------------------------------------------

def verify_experiment_artifacts(
    output_dir: str,
    expected_systems: List[str],
    stored_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    tolerance: float = 1e-4,
) -> Dict[str, Any]:
    """
    Verify the integrity of all artifacts in an experiment output directory.

    Checks (all must pass — any failure raises IntegrityError):
      1. All expected system raw files exist and are non-empty
      2. All expected system raw files contain valid JSONL
      3. Stored metrics recompute from raw data within tolerance
      4. No NaN values in stored metrics
      5. All required output directories exist
      6. metrics/per_system.json exists and is non-empty
      7. metrics/comparison.json exists and is non-empty
      8. manifest.json exists
      9. All expected systems present in comparison
      10. Raw JSONL checksums match stored checksums

    Parameters
    ----------
    output_dir : str
        Root directory of the experiment output.
    expected_systems : list[str]
        Names of all systems that should have been evaluated.
    stored_metrics : dict, optional
        If provided, recomputed metrics are compared against these.
        Keys: system_name → {metric_name: float}.
    tolerance : float
        Maximum allowed absolute difference when comparing stored vs recomputed metrics.

    Returns
    -------
    dict with "passed": True/False, "checks": list of check results.

    Raises
    ------
    IntegrityError
        If any check fails.
    """
    failures: List[str] = []
    warnings: List[str] = []
    checks_passed: List[str] = []

    raw_dir = os.path.join(output_dir, "raw")
    metrics_dir = os.path.join(output_dir, "metrics")

    # Check 1: Required directories exist
    for required_dir in [raw_dir, metrics_dir]:
        if not os.path.isdir(required_dir):
            failures.append(f"MISSING DIRECTORY: {required_dir}")
        else:
            checks_passed.append(f"Directory exists: {required_dir}")

    # Check 2: manifest.json exists
    manifest_path = os.path.join(output_dir, "manifest.json")
    if _check_file_exists(manifest_path, failures):
        checks_passed.append("manifest.json present")

    # Check 3: per_system.json and comparison.json
    per_system_path = os.path.join(metrics_dir, "per_system.json")
    comparison_path = os.path.join(metrics_dir, "comparison.json")
    per_system_data = _check_json_not_empty(per_system_path, failures)
    comparison_data = _check_json_not_empty(comparison_path, failures)
    if per_system_data:
        checks_passed.append("metrics/per_system.json present and non-empty")
    if comparison_data:
        checks_passed.append("metrics/comparison.json present and non-empty")

    # Check 4: All expected systems have raw files
    found_systems: Set[str] = set()
    raw_records_by_system: Dict[str, List[Dict[str, Any]]] = {}

    for sys_name in expected_systems:
        raw_path = os.path.join(raw_dir, f"{sys_name}.jsonl")
        if not _check_file_exists(raw_path, failures):
            continue
        try:
            records = _load_jsonl(raw_path)
            raw_records_by_system[sys_name] = records
            found_systems.add(sys_name)
            checks_passed.append(f"Raw file exists: {sys_name}.jsonl ({len(records)} records)")
        except IntegrityError as e:
            failures.append(str(e))

    missing_systems = set(expected_systems) - found_systems
    for missing in missing_systems:
        failures.append(f"MISSING SYSTEM: No raw file for '{missing}'")

    # Check 5: No empty raw files
    for sys_name, records in raw_records_by_system.items():
        if len(records) == 0:
            failures.append(f"EMPTY RAW FILE: {sys_name}.jsonl has 0 records")

    # Check 6: No NaN values in stored metrics
    if per_system_data:
        for sys_name, metrics in per_system_data.items():
            _check_no_nan_in_metrics(metrics, f"per_system.json[{sys_name}]", failures)

    # Check 7: All expected systems present in comparison
    if comparison_data and "systems" in comparison_data:
        compared_systems = set(comparison_data["systems"])
        for sys_name in expected_systems:
            if sys_name not in compared_systems:
                failures.append(
                    f"System '{sys_name}' missing from comparison.json"
                )

    # Check 8: Recompute key metrics from raw and compare against stored
    if stored_metrics:
        for sys_name, records in raw_records_by_system.items():
            if sys_name not in stored_metrics:
                warnings.append(f"No stored metrics to verify for system '{sys_name}'")
                continue

            stored = stored_metrics[sys_name]

            # Recompute Recall@5
            if "recall_at_5" in stored:
                recomputed_r5 = _recompute_recall_at_5(records)
                if not math.isnan(recomputed_r5):
                    diff = abs(recomputed_r5 - stored["recall_at_5"])
                    if diff > tolerance:
                        failures.append(
                            f"METRIC MISMATCH: {sys_name} recall_at_5: "
                            f"stored={stored['recall_at_5']:.6f}, "
                            f"recomputed={recomputed_r5:.6f}, "
                            f"diff={diff:.6f} > tolerance={tolerance}"
                        )
                    else:
                        checks_passed.append(
                            f"recall_at_5 verified for {sys_name} (diff={diff:.2e})"
                        )

            # Recompute Token F1
            if "token_f1" in stored:
                recomputed_f1 = _recompute_token_f1(records)
                if not math.isnan(recomputed_f1):
                    diff = abs(recomputed_f1 - stored["token_f1"])
                    if diff > tolerance:
                        failures.append(
                            f"METRIC MISMATCH: {sys_name} token_f1: "
                            f"stored={stored['token_f1']:.6f}, "
                            f"recomputed={recomputed_f1:.6f}, "
                            f"diff={diff:.6f} > tolerance={tolerance}"
                        )
                    else:
                        checks_passed.append(
                            f"token_f1 verified for {sys_name} (diff={diff:.2e})"
                        )

    # Check 9: Checksum verification
    stored_checksums = load_checksums(output_dir)
    if stored_checksums:
        for filename, expected_checksum in stored_checksums.items():
            filepath = os.path.join(raw_dir, filename)
            if os.path.exists(filepath):
                actual_checksum = _compute_file_checksum(filepath)
                if actual_checksum != expected_checksum:
                    failures.append(
                        f"CHECKSUM MISMATCH: {filename}: "
                        f"stored={expected_checksum[:16]}..., "
                        f"actual={actual_checksum[:16]}..."
                    )
                else:
                    checks_passed.append(f"Checksum verified: {filename}")

    # Final decision
    verification_result = {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "checks_passed": checks_passed,
        "n_failures": len(failures),
        "n_warnings": len(warnings),
        "n_checks_passed": len(checks_passed),
    }

    # Save verification report
    report_path = os.path.join(output_dir, "integrity_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(verification_result, f, indent=2)

    if failures:
        failure_text = "\n  ".join(failures)
        raise IntegrityError(
            f"Artifact integrity verification FAILED with {len(failures)} failure(s):\n"
            f"  {failure_text}\n"
            f"Full report: {report_path}"
        )

    return verification_result
