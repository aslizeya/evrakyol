"""Çalıştırma sonuçlarından tarihli Markdown rapor ve README için özet (son.json) üretir."""

import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.config import REPO_ROOT
from app.rag.schema import OUT_OF_SCOPE

REPORTS_DIR = REPO_ROOT / "eval" / "raporlar"

# (kimlik, etiket, ikili mi, yüksek değer iyi mi). İlk satır başlık metriğidir.
METRICS: list[tuple[str, str, bool, bool]] = [
    ("islem_dogru", "Doğru işlem sınıflandırma", True, True),
    ("unsur_kapsama", "Beklenen unsurların kapsanması", False, True),
    ("evrak_kapsama", "Beklenen evrakların kapsanması", False, True),
    ("uydurmasiz", "Uydurma içermeyen yol haritası", True, True),
    ("desteklenmeyen", "Desteklenmeyen iddia oranı", False, False),
    ("kaynak_gosterme", "Kaynak gösterilen adım oranı", False, True),
    ("dogrulanan_adim", "Kaynağa karşı doğrulanan adım oranı", False, True),
    ("cevap_cikarma", "Netleştirme cevabı çıkarma", False, True),
    ("soru_siniri", "En fazla 3 netleştirici soru", True, True),
    ("yol_haritasi", "Yol haritası üretilebilen vaka", True, True),
    ("pii_sizinti", "Kişisel veri sızıntısı (LLM isteğinde)", True, False),
]

# Birinci taraf API fiyatları, $/milyon token (girdi, çıktı); önbellekten okuma girdinin 0,1 katı.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def interval(values: list[float], binary: bool) -> tuple[float, float, float]:
    """Ortalama ve %95 güven aralığı (ikili metrikte Wilson, diğerlerinde normal yaklaşım)."""
    n = len(values)
    mean = sum(values) / n
    z = 1.96
    if binary:
        denom = 1 + z * z / n
        centre = (mean + z * z / (2 * n)) / denom
        half = z * math.sqrt(mean * (1 - mean) / n + z * z / (4 * n * n)) / denom
        return mean, max(0.0, centre - half), min(1.0, centre + half)
    if n < 2:
        return mean, mean, mean
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    half = z * sd / math.sqrt(n)
    return mean, max(0.0, mean - half), min(1.0, mean + half)


def _cost(model: str | None, usage: dict | None) -> float | None:
    if not usage or not isinstance(model, str) or model not in PRICES:
        return None
    price_in, price_out = PRICES[model]
    return (
        usage.get("input_tokens", 0) * price_in
        + usage.get("cache_read_input_tokens", 0) * price_in * 0.1
        + usage.get("output_tokens", 0) * price_out
    ) / 1_000_000


