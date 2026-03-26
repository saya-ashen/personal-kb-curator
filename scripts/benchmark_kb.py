#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
MEMLITE_DIR = ROOT_DIR / "memlite"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(MEMLITE_DIR) not in sys.path:
    sys.path.insert(0, str(MEMLITE_DIR))

from indexer import build_index  # type: ignore
from intake import import_document  # type: ignore
from rag import ask_with_citations  # type: ignore


@dataclass
class SamplePlan:
    target_size: int
    executed_size: int
    sampled: bool
    sample_size_override: int | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mem-lite KB benchmark runner")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path")
    parser.add_argument(
        "--target-size", type=int, required=True, help="Target corpus size"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Optional executed corpus size override (enables sampled mode)",
    )
    parser.add_argument(
        "--query-runs",
        type=int,
        default=40,
        help="Retrieval query repeats for p95/p99",
    )
    parser.add_argument(
        "--soak",
        action="store_true",
        help="Marks run as non-blocking 100k soak evidence",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output JSON path. Defaults to rag/index/benchmark-*.json",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep generated benchmark workspace for reproducibility",
    )
    return parser.parse_args()


def _mem_total_gb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    kib = float(parts[1])
                    return round(kib / (1024.0 * 1024.0), 2)
                except ValueError:
                    return None
    return None


