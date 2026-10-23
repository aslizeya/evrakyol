import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Disclaimer } from "./Disclaimer";

describe("Disclaimer", () => {
  it("zorunlu uyarı metnini gösterir", () => {
    render(<Disclaimer />);
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent("Bilgiler resmi kaynaklardan derlenmiştir");
    expect(note).toHaveTextContent("ilgili kurumdan teyit ediniz");
    expect(note).toHaveTextContent("Hukuki tavsiye değildir.");
  });
});
