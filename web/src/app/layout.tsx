import type { Metadata, Viewport } from "next";
import { Archivo, Martian_Mono } from "next/font/google";
import { Suspense } from "react";
import { AskProvider } from "@/components/ask/AskProvider";
import { AskPanel } from "@/components/ask/AskPanel";
import { EvidenceProvider } from "@/components/evidence/EvidenceProvider";
import { TopBar } from "@/components/shell/TopBar";
import { Wordmark } from "@/components/ui";
import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  axes: ["wdth"],
});

const martian = Martian_Mono({
  variable: "--font-martian",
  subsets: ["latin"],
  axes: ["wdth"],
});

export const metadata: Metadata = {
  title: { default: "Litmus", template: "%s · Litmus" },
  description: "Git for research, except you never have to commit. Every run recorded, every claim traceable.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f6f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0e151b" },
  ],
};

const themeScript = `try{var t=localStorage.getItem("litmus-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

function TopBarShell() {
  return (
    <header className="sticky top-0 z-40 flex h-[57px] items-center border-b border-rule bg-paper/90 px-5">
      <Wordmark />
    </header>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${archivo.variable} ${martian.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full">
        <EvidenceProvider>
          <AskProvider>
            <div className="flex min-h-screen flex-col">
              <Suspense fallback={<TopBarShell />}>
                <TopBar />
              </Suspense>
              <div className="flex flex-1">
                <main className="min-w-0 flex-1">{children}</main>
                <Suspense>
                  <AskPanel />
                </Suspense>
              </div>
            </div>
          </AskProvider>
        </EvidenceProvider>
      </body>
    </html>
  );
}