def _storage_classification() -> str:
    rotational_flags: list[int] = []
    for queue_file in Path("/sys/block").glob("*/queue/rotational"):
        try:
            rotational_flags.append(int(queue_file.read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            continue
    if not rotational_flags:
        return "unknown"
    if any(flag == 0 for flag in rotational_flags):
        return "non-rotational-detected"
    return "rotational-only"


def _machine_metadata() -> dict[str, Any]:
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "memory_gb": _mem_total_gb(),
        "storage_classification": _storage_classification(),
        "baseline_spec": {
            "cpu_cores": 8,
            "memory_gb": 32,
            "storage": "NVMe SSD",
        },
    }


def _build_sample_plan(target_size: int, sample_size: int | None) -> SamplePlan:
    if sample_size is None:
        return SamplePlan(
            target_size=target_size,
            executed_size=target_size,
            sampled=False,
            sample_size_override=None,
        )
    bounded_sample = min(target_size, max(1, sample_size))
    return SamplePlan(
        target_size=target_size,
        executed_size=bounded_sample,
        sampled=bounded_sample != target_size,
        sample_size_override=sample_size,
    )


def _generate_documents(corpus_dir: Path, count: int) -> list[Path]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx in range(count):
        topic = idx % 25
        owner = idx % 9
        path = corpus_dir / f"bench-{idx:06d}.txt"
        body = (
            f"Project Alpha topic {topic} decision {idx}.\\n"
            f"Owner @owner{owner} approved milestone {idx % 7}.\\n"
            "This benchmark sample is generated for ingest and retrieval timing."
        )
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    return paths


def _run_ingest(workspace_root: Path, docs: list[Path]) -> dict[str, Any]:
    started = time.perf_counter()
    success_count = 0
    failed: list[str] = []
    for path in docs:
        try:
            import_document(workspace_root=workspace_root, path_or_url=str(path))
            success_count += 1
        except Exception as exc:  # pragma: no cover - evidence path
            failed.append(f"{path.name}: {exc.__class__.__name__}: {exc}")
    elapsed = time.perf_counter() - started
    throughput = (success_count / elapsed) * 60.0 if elapsed > 0 else None
    return {
        "seconds": round(elapsed, 6),
        "docs_attempted": len(docs),
        "docs_ingested": success_count,
        "docs_per_minute": round(throughput, 3) if throughput is not None else None,
        "failures": failed,
    }


def _run_index(workspace_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = build_index(workspace_root)
        elapsed = time.perf_counter() - started
        return {
            "seconds": round(elapsed, 6),
            "ok": True,
            "details": result,
        }
    except Exception as exc:  # pragma: no cover - evidence path
        elapsed = time.perf_counter() - started
        return {
            "seconds": round(elapsed, 6),
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def _latency_stats(values: list[float]) -> dict[str, float]:
    if len(values) < 2:
        return {
            "p95": values[0] if values else 0.0,
            "p99": values[0] if values else 0.0,
        }
    p95, p99 = (
        quantiles(values, n=100, method="inclusive")[94],
        quantiles(values, n=100, method="inclusive")[98],
    )
    return {"p95": round(p95, 6), "p99": round(p99, 6)}


def _run_retrieval(workspace_root: Path, runs: int) -> dict[str, Any]:
    latencies: list[float] = []
    errors: list[str] = []
    for idx in range(runs):
        query = f"project alpha decision topic {idx % 10}"
        started = time.perf_counter()
        try:
            ask_with_citations(
                workspace_root=workspace_root,
                question=query,
                filters=None,
                limit=8,
                use_cloud_generation=False,
                cloud_generator=None,
            )
            latencies.append(time.perf_counter() - started)
        except Exception as exc:  # pragma: no cover - evidence path
            errors.append(f"run-{idx}: {exc.__class__.__name__}: {exc}")
            break
    stats = _latency_stats(latencies) if latencies else {"p95": None, "p99": None}
    return {
        "runs": runs,
        "completed_runs": len(latencies),
        "p95_seconds": stats["p95"],
        "p99_seconds": stats["p99"],
        "errors": errors,
    }


def _gate_context(
    sample_plan: SamplePlan,
    soak_mode: bool,
) -> dict[str, Any]:
    mode = "sampled" if sample_plan.sampled else "full"
    return {
        "target_size": sample_plan.target_size,
        "executed_size": sample_plan.executed_size,
        "mode": mode,
        "sample_size_override": sample_plan.sample_size_override,
        "soak_mode": soak_mode,
        "spec_gate_profile": "10k_acceptance",
        "spec_gates_applicable": (
            sample_plan.target_size == 10000 and not sample_plan.sampled
        ),
    }


def _pass_fail(
    gate_context: dict[str, Any],
    index_info: dict[str, Any],
    ingest_info: dict[str, Any],
    retrieval_info: dict[str, Any],
) -> dict[str, Any]:
    gates_applicable = bool(gate_context.get("spec_gates_applicable"))
    index_seconds = index_info.get("seconds")
    ingest_throughput = ingest_info.get("docs_per_minute")
    p95 = retrieval_info.get("p95_seconds")
    p99 = retrieval_info.get("p99_seconds")
    ingest_success = ingest_info.get("docs_ingested") == ingest_info.get(
        "docs_attempted"
    ) and not ingest_info.get("failures")

    def check(applicable: bool, passed: bool | None, reason: str) -> dict[str, Any]:
        return {
            "applicable": applicable,
            "passed": passed if applicable else None,
            "reason": reason,
        }

    return {
        "index_duration_le_45m": check(
            gates_applicable,
            (
                bool(index_info.get("ok"))
                and isinstance(index_seconds, (int, float))
                and index_seconds <= 2700.0
            ),
            "full 10k run required for acceptance gate",
        )
        if index_seconds is not None
        else check(gates_applicable, None, "index duration unavailable"),
        "ingest_throughput_ge_20_docs_per_min": check(
            gates_applicable,
            (
                isinstance(ingest_throughput, (int, float))
                and ingest_throughput >= 20.0
                and ingest_success
            ),
            "requires ingest throughput threshold and zero ingest failures",
        )
        if ingest_throughput is not None
        else check(gates_applicable, None, "ingest throughput unavailable"),
        "retrieval_p95_lt_1_5s": check(
            gates_applicable,
            isinstance(p95, (int, float)) and p95 < 1.5,
            "full 10k run required for acceptance gate",
        )
        if p95 is not None
        else check(gates_applicable, None, "retrieval p95 unavailable"),
        "retrieval_p99_lt_2_5s": check(
            gates_applicable,
            isinstance(p99, (int, float)) and p99 < 2.5,
            "full 10k run required for acceptance gate",
        )
        if p99 is not None
        else check(gates_applicable, None, "retrieval p99 unavailable"),
    }


def main() -> None:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    sample_plan = _build_sample_plan(args.target_size, args.sample_size)
    benchmark_workspace = Path(
        tempfile.mkdtemp(prefix="kb-bench-", dir=str(workspace_root))
    )
    corpus_dir = benchmark_workspace / "corpus"

    run_started = datetime.now(timezone.utc).isoformat()
    generated_docs = _generate_documents(corpus_dir, sample_plan.executed_size)
    ingest_info = _run_ingest(benchmark_workspace, generated_docs)
    index_info = _run_index(benchmark_workspace)
    retrieval_info = _run_retrieval(benchmark_workspace, max(1, args.query_runs))
    gate_context = _gate_context(sample_plan, bool(args.soak))
    thresholds = _pass_fail(gate_context, index_info, ingest_info, retrieval_info)

    report = {
        "run_started_at": run_started,
        "workspace_root": str(workspace_root),
        "benchmark_workspace": str(benchmark_workspace)
        if args.keep_workspace
        else None,
        "benchmark_workspace_retained": bool(args.keep_workspace),
        "target_size": sample_plan.target_size,
        "executed_size": sample_plan.executed_size,
        "sampled": sample_plan.sampled,
        "soak_mode": bool(args.soak),
        "non_blocking_evidence": bool(args.soak),
        "machine": _machine_metadata(),
        "metrics": {
            "index_duration_seconds": index_info.get("seconds"),
            "ingest_throughput_docs_per_min": ingest_info.get("docs_per_minute"),
            "retrieval_p95_seconds": retrieval_info.get("p95_seconds"),
            "retrieval_p99_seconds": retrieval_info.get("p99_seconds"),
        },
        "gate_context": gate_context,
        "threshold_checks": thresholds,
        "details": {
            "ingest": ingest_info,
            "index": index_info,
            "retrieval": retrieval_info,
        },
        "known_gaps": [],
    }

    if sample_plan.sampled:
        report["known_gaps"].append(
            "Sampled run: executed_size is smaller than target_size; treat as indicative only."
        )
    if not gate_context["spec_gates_applicable"]:
        report["known_gaps"].append(
            "10k acceptance gates are not applicable for this run context."
        )
    if not index_info.get("ok"):
        report["known_gaps"].append(
            "Index build failed; retrieval thresholds are not representative."
        )
    if retrieval_info.get("errors"):
        report["known_gaps"].append(
            "Retrieval benchmark encountered errors before full run count."
        )

    output_path = (
        Path(args.output).resolve()
        if args.output
        else workspace_root
        / "rag"
        / "index"
        / (f"benchmark-{'soak-' if args.soak else ''}{sample_plan.target_size}.json")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["output_path"] = str(output_path)
    print(json.dumps(report, indent=2))

    if not args.keep_workspace:
        shutil.rmtree(benchmark_workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
