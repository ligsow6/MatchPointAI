import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { THEME_BOOTSTRAP } from "@/components/layout/ThemeToggle";
import { loadOverview } from "@/lib/data";
import { formatDate } from "@/lib/format";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import "./globals.css";
import styles from "./layout.module.css";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

export const metadata: Metadata = {
  title: { default: `${SITE_NAME} · Prédiction de matchs ATP`, template: `%s · ${SITE_NAME}` },
  description: SITE_DESCRIPTION,
  openGraph: {
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
    type: "website",
    locale: "fr_FR",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafaf8" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1012" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const overview = loadOverview();
  return (
    <html lang="fr" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        <a href="#contenu" className={styles.skipLink}>
          Aller au contenu
        </a>
        <SiteHeader />
        <main id="contenu" tabIndex={-1} className={styles.main}>
          {children}
        </main>
        <SiteFooter dataThrough={formatDate(overview.dataset.lastDate)} />
      </body>
    </html>
  );
}
