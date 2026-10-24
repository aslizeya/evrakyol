"""Değerlendirme komut satırı aracı.

python -m app.evaluation check                    # vaka setini denetle (ücretsiz)
python -m app.evaluation review                   # onay dökümünü üret: eval/VAKALAR.md
python -m app.evaluation run --label taban        # çalıştır (gerçek LLM çağrıları; ücretli)
    [--retriever db|memory] [--reps 2] [--only miras_arac_01 ...] [--no-judge]
python -m app.evaluation report eval/runs/taban   # raporu yeniden üret
"""

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

from app.config import REPO_ROOT, get_settings
from app.evaluation.cases import DEFAULT_CASES, load_case_set, validate_case_set
from app.evaluation.report import write_report
from app.evaluation.review import render_review
from app.evaluation.runner import RunConfig, Runner, prepare_run_dir
from app.process_types import get_process_types


def cmd_check(args: argparse.Namespace) -> int:
    case_set = load_case_set(args.cases)
    problems = validate_case_set(case_set, list(get_process_types()))
    groups = Counter(c.group for c in case_set.vakalar)
    roadmap = sum(c.has_roadmap for c in case_set.vakalar)
    print(
        f"{len(case_set.vakalar)} vaka, {roadmap} yol haritası vakası, "
        f"{len(case_set.unsurlar)} unsur"
    )
    for group, n in sorted(groups.items()):
        print(f"  {group}: {n}")
    print(f"Doğrulanmamış: {sum(not c.dogrulandi for c in case_set.vakalar)}")
    for problem in problems:
        print(f"SORUN: {problem}")
    return 1 if problems else 0


def cmd_review(args: argparse.Namespace) -> int:
    case_set = load_case_set(args.cases)
    names = {p.code: p.name for p in get_process_types()} | {"kapsam_disi": "Kapsam dışı"}
    out = REPO_ROOT / "eval" / "VAKALAR.md"
    out.write_text(render_review(case_set, names), encoding="utf-8")
    print(f"Yazıldı: {out.relative_to(REPO_ROOT)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from app.llm import AnthropicProvider, DailyLimitedProvider

    settings = get_settings()
    case_set = load_case_set(args.cases)
    problems = validate_case_set(case_set, list(get_process_types()))
    if problems:
        print("Vaka seti tutarsız; önce `check` komutunu çalıştırın.", file=sys.stderr)
        return 1

    def provider(model: str):
        inner = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=model,
            effort=settings.llm_effort,
            use_fallbacks=settings.llm_fallbacks,
        )
        return DailyLimitedProvider(inner, settings.llm_daily_request_limit)

    if args.retriever == "db":
        from app.db import get_sessionmaker
        from app.embedding import get_embedder
        from app.rag.retrieval import HybridRetriever

        retriever = HybridRetriever(get_sessionmaker(), get_embedder())
    else:
        from app.rag.memory_retriever import InMemoryRetriever

        retriever = InMemoryRetriever()

    judge_model = None if args.no_judge else args.judge_model
    config = RunConfig(
        label=args.label,
        model=args.model,
        judge_model=judge_model,
        retriever=args.retriever,
        reps=args.reps,
        workers=args.workers,
        timeout_s=args.timeout_s,
        only=args.only or [],
    )
    out_dir = prepare_run_dir(config, args.cases, case_set)
    runner = Runner(
        config=config,
        case_set=case_set,
        process_types=list(get_process_types()),
        llm=provider(args.model),
        judge=provider(judge_model) if judge_model else None,
        retriever=retriever,
        out_dir=out_dir,
    )
    runner.run()
    report = write_report(out_dir)
    print(f"Rapor: {report.relative_to(REPO_ROOT)}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    report = write_report(Path(args.run_dir).resolve())
    print(f"Rapor: {report.relative_to(REPO_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="python -m app.evaluation", description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="vaka setini denetle").set_defaults(func=cmd_check)
    sub.add_parser("review", help="onay dökümünü üret").set_defaults(func=cmd_review)

    run = sub.add_parser("run", help="değerlendirmeyi çalıştır (ücretli)")
    run.add_argument("--label", required=True, help="çalıştırma adı, ör. taban")
    run.add_argument("--model", default=settings.llm_model)
    run.add_argument("--judge-model", default=settings.eval_judge_model)
    run.add_argument("--no-judge", action="store_true", help="uydurma yargıcını çalıştırma")
    run.add_argument("--retriever", choices=["db", "memory"], default="db")
    run.add_argument("--reps", type=int, default=1)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--timeout-s", type=float, default=300.0)
    run.add_argument("--only", nargs="+", help="yalnızca bu vaka kimlikleri")
    run.set_defaults(func=cmd_run)

    report = sub.add_parser("report", help="raporu yeniden üret")
    report.add_argument("run_dir")
    report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
