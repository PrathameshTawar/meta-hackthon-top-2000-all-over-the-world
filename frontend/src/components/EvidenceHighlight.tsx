"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { Languages, RotateCcw, FileSearch } from "lucide-react";

interface EvidenceHighlightProps {
  quote: string;
  fieldName: string;
}

export function EvidenceHighlight({ quote, fieldName }: EvidenceHighlightProps) {
  const { t, translateQuote } = useI18n();
  const [isTranslated, setIsTranslated] = useState(false);

  const displayedQuote = isTranslated ? translateQuote(quote) : quote;

  return (
    <div className="rounded-xl border border-ochre-300/80 bg-ochre-50/40 p-3.5 shadow-2xs">
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-xs font-semibold text-ochre-900 flex items-center gap-1.5">
          <FileSearch size={13} className="text-brand-600" />
          <span>{t("source_quote", { field: t(`field_${fieldName}`) || fieldName })}</span>
        </p>
        <button
          onClick={() => setIsTranslated(!isTranslated)}
          className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-khata-ink bg-white border border-khata-subtle hover:bg-khata-raised rounded-md px-2.5 py-1 transition-all cursor-pointer shadow-2xs"
          title="Toggle English translation for judges and non-Marathi speakers"
        >
          {isTranslated ? (
            <>
              <RotateCcw size={11} className="text-brand-600" />
              {t("show_original")}
            </>
          ) : (
            <>
              <Languages size={11} className="text-brand-600" />
              {t("translate_quote")}
            </>
          )}
        </button>
      </div>

      <blockquote className="verbatim-box text-xs text-khata-ink font-mono leading-relaxed border-l-2 border-brand-500 pl-3 bg-white/90 rounded-r-lg py-2 px-2.5 shadow-2xs">
        &ldquo;{displayedQuote}&rdquo;
      </blockquote>
      {isTranslated && (
        <p className="text-[10px] text-khata-muted mt-1.5 font-medium italic">
          Translated from Marathi/Hindi source evidence
        </p>
      )}
    </div>
  );
}