def summarize(run_dir: Path) -> dict:
    rows = read_jsonl(run_dir / "results.jsonl")
    errors = read_jsonl(run_dir / "errors.jsonl")
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    succeeded = {(r["prompt_id"], r["rep"]) for r in rows}
    open_errors = [e for e in errors if (e["prompt_id"], e["rep"]) not in succeeded]

    metrics = {}
    for metric_id, label, binary, higher_better in METRICS:
        values = [
            r["grade"][metric_id]
            for r in rows
            if r["status"] == "ok" and r["grade"].get(metric_id) is not None
        ]
        if values:
            mean, low, high = interval(values, binary)
            metrics[metric_id] = {
                "label": label,
                "n": len(values),
                "mean": round(mean, 4),
                "ci95": [round(low, 4), round(high, 4)],
                "higher_is_better": higher_better,
            }

    # Kapsam dışı tespiti: kesinlik ve duyarlılık
    scored = [r for r in rows if "predicted" in r["meta"]]
    expected_out = [r for r in scored if r["tags"][0] == OUT_OF_SCOPE]
    predicted_out = [r for r in scored if r["meta"]["predicted"] == OUT_OF_SCOPE]
    true_out = [r for r in expected_out if r["meta"]["predicted"] == OUT_OF_SCOPE]
    scope = {
        "kapsam_disi_duyarlilik": len(true_out) / len(expected_out) if expected_out else None,
        "kapsam_disi_kesinlik": len(true_out) / len(predicted_out) if predicted_out else None,
    }

    costs = [
        c
        for r in rows
        for c in (
            _cost(r.get("model"), r.get("usage")),
            _cost(r.get("judge_model"), r.get("judge_usage")),
        )
        if c is not None
    ]
    return {
        "run": meta,
        "generated_at": datetime.now(UTC).isoformat(),
        "attempts": len(rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "open_errors": len(open_errors),
        "error_classes": dict(Counter(e["failure_class"] for e in open_errors)),
        "fallback_served": sum(bool(r["meta"].get("fallback_served")) for r in rows),
        "judge_errors": sum("judge_error" in r["meta"] for r in rows),
        "metrics": metrics,
        "scope": scope,
        "cost_usd": round(sum(costs), 4) if costs else None,
    }


def _usd(value: float | None) -> str:
    return "–" if value is None else f"${value:.4f}"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"%{value * 100:.1f}"


def render_markdown(summary: dict, rows: list[dict]) -> str:
    run = summary["run"]
    out: list[str] = [
        f"# Değerlendirme raporu — {run['label']}",
        "",
        f"- Tarih: {summary['generated_at'][:10]}",
        f"- Model: `{run['model']}` · Yargıç: `{run['judge_model'] or 'yok'}`"
        f" · Arama: `{run['retriever']}` · Tekrar: {run['reps']}",
        f"- Kod sürümü: `{run['git'] or 'bilinmiyor'}` · Vaka dosyası özeti: "
        f"`{run['cases_sha256'][:12]}` ({run['case_count']} vaka)",
        f"- Deneme: {summary['attempts']} · Durumlar: {summary['status_counts']}"
        f" · Açık altyapı hatası: {summary['open_errors']} {summary['error_classes'] or ''}",
        f"- Yedek modelin yanıtladığı deneme: {summary['fallback_served']}"
        f" · Yargıç hatası: {summary['judge_errors']}"
        f" · Ölçülen maliyet: {_usd(summary['cost_usd'])}",
        "",
    ]
    if run["unverified_cases"]:
        out += [
            f"> **Uyarı:** {run['unverified_cases']} vakanın beklenen cevapları henüz proje sahibi "
            "tarafından doğrulanmadı (taslak). Bu sonuçlar yayın metriği olarak kullanılmamalıdır.",
            "",
        ]
    if run["retriever"] != "db":
        out += [
            "> **Not:** Bu çalıştırmada yayındaki hibrit arama yerine bellek içi basit arama "
            "kullanıldı; arama kalitesi yayındakinden düşüktür.",
            "",
        ]
    out += ["## Metrikler", "", "| Metrik | Değer | %95 aralık | n |", "|---|---|---|---|"]
    for m in summary["metrics"].values():
        arrow = "↑" if m["higher_is_better"] else "↓"
        low, high = m["ci95"]
        out.append(
            f"| {m['label']} {arrow} | {_pct(m['mean'])} | {_pct(low)}–{_pct(high)} | {m['n']} |"
        )
    scope = summary["scope"]
    out += [
        f"| Kapsam dışı tespiti — duyarlılık ↑ | {_pct(scope['kapsam_disi_duyarlilik'])} | | |",
        f"| Kapsam dışı tespiti — kesinlik ↑ | {_pct(scope['kapsam_disi_kesinlik'])} | | |",
        "",
    ]

    # Sınıflandırma hataları
    wrong = [r for r in rows if r["grade"].get("islem_dogru") == 0.0]
    out += ["## Yanlış sınıflandırılan vakalar", ""]
    if not wrong:
        out.append("Yok.")
    for r in wrong:
        out.append(
            f"- `{r['prompt_id']}`: beklenen `{r['tags'][0]}`, "
            f"tahmin `{r['meta'].get('predicted')}` — {r['prompt']}"
        )
    out.append("")

    # Grup bazında
    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_group[r["tags"][0]].append(r)
    out += [
        "## Grup bazında",
        "",
        "| Grup | Deneme | Sınıflandırma | Unsur kapsama | Uydurmasız |",
        "|---|---|---|---|---|",
    ]
    for group, items in sorted(by_group.items()):

        def avg(metric: str, items=items) -> str:
            vals = [i["grade"].get(metric) for i in items if i["grade"].get(metric) is not None]
            return _pct(sum(vals) / len(vals)) if vals else "–"

        out.append(
            f"| {group} | {len(items)} | {avg('islem_dogru')} | "
            f"{avg('unsur_kapsama')} | {avg('uydurmasiz')} |"
        )
    out.append("")

    # Yol haritası ayrıntıları
    roadmap_rows = [r for r in rows if "roadmap_status" in r["meta"]]
    if roadmap_rows:
        out += ["## Yol haritası vakaları", ""]
        for r in sorted(roadmap_rows, key=lambda x: (x["prompt_id"], x["rep"])):
            g, m = r["grade"], r["meta"]
            out.append(
                f"### `{r['prompt_id']}` #{r['rep']} — kapsama {_pct(g.get('unsur_kapsama'))}, "
                f"uydurmasız {_pct(g.get('uydurmasiz'))}"
            )
            out.append(f"- Metin: {r['prompt']}")
            if m.get("karsilanmayan"):
                out.append(f"- Karşılanmayan unsurlar: {', '.join(m['karsilanmayan'])}")
            for claim in m.get("desteklenmeyen_iddialar", []):
                out.append(
                    f"- Desteklenmeyen iddia ({claim['konum']}): {claim['iddia']} "
                    f"— {claim['gerekce']}"
                )
            if m.get("dropped_steps"):
                out.append(f"- Doğrulanamadığı için çıkarılan adım: {m['dropped_steps']}")
            out.append(f"- Ayrıntı: `traces/{r['prompt_id']}_rep{r['rep']}.json`")
            out.append("")
    return "\n".join(out) + "\n"


def write_report(run_dir: Path) -> Path:
    summary = summarize(run_dir)
    rows = read_jsonl(run_dir / "results.jsonl")
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), "utf-8"
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{summary['generated_at'][:10]}_{summary['run']['label']}.md"
    path.write_text(render_markdown(summary, rows), "utf-8")
    # README'deki metrikler bu dosyadan alınır (yalnızca tam ve doğrulanmış çalıştırmalar için).
    if summary["run"]["unverified_cases"] == 0 and summary["run"]["retriever"] == "db":
        (REPORTS_DIR / "son.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), "utf-8"
        )
    return path
