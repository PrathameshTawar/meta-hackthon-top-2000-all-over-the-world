"use client";

/**
 * Shows the quoted span that supports a field value.
 * This is the key UI element that proves the agent cited its source —
 * highlighted in the transcript / OCR output.
 */

const FIELD_LABELS: Record<string, string> = {
  amount:   "Amount",
  due_date: "Due date",
  payee:    "Payee",
  title:    "Title",
};

interface EvidenceHighlightProps {
  quote: string;
  fieldName: string;
}

export function EvidenceHighlight({ quote, fieldName }: EvidenceHighlightProps) {
  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
      <p className="text-xs font-semibold text-brand-600 mb-2">
        📎 Source quote for {FIELD_LABELS[fieldName] ?? fieldName}
      </p>
      <blockquote className="text-sm text-gray-700 font-mono leading-relaxed border-l-2 border-brand-400 pl-3">
        "{quote}"
      </blockquote>
    </div>
  );
}
