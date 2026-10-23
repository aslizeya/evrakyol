import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Disclaimer } from "@/components/Disclaimer";
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
        <main id="icerik" className="flex flex-1 flex-col">
          {children}
        </main>
        <footer className="border-t border-border px-4 py-4 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Disclaimer />
          </div>
        </footer>
      </body>
    </html>
  );
}
