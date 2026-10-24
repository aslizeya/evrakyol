import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { formatDate } from "./format";
import { RoadmapView } from "./RoadmapView";
import { ROADMAP } from "./test-fixtures";

describe("RoadmapView", () => {
  it("adım ayrıntılarını, kaynakları ve uyarıları gösterir", () => {
    render(
      <RoadmapView roadmap={ROADMAP} processName="Miras yoluyla araç devri" onRestart={() => {}} />,
    );

    expect(screen.getByText("Zorunlu mali sorumluluk sigorta poliçesi")).toBeInTheDocument();
    expect(screen.getByText("1.250,50 TL")).toBeInTheDocument();
    expect(
      screen.getByText("Kaynakta belirtilmemiş; ilgili kurumdan öğreniniz."),
    ).toBeInTheDocument();
    expect(screen.getByText(/90 gün içinde/)).toBeInTheDocument();
    expect(screen.getByText(/Yüksek güven/)).toBeInTheDocument();

    const link = screen.getByRole("link", { name: /Mirasçılık Belgesi/ });
    expect(link).toHaveAttribute("href", "https://portal.tnb.org.tr/Sayfalar/MirascilikHiz.aspx");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAccessibleName(/yeni sekmede açılır/);
    expect(screen.getByText(/son kontrol 24 Ekim 2026/)).toBeInTheDocument();
  });

  it("tarihi Türkçe biçimler", () => {
    expect(formatDate("2026-02-27")).toBe("27 Şubat 2026");
    expect(formatDate("geçersiz")).toBe("geçersiz");
  });
});
