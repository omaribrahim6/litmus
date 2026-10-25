import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Suspense } from "react";
import { AskProvider } from "@/components/ask/AskProvider";
import { AskPanel } from "@/components/ask/AskPanel";
import { EvidenceProvider } from "@/components/evidence/EvidenceProvider";
import { Sidebar } from "@/components/shell/Sidebar";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-mono-face", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Litmus", template: "%s · Litmus" },
  description: "Git for research, except you never have to commit. Every run recorded, every claim traceable.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#171717" },
  ],
};

// Follows the system theme unless the viewer picked one.
const themeScript = `try{var t=localStorage.getItem("litmus-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

function SidebarShell() {
  return <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 border-r border-rule bg-side md:block" />;
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full">
        <EvidenceProvider>
          <AskProvider>
            <div className="flex min-h-screen max-md:flex-col">
              <Suspense fallback={<SidebarShell />}>
                <Sidebar />
              </Suspense>
              <main className="min-w-0 flex-1">{children}</main>
              <Suspense>
                <AskPanel />
              </Suspense>
            </div>
          </AskProvider>
        </EvidenceProvider>
      </body>
    </html>
  );
}
