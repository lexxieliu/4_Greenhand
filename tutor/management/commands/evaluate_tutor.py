import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from tutor.eval.mock_context import DemoContext
from tutor.services import ask_tutor

CASES = Path(__file__).resolve().parents[2] / "eval" / "test_cases.json"
OUT_DIR = settings.BASE_DIR / "docs" / "ai_eval"


def _contains(text, pattern):
    """pattern is 'a|b|c': true if any alternative appears in the text."""
    return any(alt in text for alt in pattern.split("|"))


def check(case, result):
    """Automatic checks for one case. Returns a list of failed checks (empty = pass)."""
    failures = []
    if result["status"] != case["expect_status"]:
        failures.append(f"status {result['status']} (expected {case['expect_status']})")
    if result["status"] != "answer":
        return failures
    text = (result["answer"] + " " + " ".join(result["steps"])).lower()
    failures += [f"missing '{p}'" for p in case["must_include"] if not _contains(text, p)]
    failures += [f"mentions '{p}'" for p in case["must_not_include"] if _contains(text, p)]
    retrieved = [s["id"] for s in result["sources"]]
    if case["gold_sources"] and not set(case["gold_sources"]) & set(retrieved):
        failures.append("no relevant note retrieved")
    if not case["gold_sources"] and any(s["cited"] for s in result["sources"]):
        failures.append("cites notes although none cover the question")
    if case.get("expect_safety_warning") and not result["safety_warning"]:
        failures.append("no safety warning")
    return failures


def _shown(result):
    if result["status"] == "answer":
        return result["answer"] + " Steps: " + " / ".join(result["steps"])
    return result.get("reason") or result.get("message", "")


class Command(BaseCommand):
    help = "Run the tutor on the realistic test cases in tutor/eval/test_cases.json and save a report to docs/ai_eval/."

    def add_arguments(self, parser):
        parser.add_argument("--label", default="latest", help="Name of the report files (e.g. before, after).")
        parser.add_argument("--only", nargs="*", help="Run only these case ids.")
        parser.add_argument("--rescore", action="store_true",
                            help="Re-check a saved report with the current test cases instead of calling the models.")

    def handle(self, *args, **options):
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        if options["rescore"]:
            return self._rescore(cases, options["label"])
        if options["only"]:
            cases = [c for c in cases if c["id"] in options["only"]]
        rows = []
        for case in cases:
            start = time.perf_counter()
            result = ask_tutor(case["question"], case["plant"], source=DemoContext())
            seconds = round(time.perf_counter() - start, 2)
            failures = check(case, result)
            rows.append({"case": case, "result": result, "seconds": seconds, "failures": failures})
            mark = self.style.SUCCESS("PASS") if not failures else self.style.ERROR("FAIL " + "; ".join(failures))
            self.stdout.write(f"{case['id']:>3} {seconds:6.1f}s {mark}\n    {_shown(result)[:300]}")

        self._save(rows, options["label"])

    def _rescore(self, cases, label):
        path = OUT_DIR / f"results_{label}.json"
        rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
        by_id = {c["id"]: c for c in cases}
        for row in rows:
            row["case"] = by_id[row["case"]["id"]]
            row["failures"] = check(row["case"], row["result"])
        self._save(rows, label)

    def _save(self, rows, label):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"results_{label}.json").write_text(
            json.dumps({"model": settings.LOCAL_MODEL_ID, "embedding_model": settings.EMBEDDING_MODEL_ID, "rows": rows},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        (OUT_DIR / f"results_{label}.md").write_text(self._markdown(rows), encoding="utf-8")
        passed = sum(not r["failures"] for r in rows)
        model_rows = [r for r in rows if "latency_ms" in r["result"]]
        mean = sum(r["seconds"] for r in model_rows) / max(len(model_rows), 1)
        self.stdout.write(f"\n{passed}/{len(rows)} passed · mean latency of model calls {mean:.1f}s · "
                          f"report: docs/ai_eval/results_{label}.md")

    def _markdown(self, rows):
        lines = [
            f"# Tutor evaluation · model `{settings.LOCAL_MODEL_ID}` · embeddings `{settings.EMBEDDING_MODEL_ID}`", "",
            "| Id | Kind | Test input | Expected behavior | Actual output | Notes used (cited ✓) | Checks | Latency |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            case, result = row["case"], row["result"]
            notes = ", ".join(f"{s['id']}{' ✓' if s['cited'] else ''}" for s in result.get("sources", [])) or "–"
            checks = "pass" if not row["failures"] else "FAIL: " + "; ".join(row["failures"])
            scope = f" *(plant: {case['plant']})*" if case["plant"] else ""
            cells = [case["id"], case["kind"], case["question"].strip() + scope or "(empty)", case["expected"],
                     f"**{result['status']}** – {_shown(result)}", notes, checks, f"{row['seconds']} s"]
            lines.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |")
        return "\n".join(lines) + "\n"
