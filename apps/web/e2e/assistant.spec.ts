import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const QUESTION = "Babamdan kalan arabayı üzerime almak istiyorum.";

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

async function ask(page: Page, text: string) {
  await page.getByLabel("Hangi resmi işlemi yapmak istiyorsunuz?").fill(text);
  await page.getByRole("button", { name: "Yol haritamı çıkar" }).click();
}

test("soru -> netleştirme -> yol haritası akışı; her aşama erişilebilir", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("note")).toContainText("Hukuki tavsiye değildir.");
  await expectAccessible(page);

  await page.getByRole("button", { name: QUESTION }).click();
  await page.getByRole("button", { name: "Yol haritamı çıkar" }).click();

  await expect(page.getByRole("heading", { name: "Birkaç kısa soru" })).toBeFocused();
  await expectAccessible(page);
  await page.getByRole("radio", { name: "Hayır" }).check();
  await page.getByRole("button", { name: "Devam et" }).click();

  await expect(page.getByRole("heading", { name: "Yol haritanız" })).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 3, name: /Noterden mirasçılık belgesi alın/ }),
  ).toBeVisible();
  const source = page.getByRole("link", { name: /Trafik Tescil Hakkında/ });
  await expect(source).toHaveAttribute("href", "https://www.egm.gov.tr/trafik-tescil-hakkinda");
  await expect(page.getByText("son kontrol 24 Ekim 2026").first()).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("checkbox", { name: "Bu adımı tamamladım" }).first().check();
  await expect(page.getByText("1 / 2 adım tamamlandı")).toBeVisible();
});

test("kapsam dışı işlem dürüstçe belirtilir", async ({ page }) => {
  await page.goto("/");
  await ask(page, "Babamdan kalan evi üzerime almak istiyorum, tapu devri nasıl olur?");
  await expect(page.getByRole("heading", { name: "Bu işlem henüz desteklenmiyor" })).toBeVisible();
  await page.getByRole("button", { name: "Yeni soru sor" }).click();
  await expect(page.getByLabel("Hangi resmi işlemi yapmak istiyorsunuz?")).toBeVisible();
});

test("kaynak yoksa yol haritası uydurulmaz, kuruma yönlendirilir", async ({ page }) => {
  await page.goto("/");
  await ask(page, "Kaynaksız bir durum: babamdan kalan arabayı almak istiyorum");
  await page.getByRole("radio", { name: "Evet" }).check();
  await page.getByRole("button", { name: "Devam et" }).click();
  await expect(
    page.getByRole("heading", { name: "Resmi kaynaklarda yeterli bilgi bulunamadı" }),
  ).toBeVisible();
  await expect(page.getByText(/Noterlik ile iletişime geçin/)).toBeVisible();
  await expect(page.locator("li[data-step]")).toHaveCount(0);
});

test("kişisel bilgi gizlendiğinde kullanıcı bilgilendirilir", async ({ page }) => {
  await page.goto("/");
  await ask(page, "TC kimlik numaram 12345678901, babamdan kalan arabayı almak istiyorum");
  await expect(page.getByText(/kişisel bilgiler .* gizlendi/)).toBeVisible();
});

test("yol haritası yatay kaydırma olmadan sığar ve yazdırmada düğmeler gizlenir", async ({
  page,
}) => {
  await page.goto("/");
  await ask(page, QUESTION);
  await page.getByRole("radio", { name: "Hayır" }).check();
  await page.getByRole("button", { name: "Devam et" }).click();
  await expect(page.getByRole("heading", { name: "Yol haritanız" })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: "Yazdır / PDF olarak kaydet" })).toBeHidden();
  await expect(page.getByRole("heading", { level: 3 }).first()).toBeVisible();
});
