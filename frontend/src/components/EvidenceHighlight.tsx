"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { Languages, RotateCcw } from "lucide-react";

interface EvidenceHighlightProps {
  quote: string;
  fieldName: string;
}

export function EvidenceHighlight({ quote, fieldName }: EvidenceHighlightProps) {
  const { t, translateQuote } = useI18n();
  const [isTranslated, setIsTranslated] = useState(false);

  const displayedQuote = isTranslated ? translateQuote(quote) : quote;

  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-xs font-semibold text-brand-600">
          📎 {t("source_quote", { field: t(`field_${fieldName}`) || fieldName })}
        </p>
        <button
          onClick={() => setIsTranslated(!isTranslated)}
          className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 bg-white border border-brand-300 hover:bg-brand-100 rounded-md px-2 py-0.5 transition-colors cursor-pointer shadow-2xs"
          title="Toggle English translation for judges and non-Marathi speakers"
        >
          {isTranslated ? (
            <>
              <RotateCcw size={11} />
              {t("show_original")}
            </>
          ) : (
            <>
              <Languages size={11} />
              {t("translate_quote")}
            </>
          )}
        </button>
      </div>

      <blockquote className="text-sm text-gray-800 font-mono leading-relaxed border-l-2 border-brand-400 pl-3 bg-white/70 rounded-r-md py-1.5 px-2">
        "{displayedQuote}"
      </blockquote>
      {isTranslated && (
        <p className="text-[10px] text-gray-400 mt-1.5 italic">
          Translated from Marathi/Hindi source evidence
        </p>
      )}
    </div>
  );
}
