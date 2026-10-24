"""Değerlendirme çalıştırıcısı.

Uygulamanın gerçek giriş noktalarını (`understand`, `RoadmapService`) çağırır; API'deki akışla
aynıdır. Çıktı düzeni (eval/runs/<çalıştırma>/):

    run.json        yapılandırma (modeller, arama türü, git sürümü, vaka dosyası özeti)
    results.jsonl   vaka x tekrar başına bir satır; satır vaka bitince yazılır
    errors.jsonl    puanlanabilir çıktı üretmeyen denemeler (API hatası, zaman aşımı, ...)
    traces/         vaka başına tüm LLM istekleri ve yanıtları

Yeniden çalıştırmada (vaka, tekrar) anahtarı results.jsonl'da olan denemeler atlanır.
"""

import json
import logging
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import REPO_ROOT
from app.evaluation.cases import Case, CaseSet, file_sha256
from app.evaluation.graders import grade_roadmap, grade_understanding, pii_leaked
from app.evaluation.judge import JudgeError, judge_roadmap
from app.llm import LLMError, LLMProvider, LLMResponse
from app.process_types import ProcessType
from app.rag.retrieval import Retriever
from app.rag.roadmap import RoadmapGenerationError, RoadmapService
from app.rag.understanding import UnderstandingError, understand

logger = logging.getLogger(__name__)

RUNS_DIR = REPO_ROOT / "eval" / "runs"

# Puanlanmış sonuç sayılan LLM durumları; diğer LLM hataları altyapı hatasıdır (errors.jsonl).
GRADED_LLM_REASONS = {"refusal": "refusal", "max_tokens": "truncated"}


@dataclass
class RecordedCall:
    stage: str
    system: str
    user: str
    response: str | None
    model: str | None
    usage: dict[str, int]
    latency_s: float
    error: str | None = None


class RecordingProvider:
    """Bir vakanın tüm LLM çağrılarını (istek, yanıt, kullanım, süre) kaydeder."""

    def __init__(self, inner: LLMProvider, stage: str):
        self.inner = inner
        self.stage = stage
        self.calls: list[RecordedCall] = []

    def generate_json(self, *, system: str, user: str, **kwargs) -> LLMResponse:
        started = time.perf_counter()
        try:
            response = self.inner.generate_json(system=system, user=user, **kwargs)
        except LLMError as exc:
            self.calls.append(
                RecordedCall(self.stage, system, user, None, None, {}, 0.0, error=exc.reason)
            )
            raise
        self.calls.append(
            RecordedCall(
                stage=self.stage,
                system=system,
                user=user,
                response=response.text,
                model=response.model,
                usage={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cache_read_input_tokens": response.cache_read_tokens,
                },
                latency_s=time.perf_counter() - started,
            )
        )
        return response


def _sum_usage(calls: list[RecordedCall]) -> dict[str, int]:
    total = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
    for call in calls:
        for key in total:
            total[key] += call.usage.get(key, 0)
    return total


@dataclass
class RunConfig:
    label: str
    model: str
    judge_model: str | None
    retriever: str  # "db" veya "memory"
    reps: int = 1
    workers: int = 4
    timeout_s: float = 300.0
    only: list[str] = field(default_factory=list)


@dataclass
class Attempt:
    row: dict | None = None
    error: dict | None = None
    trace: list[dict] = field(default_factory=list)


