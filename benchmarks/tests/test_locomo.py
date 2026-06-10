"""LoCoMo harness tests — run via Docker pytest."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from benchmarks.backends.full_context import FullContextBackend
from benchmarks.backends.observations import ObservationsBackend
from benchmarks.data.locomo_loader import (
    conversation_messages_for_ingest,
    conversation_to_messages,
    get_qa_pairs,
    load_samples,
    observation_messages,
    sample_observations,
    session_summary_messages,
    turn_lookup,
)
from benchmarks.metrics.judge import AnswerGrader
from benchmarks.metrics.tokens import count_tokens
from benchmarks.metrics.qa import (
    adversarial_passes,
    answer_in_context,
    grade_answer,
    list_answer_in_context,
    multihop_retrieval_hit,
    score_qa,
    status_answer_in_context,
    summarize_qa_results,
    temporal_relative_in_context,
)
from benchmarks.metrics.report import build_strength_summary
from benchmarks.runners.run_locomo import (
    backend_is_complete,
    resolve_backends,
    run_backend,
    score_row,
)


def test_load_mini_fixture():
    samples = load_samples()
    assert len(samples) >= 1
    assert samples[0]["sample_id"] == "condensate-mini-001"
    assert len(get_qa_pairs(samples[0])) == 5


def test_conversation_messages_for_ingest_includes_session_metadata():
    sample = load_samples()[0]
    messages = conversation_messages_for_ingest(sample["conversation"])
    assert any(msg.get("metadata", {}).get("session_date") for msg in messages)
    assert any(msg.get("metadata", {}).get("dia_id") for msg in messages)


def test_session_summary_messages_non_empty_for_locomo10():
    sample = load_samples(Path("benchmarks/data/locomo10.json"))[0]
    summaries = session_summary_messages(sample)
    assert len(summaries) > 0
    assert summaries[0]["metadata"].get("kind") == "session_summary"


def test_conversation_to_messages_preserves_sessions():
    sample = load_samples()[0]
    messages = conversation_to_messages(sample["conversation"])
    assert any("Seattle" in m["content"] for m in messages)
    assert any(m["role"] == "system" for m in messages)


def test_observation_messages_include_dia_id():
    sample = {
        "observation": {
            "session_1_observation": {
                "Caroline": [
                    ["Caroline attended an LGBTQ support group recently.", "D1:3"],
                ],
            }
        }
    }
    messages = observation_messages(sample)
    assert len(messages) == 1
    assert "D1:3" in messages[0]["content"]
    assert messages[0]["metadata"]["dia_id"] == "D1:3"


def test_adversarial_passes_uses_word_boundary_for_short_traps():
    assert adversarial_passes(
        "Caroline went to a support group yesterday.",
        "Yes",
    )
    assert not adversarial_passes(
        "Yes, Oscar belongs to Melanie.",
        "Yes",
    )


def test_multihop_retrieval_hit_when_evidence_complete():
    assert multihop_retrieval_hit(
        "Psychology, counseling certification",
        "Caroline is keen on counseling or working in mental health.",
        category="multi-hop",
        evidence_recall=1.0,
    )
    assert not multihop_retrieval_hit(
        "Psychology, counseling certification",
        "Caroline is keen on counseling or working in mental health.",
        category="multi-hop",
        evidence_recall=0.5,
    )
    assert multihop_retrieval_hit(
        "dinosaurs, nature",
        "Melanie took the kids hiking in nature.",
        category="single-hop",
        evidence_recall=1.0,
    )
    assert multihop_retrieval_hit(
        "LGBTQ+ individuals",
        "The agency supports many people.",
        category="open-domain",
        evidence_recall=1.0,
    )


def test_sample_observations_nested_locomo_shape():
    sample = {
        "observation": {
            "session_1_observation": {
                "Caroline": [
                    ["Caroline attended an LGBTQ support group recently.", "D1:3"],
                    ["Caroline is planning to continue her education.", "D1:9"],
                ],
                "Melanie": [
                    ["Melanie painted a lake sunrise last year.", "D1:14"],
                ],
            }
        }
    }
    lines = sample_observations(sample)
    assert len(lines) == 3
    assert any("LGBTQ support group" in line for line in lines)
    assert any("[D1:3]" in line for line in lines)


def test_sample_observations_locomo10_non_empty():
    locomo10 = Path(__file__).resolve().parents[1] / "data" / "locomo10.json"
    if not locomo10.exists():
        return
    samples = load_samples(locomo10)
    assert samples
    for sample in samples:
        assert len(sample_observations(sample)) > 0


def test_observations_backend_smaller_than_full_context():
    sample = load_samples()[0]
    session_id = sample["sample_id"]
    full = FullContextBackend()
    obs = ObservationsBackend()
    messages = conversation_to_messages(sample["conversation"])
    full.reset(session_id)
    full.add(session_id, messages)
    obs.load_observations(session_id, sample_observations(sample))
    query = get_qa_pairs(sample)[0]["question"]
    full_ctx = full.search(session_id, query)
    obs_ctx = obs.search(session_id, query)
    assert obs.token_count(obs_ctx) < full.token_count(full_ctx)


def test_observations_retrieval_hits_answers():
    sample = load_samples()[0]
    session_id = sample["sample_id"]
    backend = ObservationsBackend()
    backend.load_observations(session_id, sample_observations(sample))
    turns = turn_lookup(sample["conversation"])
    hits = 0
    for qa in get_qa_pairs(sample):
        context = backend.search(session_id, qa["question"])
        if score_qa(context, qa, turns)["retrieval_hit"]:
            hits += 1
    assert hits >= 4


def test_count_tokens_non_empty():
    assert count_tokens("hello world") >= 1


def test_answer_in_context_negative_answer():
    assert answer_in_context("No", "Work projects are PostgreSQL-only now after migration.")


def test_answer_in_context_temporal_last_year():
    ctx = "[session @ 1:56 pm on 8 May, 2023] Melanie: I painted that lake sunrise last year!"
    assert answer_in_context(2022, ctx)
    assert answer_in_context("2022", ctx)


def test_answer_in_context_temporal_month_year():
    ctx = "[session @ 1:56 pm on 8 May, 2023] Melanie: We're going camping in June 2023!"
    assert answer_in_context("June 2023", ctx)


def test_answer_in_context_list_and_status():
    ctx = "Melanie's kids love dinosaurs and nature walks."
    assert list_answer_in_context("dinosaurs, nature", ctx)
    status_ctx = "[observation D3:13] Caroline has known her friends for 4 years since moving, especially after a tough breakup."
    assert status_answer_in_context("Single", status_ctx)


def test_answer_in_context_temporal_relative():
    summer_ctx = "[session @ 1:14 pm on 25 May, 2023] Melanie: We're going camping in June 2023!"
    assert answer_in_context("June 2023", summer_ctx)


def test_multihop_retrieval_hit_partial_list_evidence():
    ctx = "[observation D1:9] Caroline is exploring career options in counseling or mental health."
    assert multihop_retrieval_hit(
        "Psychology, counseling certification",
        ctx,
        category="multi-hop",
        evidence_recall=0.5,
    ) is False
    rich_ctx = ctx + " Caroline is studying psychology and pursuing counseling certification."
    assert multihop_retrieval_hit(
        "Psychology, counseling certification",
        rich_ctx,
        category="multi-hop",
        evidence_recall=0.5,
    )


def test_grade_answer_local_match():
    ok, method = grade_answer("Seattle", "Seattle")
    assert ok and method == "substring"


def test_answer_grader_local_only():
    grader = AnswerGrader(use_llm_fallback=False)
    result = grader.grade("Where does she live?", "Seattle", "She lives in Seattle")
    assert result.correct
    assert result.grading_method.startswith("local_")


def test_run_backend_full_context_report():
    samples = load_samples()
    report = run_backend("full_context", samples)
    assert report["summary"]["total"] == 5
    assert report["summary"]["retrieval_accuracy"] >= 0.8


def test_strength_summary_prefers_observations():
    samples = load_samples()
    reports = {
        "full_context": run_backend("full_context", samples),
        "observations": run_backend("observations", samples),
    }
    strengths = build_strength_summary(reports)
    obs = strengths["comparisons"]["observations"]
    assert obs["token_savings_vs_full_context"] > 0.3


def test_resolve_backends_includes_structured():
    names = resolve_backends("all", skip_condensate=True)
    assert names == ["full_context", "observations", "structured"]


def test_full_context_skips_llm_grading():
    sample = load_samples()[0]
    session_id = sample["sample_id"]
    backend = FullContextBackend()
    messages = conversation_to_messages(sample["conversation"])
    backend.reset(session_id)
    backend.add(session_id, messages)
    turns = turn_lookup(sample["conversation"])
    qa = get_qa_pairs(sample)[0]
    grader = AnswerGrader(use_llm_fallback=False)

    scored = score_row("full_context", backend, session_id, qa, turns, grader)
    assert "graded_correct" not in scored


def test_backend_is_complete():
    samples = load_samples()
    report = {
        "backends": {
            "full_context": run_backend("full_context", samples),
        }
    }
    assert backend_is_complete(report, "full_context", samples)
    assert not backend_is_complete(report, "observations", samples)


def test_run_backend_resume_skips_completed_sample(tmp_path: Path):
    samples = load_samples()
    first = samples[0]
    initial = run_backend("full_context", [first])
    checkpoint_path = tmp_path / "resume-report.json"
    checkpoint_path.write_text(
        json.dumps({"backends": {"full_context": initial}}, indent=2),
        encoding="utf-8",
    )

    resumed = run_backend(
        "full_context",
        [first],
        resume=True,
        resume_sample_reports=initial["sample_reports"],
    )
    assert resumed["summary"]["total"] == initial["summary"]["total"]
    assert len(resumed["sample_reports"]) == 1


def test_run_locomo_cli_smoke(tmp_path: Path):
    out = tmp_path / "locomo-report.json"
    cmd = [
        sys.executable,
        "benchmarks/runners/run_locomo.py",
        "--backend",
        "all",
        "--skip-condensate",
        "--output",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["benchmark"] == "locomo"
    assert "observations" in payload["backends"]
    assert "structured" in payload["backends"]
    assert "grading_policy" in payload
    assert payload["condensate_strengths"]["comparisons"]["observations"]["token_savings_vs_full_context"] > 0
    assert "structured" in payload["condensate_strengths"]["comparisons"]


def test_build_strength_summary_condensate_headline():
    backends = {
        "full_context": {
            "summary": {
                "retrieval_accuracy": 0.8041,
                "avg_retrieved_tokens": 20475.72,
            }
        },
        "condensate": {
            "summary": {
                "retrieval_accuracy": 0.3212,
                "avg_retrieved_tokens": 131.8,
            }
        },
    }
    strengths = build_strength_summary(backends)
    headline = strengths["headline"]
    assert "99%" in headline or "32.1%" in headline
    assert "Run with --backend condensate" not in headline


def test_render_report_html_smoke(tmp_path: Path):
    from benchmarks.scripts.render_report_html import render_csv_file, render_markdown_file

    md = tmp_path / "sample.md"
    md.write_text("# Title\n\n| A | B |\n| - | - |\n| 1 | 2 |\n", encoding="utf-8")
    render_markdown_file(md, tmp_path / "sample.html")
    html_text = (tmp_path / "sample.html").read_text(encoding="utf-8")
    assert "<table>" in html_text
    assert "Title" in html_text

    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("category,backend,accuracy\nsingle-hop,condensate,0.5\n", encoding="utf-8")
    render_csv_file(csv_path, tmp_path / "sample.csv.html")
    assert "50.0%" in (tmp_path / "sample.csv.html").read_text(encoding="utf-8")


def test_analyze_locomo_report_mini_fixture():
    from benchmarks.scripts.analyze_locomo_report import analyze_report, render_markdown

    payload = {
        "dataset": "mini",
        "samples_evaluated": 1,
        "total_qa_pairs": 2,
        "backends": {
            "full_context": {
                "sample_reports": [
                    {
                        "sample_id": "conv-mini",
                        "ingest_ms": 10.0,
                        "summary": {
                            "total": 2,
                            "retrieval_accuracy": 0.5,
                            "avg_retrieved_tokens": 100,
                            "avg_transcript_tokens": 1000,
                            "token_savings_vs_transcript": 0.9,
                        },
                        "qa_results": [
                            {
                                "question": "Q1?",
                                "answer": "A1",
                                "category": "single-hop",
                                "retrieval_hit": True,
                                "retrieved_tokens": 90,
                            },
                            {
                                "question": "Q2?",
                                "answer": "A2",
                                "category": "temporal",
                                "retrieval_hit": False,
                                "retrieved_tokens": 110,
                                "native_answer": "unknown",
                                "evidence_ids": ["D1:1"],
                            },
                        ],
                    }
                ]
            }
        },
    }
    analysis = analyze_report(payload)
    assert analysis["misses_by_category"]["full_context"]["temporal"]["misses"] == 1
    assert "temporal" in analysis["example_misses"]["full_context"]
    markdown = render_markdown(analysis)
    assert "Miss counts by category" in markdown
    assert "conv-mini" in markdown

