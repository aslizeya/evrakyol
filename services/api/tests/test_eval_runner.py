"""Çalıştırıcı ve raporun uçtan uca testi (sahte LLM, sahte arama; ücretsiz)."""

import json
from pathlib import Path

import pytest
from rag_fixtures import CHUNKS, GOOD_STEPS, FakeRetriever, roadmap_json, step

from app.evaluation.cases import load_case_set
from app.evaluation.judge import JUDGE_SYSTEM
from app.evaluation.report import render_markdown, summarize
from app.evaluation.runner import RunConfig, Runner
from app.llm import LLMError, LLMResponse
from app.process_types import get_process_types
from app.rag.prompts import ROADMAP_SYSTEM, UNDERSTANDING_SYSTEM

CASE_SET = load_case_set()


class RoutingFake:
    """İstemin türüne göre yanıt verir; vaka başına davranış `plan` ile değiştirilebilir."""

    def __init__(self, model: str = "claude-opus-5-5"):
        self.model = model
        self.understanding: dict[str, str | Exception] = {}
        self.roadmap: str | Exception = roadmap_json(GOOD_STEPS)
        self.judge: str = json.dumps({"iddialar": []})

    def generate_json(self, *, system: str, user: str, **_) -> LLMResponse:
        if system == UNDERSTANDING_SYSTEM:
            text = user.split("<kullanici_metni>")[1].split("</kullanici_metni>")[0]
            reply = self.understanding.get(text, "miras_arac_devri")
            if isinstance(reply, Exception):
                raise reply
            payload = json.dumps({"islem": reply, "gerekce": "g", "cevaplar": []})
            return LLMResponse(payload, self.model, input_tokens=100, output_tokens=10)
        if system == ROADMAP_SYSTEM:
            if isinstance(self.roadmap, Exception):
                raise self.roadmap
            return LLMResponse(self.roadmap, self.model, input_tokens=1000, output_tokens=500)
        if system == JUDGE_SYSTEM:
            return LLMResponse(self.judge, "claude-sonnet-5-5", input_tokens=800, output_tokens=200)
        raise AssertionError("bilinmeyen istem")


def make_runner(tmp_path: Path, llm: RoutingFake, judge: RoutingFake | None, only: list[str]):
    config = RunConfig(
        label="test", model="claude-opus-5-5", judge_model="claude-sonnet-5-5",
        retriever="memory", workers=1, timeout_s=30, only=only,
    )  # fmt: skip
    (tmp_path / "run.json").write_text(
        json.dumps({"label": "test", "model": config.model, "judge_model": config.judge_model,
                    "retriever": "memory", "reps": 1, "git": None, "cases_sha256": "0" * 64,
                    "case_count": len(CASE_SET.vakalar), "unverified_cases": 92}),
        "utf-8",
    )  # fmt: skip
    return Runner(
        config=config,
        case_set=CASE_SET,
        process_types=list(get_process_types()),
        llm=llm,
        judge=judge,
        retriever=FakeRetriever(CHUNKS),
        out_dir=tmp_path,
    )


def rows(path: Path, name: str = "results.jsonl") -> list[dict]:
    file = path / name
    return [json.loads(x) for x in file.read_text("utf-8").splitlines()] if file.exists() else []


def test_end_to_end_run_writes_rows_traces_and_report(tmp_path: Path) -> None:
    llm, judge = RoutingFake(), RoutingFake()
    runner = make_runner(tmp_path, llm, judge, ["miras_arac_01", "kapsam_disi_01", "pasaport_01"])
    llm.understanding["Babamdan kalan evi üzerime almak istiyorum."] = "kapsam_disi"
    llm.understanding["İlk defa pasaport çıkaracağım, nereye başvurmalıyım?"] = "pasaport"
    runner.run(progress=lambda _: None)

    results = {r["prompt_id"]: r for r in rows(tmp_path)}
    assert set(results) == {"miras_arac_01", "kapsam_disi_01", "pasaport_01"}
    miras = results["miras_arac_01"]
    assert miras["status"] == "ok"
    assert miras["grade"]["islem_dogru"] == 1.0
    assert miras["grade"]["uydurmasiz"] == 1.0
    assert (
        0 < miras["grade"]["unsur_kapsama"] < 1
    )  # örnek yol haritası unsurların bir kısmını içerir
    assert miras["model"] == "claude-opus-5-5"
    assert miras["usage"]["input_tokens"] == 1100
    assert miras["judge_usage"]["input_tokens"] == 800
    assert "roadmap_status" not in results["pasaport_01"]["meta"]  # yalnızca sınıflandırma
    trace = json.loads((tmp_path / "traces" / "miras_arac_01_rep0.json").read_text("utf-8"))
    assert [t["name"] for t in trace[::3]] == ["anlama", "yol_haritasi", "yargic"]

    summary = summarize(tmp_path)
    assert summary["metrics"]["islem_dogru"]["mean"] == 1.0
    assert summary["scope"]["kapsam_disi_duyarlilik"] == 1.0
    assert summary["cost_usd"] > 0
    markdown = render_markdown(summary, rows(tmp_path))
    assert "doğrulanmadı (taslak)" in markdown and "bellek içi" in markdown


