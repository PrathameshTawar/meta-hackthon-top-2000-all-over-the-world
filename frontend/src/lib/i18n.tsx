"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

import { translate, translateText, type Language } from "./translations";

export { TRANSLATIONS, translate, translateText, type Language } from "./translations";

export interface I18nContextType {
  lang: Language;
  setLang: (lang: Language) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  translateQuote: (text: string) => string;
}

export const I18nContext = createContext<I18nContextType>({
  lang: "en",
  setLang: () => {},
  t: (k) => k,
  translateQuote: (q) => q,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>("en");

  useEffect(() => {
    const saved = localStorage.getItem("saath_lang") as Language | null;
    if (saved && (saved === "en" || saved === "mr" || saved === "hi")) {
      setLangState(saved);
    }
  }, []);

  const setLang = (newLang: Language) => {
    setLangState(newLang);
    localStorage.setItem("saath_lang", newLang);
  };

  const t = (key: string, params?: Record<string, string | number>): string =>
    translate(lang, key, params);

  return (
    <I18nContext.Provider value={{ lang, setLang, t, translateQuote: translateText }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}

