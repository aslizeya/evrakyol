"""Proje sahibinin onayı için vaka setinin okunabilir dökümü (eval/VAKALAR.md)."""

from collections import Counter

from app.evaluation.cases import CaseSet


def _fence(text: str) -> str:
    longest = max((len(run) for run in text.split("`") if not run), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def render_review(case_set: CaseSet, process_names: dict[str, str]) -> str:
    counts = Counter(c.group for c in case_set.vakalar)
    unverified = sum(not c.dogrulandi for c in case_set.vakalar)
    lines = [
        "# Değerlendirme vakaları (onay için)",
        "",
        "Bu dosya `eval/cases.yaml`'dan otomatik üretilir; düzenlemeleri o dosyada yapın, sonra "
        "`python -m app.evaluation review` çalıştırın.",
        "",
        f"Toplam **{len(case_set.vakalar)}** vaka · doğrulanmamış (taslak): **{unverified}**",
        "",
        "| Grup | Vaka |",
        "|---|---|",
        *[f"| {process_names.get(g, g)} | {n} |" for g, n in sorted(counts.items())],
        "",
        "## Nasıl doğrulanır?",
        "",
        "1. Aşağıdaki **beklenen unsurlar** tablosunda her satırın kaynak alıntısını resmi sayfada "
        "kontrol edin. Unsur doğru değilse `cases.yaml`'da düzeltin veya silin.",
        "2. Her yol haritası vakasında beklenen unsurların **o kullanıcının durumunda** gerçekten "
        "gerekli olup olmadığına bakın; eksik/fazla olanları düzeltin.",
        "3. Sınıflandırma vakalarında beklenen işlemin doğru olduğunu kontrol edin.",
        "4. Onayladığınız vakada `dogrulandi: true` yapın.",
        "",
        "## Beklenen unsurlar",
        "",
        "| Kimlik | Unsur | Tür | Aranan ifadeler | Kaynak |",
        "|---|---|---|---|---|",
    ]
    for ref, el in case_set.unsurlar.items():
        terms = " / ".join(e if isinstance(e, str) else " + ".join(e) for e in el.esdeger)
        lines.append(f"| `{ref}` | {el.ad} | {el.tur} | {terms} | {el.kaynak} |")
    lines.append("")

    current_group = None
    for case in case_set.vakalar:
        if case.group != current_group:
            current_group = case.group
            lines += [f"## {process_names.get(current_group, current_group)}", ""]
        status = "✅ doğrulandı" if case.dogrulandi else "⬜ taslak"
        tags = ", ".join(case.etiketler[1:])
        lines.append(f"### `{case.id}` — {status}{' · ' + tags if tags else ''}")
        lines.append("")
        lines.append(_fence(case.metin))
        lines.append("")
        lines.append(
            f"- Beklenen işlem: **{process_names.get(case.beklenen_islem, case.beklenen_islem)}**"
        )
        if case.beklenen_cevaplar:
            pairs = ", ".join(f"{k} = {v}" for k, v in case.beklenen_cevaplar.items())
            lines.append(f"- Metinden çıkarılması beklenen cevaplar: {pairs}")
        if case.cevaplar:
            pairs = ", ".join(f"{k} = {v}" for k, v in case.cevaplar.items())
            lines.append(f"- Netleştirme cevapları (simülasyon): {pairs}")
        if case.beklenen_unsurlar:
            names = ", ".join(case_set.unsurlar[r].ad for r in case.beklenen_unsurlar)
            lines.append(f"- Yol haritasında beklenen: {names}")
        if case.kisisel_veriler:
            lines.append(
                f"- LLM'e maskelenmeden gitmemesi gerekenler: {', '.join(case.kisisel_veriler)}"
            )
        lines.append("")
    return "\n".join(lines)
