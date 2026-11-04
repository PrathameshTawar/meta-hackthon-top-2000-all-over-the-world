"use client";

import Link from "next/link";
import { Board } from "@/components/Board";
import { useI18n } from "@/lib/i18n";
import { Globe, ShieldCheck } from "lucide-react";

// Default to household 1 for the demo.
const HOUSEHOLD_ID = 1;

export default function HomePage() {
  const { lang, setLang, t } = useI18n();

  return (
    <main className="min-h-screen bg-khata-canvas text-khata-ink flex flex-col">
      {/* Top Ledger Navigation */}
      <header className="bg-white/95 backdrop-blur-sm border-b border-khata-subtle px-6 py-3 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-20">
        <div className="flex items-center gap-3.5">
          {/* Authentic Terracotta Seal Mark */}
          <div className="w-8 h-8 rounded-lg bg-brand-500 border border-brand-600 flex items-center justify-center text-white font-bold text-sm shadow-xs">
            <span className="font-devanagari select-none text-base">स</span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold tracking-tight text-khata-ink flex items-center gap-1.5">
                Saath
                <span className="text-xs font-normal text-khata-muted font-devanagari px-1.5 py-0.5 rounded bg-khata-raised border border-khata-subtle">
                  साथ
                </span>
              </span>
              <span className="hidden md:inline-flex items-center gap-1 text-[11px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200/80 rounded px-1.5 py-0.2">
                <ShieldCheck size={11} />
                Verbatim Grounded
              </span>
            </div>
            <p className="text-[11px] text-khata-muted font-medium mt-0.5">
              {t("tagline")}
            </p>
          </div>
        </div>

        {/* Global Language Switcher for foreign judges & family members */}
        <div className="flex items-center gap-3">
          <nav className="flex items-center gap-3 text-[11px] text-khata-muted">
            <Link href="/privacy" className="hover:text-khata-ink">Privacy</Link>
            <Link href="/terms" className="hover:text-khata-ink">Terms</Link>
          </nav>
          <div className="flex items-center bg-khata-raised rounded-lg p-0.5 border border-khata-subtle">
            <button
              onClick={() => setLang("en")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                lang === "en"
                  ? "bg-white text-brand-600 shadow-xs border border-khata-subtle/80"
                  : "text-khata-muted hover:text-khata-ink"
              }`}
            >
              English
            </button>
            <button
              onClick={() => setLang("mr")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                lang === "mr"
                  ? "bg-white text-brand-600 shadow-xs border border-khata-subtle/80"
                  : "text-khata-muted hover:text-khata-ink"
              }`}
            >
              मराठी
            </button>
            <button
              onClick={() => setLang("hi")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                lang === "hi"
                  ? "bg-white text-brand-600 shadow-xs border border-khata-subtle/80"
                  : "text-khata-muted hover:text-khata-ink"
              }`}
            >
              हिंदी
            </button>
          </div>
        </div>
      </header>

      <Board householdId={HOUSEHOLD_ID} />
    </main>
  );
}
