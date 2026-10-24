import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantFlow } from "./AssistantFlow";
import { fakeFetch, ROADMAP } from "./test-fixtures";

const QUESTION = "Babamdan kalan arabayı üzerime almak istiyorum.";

const NEEDS_CLARIFICATION = {
  status: "needs_clarification",
  masked_text: QUESTION,
  process_code: "miras_arac_devri",
  process_name: "Miras yoluyla araç devri",
  answers: { mirasci_sayisi: "Tek mirasçı" },
  questions: [
    {
      key: "mirascilik_belgesi",
      question: "Mirasçılık belgesi (veraset ilamı) alındı mı?",
      options: ["Evet", "Hayır", "Bilmiyorum"],
    },
  ],
};

const ROADMAP_OK = { status: "ok", masked_text: QUESTION, roadmap: ROADMAP };

function setup(routes: Parameters<typeof fakeFetch>[0]) {
  const fake = fakeFetch(routes);
  vi.stubGlobal("fetch", fake.fn);
  const user = userEvent.setup();
  render(<AssistantFlow />);
  return { user, calls: fake.calls };
}

async function ask(user: ReturnType<typeof userEvent.setup>, text = QUESTION) {
  await user.type(screen.getByLabelText("Hangi resmi işlemi yapmak istiyorsunuz?"), text);
  await user.click(screen.getByRole("button", { name: "Yol haritamı çıkar" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("AssistantFlow", () => {
  it("netleştirici soruyu sorar, cevaplarla yol haritasını gösterir", async () => {
    const { user, calls } = setup({
      "/api/understand": [{ body: NEEDS_CLARIFICATION }],
      "/api/roadmap": [{ body: ROADMAP_OK }],
    });
    await ask(user);

    const heading = await screen.findByRole("heading", { name: "Birkaç kısa soru" });
    expect(heading).toHaveFocus();
    await user.click(screen.getByRole("radio", { name: "Hayır" }));
    await user.click(screen.getByRole("button", { name: "Devam et" }));

    expect(await screen.findByRole("heading", { name: "Yol haritanız" })).toBeInTheDocument();
    expect(calls[1]).toEqual({
      url: "/api/roadmap",
      body: {
        text: QUESTION,
        process_code: "miras_arac_devri",
        // Metinden çıkarılan cevap korunur, kullanıcının seçtiği eklenir
        answers: { mirasci_sayisi: "Tek mirasçı", mirascilik_belgesi: "Hayır" },
      },
    });
    const steps = screen.getAllByRole("listitem").filter((li) => li.hasAttribute("data-step"));
    expect(steps).toHaveLength(2);
    expect(within(steps[0]).getByRole("heading", { level: 3 })).toHaveTextContent(
      "1.Noterden mirasçılık belgesi alın",
    );
  });

  it("işaretlenen adımlar ilerleme çubuğuna yansır", async () => {
    const { user } = setup({
      "/api/understand": [{ body: { ...NEEDS_CLARIFICATION, status: "ready", questions: [] } }],
      "/api/roadmap": [{ body: ROADMAP_OK }],
    });
    await ask(user);
    await screen.findByRole("heading", { name: "Yol haritanız" });

    const progress = screen.getByLabelText("0 / 2 adım tamamlandı");
    const [first] = screen.getAllByRole("checkbox", { name: "Bu adımı tamamladım" });
    await user.click(first);
    expect(progress).toHaveAttribute("value", "1");
    expect(screen.getByText("1 / 2 adım tamamlandı")).toBeInTheDocument();
  });

  it("cevaplanmamış soruda devam etmez ve uyarı gösterir", async () => {
    const { user, calls } = setup({ "/api/understand": [{ body: NEEDS_CLARIFICATION }] });
    await ask(user);
    await screen.findByRole("heading", { name: "Birkaç kısa soru" });
    await user.click(screen.getByRole("button", { name: "Devam et" }));
    expect(screen.getByText("Lütfen bir seçenek belirleyin.")).toBeInTheDocument();
    expect(calls).toHaveLength(1);
  });

  it("kapsam dışı işlemde açıklama gösterir", async () => {
    const { user } = setup({
      "/api/understand": [
        {
          body: {
            status: "out_of_scope",
            masked_text: "Tapu devri",
            message: "Bu işlem şu an desteklenen işlemler arasında değil.",
          },
        },
      ],
    });
    await ask(user, "Tapu devri nasıl yapılır?");
    expect(
      await screen.findByRole("heading", { name: "Bu işlem henüz desteklenmiyor" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/desteklenen işlemler arasında değil/)).toBeInTheDocument();
  });

  it("kaynak bulunamazsa uydurmak yerine kuruma yönlendirir", async () => {
    const { user } = setup({
      "/api/understand": [{ body: { ...NEEDS_CLARIFICATION, status: "ready", questions: [] } }],
      "/api/roadmap": [
        {
          body: {
            status: "no_sources",
            masked_text: QUESTION,
            roadmap: null,
            message: "Lütfen Noterlik ile iletişime geçin.",
          },
        },
      ],
    });
    await ask(user);
    expect(
      await screen.findByRole("heading", { name: "Resmi kaynaklarda yeterli bilgi bulunamadı" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Lütfen Noterlik ile iletişime geçin.")).toBeInTheDocument();
  });

  it("hata durumunda mesaj gösterir ve tekrar dener", async () => {
    const { user, calls } = setup({
      "/api/understand": [{ body: { ...NEEDS_CLARIFICATION, status: "ready", questions: [] } }],
      "/api/roadmap": [
        { status: 502, body: { detail: "Yanıt doğrulanamadı." } },
        { body: ROADMAP_OK },
      ],
    });
    await ask(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("Yanıt doğrulanamadı.");
    await user.click(screen.getByRole("button", { name: "Tekrar dene" }));
    expect(await screen.findByRole("heading", { name: "Yol haritanız" })).toBeInTheDocument();
    expect(calls.filter((c) => c.url === "/api/roadmap")).toHaveLength(2);
  });

  it("anlama isteği başarısız olursa soru formuna hata ile döner", async () => {
    const { user } = setup({ "/api/understand": [] }); // ağ hatası
    await ask(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("Bağlantı kurulamadı");
    expect(screen.getByLabelText("Hangi resmi işlemi yapmak istiyorsunuz?")).toHaveValue(QUESTION);
  });

  it("kişisel bilgiler gizlendiyse kullanıcıyı bilgilendirir", async () => {
    const text = "TC 12345678901, babamın arabasını almak istiyorum";
    const { user } = setup({
      "/api/understand": [
        {
          body: {
            ...NEEDS_CLARIFICATION,
            masked_text: "TC [TC_KIMLIK], babamın arabasını almak istiyorum",
          },
        },
      ],
    });
    await ask(user, text);
    expect(await screen.findByText(/kişisel bilgiler .* gizlendi/)).toBeInTheDocument();
  });

  it("örnek soru metin alanını doldurur; kısa metinle gönderim kapalıdır", async () => {
    const { user } = setup({});
    const submit = screen.getByRole("button", { name: "Yol haritamı çıkar" });
    expect(submit).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Veraset ilamını nereden ve nasıl alabilirim?" }),
    );
    expect(screen.getByLabelText("Hangi resmi işlemi yapmak istiyorsunuz?")).toHaveValue(
      "Veraset ilamını nereden ve nasıl alabilirim?",
    );
    expect(submit).toBeEnabled();
  });
});