class Runner:
    def __init__(
        self,
        *,
        config: RunConfig,
        case_set: CaseSet,
        process_types: list[ProcessType],
        llm: LLMProvider,
        judge: LLMProvider | None,
        retriever: Retriever,
        out_dir: Path,
    ):
        self.config = config
        self.case_set = case_set
        self.process_types = process_types
        self.llm = llm
        self.judge = judge
        self.retriever = retriever
        self.out_dir = out_dir
        self._lock = threading.Lock()

    # --- tek deneme ---

    def run_attempt(self, case: Case, rep: int) -> Attempt:
        understand_llm = RecordingProvider(self.llm, "anlama")
        roadmap_llm = RecordingProvider(self.llm, "yol_haritasi")
        judge_llm = RecordingProvider(self.judge, "yargic") if self.judge else None
        started = time.perf_counter()
        grade: dict[str, float | None] = {}
        explanation: dict[str, str] = {}
        meta: dict = {"verified": case.dogrulandi}
        status = "ok"
        try:
            result = understand(case.metin, llm=understand_llm, process_types=self.process_types)
            grade |= grade_understanding(
                case,
                status=result.status,
                process_code=result.process.code if result.process else None,
                answers=result.answers,
                questions=result.questions,
            )
            meta["predicted"] = result.process.code if result.process else "kapsam_disi"
            meta["extracted_answers"] = result.answers

            if case.has_roadmap:
                # Yol haritası beklenen işlemle üretilir; böylece sınıflandırma hatası yol
                # haritası metriklerine karışmaz (iki yetenek ayrı ölçülür).
                process = next(p for p in self.process_types if p.code == case.beklenen_islem)
                outcome = RoadmapService(self.retriever, roadmap_llm).build(
                    case.metin, process, dict(case.cevaplar)
                )
                roadmap = outcome.roadmap.model_dump() if outcome.roadmap else None
                road_grade, road_explain = grade_roadmap(
                    case,
                    self.case_set,
                    status=outcome.status,
                    roadmap=roadmap,
                    dropped_steps=outcome.dropped_steps,
                )
                grade |= road_grade
                meta |= road_explain
                meta["roadmap_status"] = outcome.status
                meta["roadmap"] = roadmap
                meta["dropped_steps"] = outcome.dropped_steps
                meta["dropped_warnings"] = outcome.dropped_warnings
                grade["uydurmasiz"] = grade["desteklenmeyen"] = None
                if roadmap and judge_llm:
                    try:
                        verdict = judge_roadmap(judge_llm, roadmap, outcome.context)
                        grade["desteklenmeyen"] = verdict.unsupported_rate
                        grade["uydurmasiz"] = float(not verdict.unsupported)
                        meta["desteklenmeyen_iddialar"] = [
                            c.model_dump() for c in verdict.unsupported
                        ]
                        meta["iddia_sayisi"] = len(verdict.claims)
                    except (JudgeError, LLMError) as exc:
                        meta["judge_error"] = type(exc).__name__
        except LLMError as exc:
            if exc.reason not in GRADED_LLM_REASONS:
                return self._error(case, rep, "llm_" + exc.reason, [understand_llm, roadmap_llm])
            status = GRADED_LLM_REASONS[exc.reason]
        except (UnderstandingError, RoadmapGenerationError) as exc:
            status = "schema_failure"
            explanation["status"] = type(exc).__name__
        except Exception as exc:  # puanlayıcı veya çalıştırıcı hatası: model başarısızlığı değil
            logger.exception("Vaka çalıştırılamadı: %s", case.id)
            return self._error(case, rep, "harness_" + type(exc).__name__, [understand_llm])

        calls = understand_llm.calls + roadmap_llm.calls
        grade["pii_sizinti"] = pii_leaked(case, [c.user for c in calls])
        served = sorted({c.model for c in calls if c.model})
        meta["fallback_served"] = any(not m.startswith(self.config.model) for m in served)
        row = {
            "prompt_id": case.id,
            "rep": rep,
            "prompt": case.metin,
            "tags": case.etiketler,
            "status": status,
            "grade": grade,
            "explanation": explanation,
            "model": served[0] if len(served) == 1 else (served or None),
            "usage": _sum_usage(calls),
            "judge_model": self.config.judge_model if judge_llm and judge_llm.calls else None,
            "judge_usage": _sum_usage(judge_llm.calls) if judge_llm else None,
            "latency_s": round(sum(c.latency_s for c in calls), 3),
            "wall_s": round(time.perf_counter() - started, 3),
            "meta": meta,
        }
        all_calls = calls + (judge_llm.calls if judge_llm else [])
        return Attempt(row=row, trace=_trace(all_calls))

    def _error(self, case: Case, rep: int, kind: str, recorders: list) -> Attempt:
        calls = [c for r in recorders for c in r.calls]
        return Attempt(
            error={
                "prompt_id": case.id,
                "rep": rep,
                "failure_class": kind,
                "usage": _sum_usage(calls),
                "at": datetime.now(UTC).isoformat(),
            },
            trace=_trace(calls),
        )

    def _with_timeout(self, case: Case, rep: int) -> Attempt:
        box: list[Attempt] = []
        worker = threading.Thread(target=lambda: box.append(self.run_attempt(case, rep)))
        worker.daemon = True  # zaman aşımında arka planda kalan istek süreci bekletmesin
        worker.start()
        worker.join(self.config.timeout_s)
        if not box:
            return Attempt(
                error={
                    "prompt_id": case.id,
                    "rep": rep,
                    "failure_class": "timeout",
                    "at": datetime.now(UTC).isoformat(),
                }
            )
        return box[0]

    # --- tüm çalıştırma ---

    def _done_keys(self) -> set[tuple[str, int]]:
        path = self.out_dir / "results.jsonl"
        if not path.exists():
            return set()
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        return {(r["prompt_id"], r["rep"]) for r in rows}

    def _append(self, name: str, record: dict) -> None:
        with self._lock, (self.out_dir / name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _save(self, case: Case, rep: int, attempt: Attempt) -> None:
        if attempt.trace:
            path = self.out_dir / "traces" / f"{case.id}_rep{rep}.json"
            path.write_text(json.dumps(attempt.trace, ensure_ascii=False, indent=1), "utf-8")
        if attempt.row:
            self._append("results.jsonl", attempt.row)
        if attempt.error:
            self._append("errors.jsonl", attempt.error)

    def run(self, progress: Callable[[str], None] = print) -> Path:
        (self.out_dir / "traces").mkdir(parents=True, exist_ok=True)
        done = self._done_keys()
        cases = [
            c for c in self.case_set.vakalar if not self.config.only or c.id in self.config.only
        ]
        todo = [(c, r) for c in cases for r in range(self.config.reps) if (c.id, r) not in done]
        progress(f"{len(todo)} deneme çalıştırılacak ({len(done)} tanesi zaten var).")

        def work(item: tuple[Case, int]) -> None:
            case, rep = item
            attempt = self._with_timeout(case, rep)
            self._save(case, rep, attempt)
            label = attempt.row["status"] if attempt.row else attempt.error["failure_class"]
            progress(f"  {case.id} #{rep}: {label}")

        with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
            list(pool.map(work, todo))
        return self.out_dir


def _trace(calls: list[RecordedCall]) -> list[dict]:
    turns: list[dict] = []
    for call in calls:
        turns.append({"role": "system", "name": call.stage, "content": call.system})
        turns.append({"role": "user", "name": call.stage, "content": call.user})
        turns.append(
            {
                "role": "assistant",
                "name": call.stage,
                "content": call.response if call.response is not None else f"[hata: {call.error}]",
                "model": call.model,
            }
        )
    return turns


def git_revision() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def prepare_run_dir(config: RunConfig, cases_path: Path, case_set: CaseSet) -> Path:
    """Çalıştırma klasörünü hazırlar; aynı etiketle yeniden çalıştırma kaldığı yerden devam eder."""
    out_dir = RUNS_DIR / config.label
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "run.json"
    meta = {
        "label": config.label,
        "started_at": datetime.now(UTC).isoformat(),
        "model": config.model,
        "judge_model": config.judge_model,
        "retriever": config.retriever,
        "reps": config.reps,
        "git": git_revision(),
        "cases_file": str(cases_path.relative_to(REPO_ROOT)),
        "cases_sha256": file_sha256(cases_path),
        "case_count": len(case_set.vakalar),
        "unverified_cases": sum(not c.dogrulandi for c in case_set.vakalar),
    }
    if meta_path.exists():
        previous = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in ("model", "judge_model", "retriever", "cases_sha256"):
            if previous.get(key) != meta[key]:
                raise ValueError(
                    f"'{config.label}' çalıştırması farklı bir {key} ile başlatılmış; "
                    "yeni bir etiket kullanın."
                )
        meta["started_at"] = previous["started_at"]
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return out_dir