def test_resume_skips_completed_attempts(tmp_path: Path) -> None:
    llm = RoutingFake()
    make_runner(tmp_path, llm, None, ["miras_arac_01"]).run(progress=lambda _: None)
    messages: list[str] = []
    make_runner(tmp_path, llm, None, ["miras_arac_01"]).run(progress=messages.append)
    assert len(rows(tmp_path)) == 1
    assert messages[0].startswith("0 deneme")


def test_infrastructure_errors_go_to_sidecar_not_results(tmp_path: Path) -> None:
    llm = RoutingFake()
    llm.understanding["İlk defa pasaport çıkaracağım, nereye başvurmalıyım?"] = LLMError(
        "api_error"
    )
    make_runner(tmp_path, llm, None, ["pasaport_01"]).run(progress=lambda _: None)
    assert rows(tmp_path) == []
    [error] = rows(tmp_path, "errors.jsonl")
    assert error["failure_class"] == "llm_api_error"
    assert summarize(tmp_path)["open_errors"] == 1


def test_refusal_and_schema_failure_are_graded_outcomes(tmp_path: Path) -> None:
    llm = RoutingFake()
    llm.roadmap = LLMError("refusal")
    make_runner(tmp_path, llm, None, ["miras_arac_01"]).run(progress=lambda _: None)
    llm.roadmap = "geçersiz json"
    make_runner(tmp_path, llm, None, ["miras_arac_02"]).run(progress=lambda _: None)
    statuses = {r["prompt_id"]: r["status"] for r in rows(tmp_path)}
    assert statuses == {"miras_arac_01": "refusal", "miras_arac_02": "schema_failure"}


def test_judge_flags_unsupported_claims(tmp_path: Path) -> None:
    llm, judge = RoutingFake(), RoutingFake()
    judge.judge = json.dumps(
        {"iddialar": [
            {"konum": "adım 1", "iddia": "Noter ücreti 500 TL", "destekleniyor": False,
             "kaynak": None, "gerekce": "Kaynakta ücret yok"},
            {"konum": "adım 1", "iddia": "Noterliğe gidilir", "destekleniyor": True,
             "kaynak": "K1", "gerekce": "K1"},
        ]}
    )  # fmt: skip
    make_runner(tmp_path, llm, judge, ["miras_arac_01"]).run(progress=lambda _: None)
    [row] = rows(tmp_path)
    assert row["grade"]["uydurmasiz"] == 0.0
    assert row["grade"]["desteklenmeyen"] == 0.5
    assert row["meta"]["desteklenmeyen_iddialar"][0]["iddia"] == "Noter ücreti 500 TL"


def test_fallback_model_is_recorded(tmp_path: Path) -> None:
    make_runner(tmp_path, RoutingFake(model="claude-opus-4-8"), None, ["pasaport_01"]).run(
        progress=lambda _: None
    )
    assert rows(tmp_path)[0]["meta"]["fallback_served"] is True


@pytest.mark.parametrize("steps", [[step("Uydurma", [("K1", "kaynakta olmayan cümle")])]])
def test_all_steps_dropped_scores_no_roadmap(tmp_path: Path, steps) -> None:
    llm = RoutingFake()
    llm.roadmap = roadmap_json(steps)
    make_runner(tmp_path, llm, RoutingFake(), ["miras_arac_01"]).run(progress=lambda _: None)
    [row] = rows(tmp_path)
    assert row["grade"]["yol_haritasi"] == 0.0
    assert row["grade"]["uydurmasiz"] is None  # yargıçlanacak yol haritası yok
