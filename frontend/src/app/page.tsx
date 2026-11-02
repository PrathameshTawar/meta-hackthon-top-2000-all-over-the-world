"use client";

import { Board } from "@/components/Board";
import { useI18n } from "@/lib/i18n";
import { Globe } from "lucide-react";

// Default to household 1 for the demo.
const HOUSEHOLD_ID = 1;

export default function HomePage() {
  const { lang, setLang, t } = useI18n();

  return (
    <main className="min-h-screen">
      <header className="bg-white border-b border-gray-200 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 shadow-2xs">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white font-bold text-sm shadow-xs">
            स
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-tight text-gray-900">
                Saath <span className="text-gray-400 font-normal text-sm">/ साथ</span>
              </span>
            </div>
            <p className="text-xs text-gray-500 font-medium">
              {t("tagline")}
            </p>
          </div>
        </div>

        {/* Global Language Switcher for foreign judges & family members */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium mr-1">
            <Globe size={14} className="text-brand-600" />
            <span>{t("language")}:</span>
          </div>
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5 border border-gray-200 shadow-2xs">
            <button
              onClick={() => setLang("en")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                lang === "en" ? "bg-white text-brand-700 shadow-xs" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              English
            </button>
            <button
              onClick={() => setLang("mr")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                lang === "mr" ? "bg-white text-brand-700 shadow-xs" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              मराठी
            </button>
            <button
              onClick={() => setLang("hi")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                lang === "hi" ? "bg-white text-brand-700 shadow-xs" : "text-gray-600 hover:text-gray-900"
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
