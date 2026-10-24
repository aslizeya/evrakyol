import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { Disclaimer } from "@/components/Disclaimer";
import { LogoMark } from "@/components/icons";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "latin-ext"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: {
    default: "Evrakyol",
    template: "%s | Evrakyol",
  },
  description:
    "Resmi işlemler için resmi kaynaklara dayanan, adım adım kişiselleştirilmiş yol haritası.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="tr" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#icerik"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:rounded focus:bg-foreground focus:px-3 focus:py-2 focus:text-background"
        >
          İçeriğe geç
        </a>
        <header className="no-print sticky top-0 z-10 border-b border-border/70 bg-background/85 backdrop-blur">
          <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between gap-4 px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 rounded-lg text-lg font-semibold">
              <LogoMark className="size-8" />
              Evrakyol
            </Link>
            <nav aria-label="Sayfa içi" className="hidden sm:block">
              <ul className="flex items-center gap-1 text-sm">
                <li>
                  <a
                    href="#nasil-calisir"
                    className="rounded-lg px-3 py-2 text-muted hover:text-foreground"
                  >
                    Nasıl çalışır
                  </a>
                </li>
                <li>
                  <a
                    href="#islemler"
                    className="rounded-lg px-3 py-2 text-muted hover:text-foreground"
                  >
                    İşlemler
                  </a>
                </li>
                <li>
                  <a
                    href="#ilkeler"
                    className="rounded-lg px-3 py-2 text-muted hover:text-foreground"
                  >
                    Güven
                  </a>
                </li>
              </ul>
            </nav>
          </div>
        </header>
        <main id="icerik" className="flex flex-1 flex-col">
          {children}
        </main>
        <footer className="border-t border-border px-4 py-8 sm:px-6">
          <div className="mx-auto flex max-w-5xl flex-col gap-4">
            <div className="no-print flex items-center gap-2 font-semibold">
              <LogoMark className="size-6" />
              Evrakyol
            </div>
            <Disclaimer />
          </div>
        </footer>
      </body>
    </html>
  );
}
