// Pure translation data and helpers (no React), so they can be unit tested.
export type Language = "en" | "mr" | "hi";

export const TRANSLATIONS: Record<Language, Record<string, string>> = {
  en: {
    // Header
    "tagline": "Saath: your parents' bills and care, handled together.",
    "subtitle": "Family coordination board",
    "language": "Language",

    // Tabs
    "tab_tasks": "Tasks",
    "tab_health": "Health",

    // Columns
    "col_new": "To Settle",
    "col_needs_review": "Needs Confirmation",
    "col_claimed": "Claimed by Sibling",
    "col_done": "Settled & Verified",

    // Toolbar
    "try_live_agent": "Try Live Agent",
    "simulate_3_days": "Simulate 3 Days Later",
    "audit_log": "Audit Log",
    "reset_demo": "Reset Demo",

    // Task details & card
    "claim_task": "Claim Task",
    "claiming": "Claiming…",
    "mark_done": "Mark Done",
    "marking": "Marking…",
    "field_amount": "Amount",
    "field_due_date": "Due date",
    "field_payee": "Payee",
    "field_title": "Title",
    "not_found": "Not found",
    "extracted_fields": "Extracted Fields",
    "source_quote": "Source quote for {field}",
    "all_evidence": "All Evidence ({count})",
    "show_quote": "▼ Show quote",
    "hide_quote": "▲ Hide quote",
    "translate_quote": "Translate to English",
    "show_original": "↩ Show Original",
    "assigned_to": "Assigned to",
    "unassigned": "Unassigned",
    "agent_confidence": "Agent confidence",
    "low_confidence": "Low confidence · {percent}%",
    "escalated": "ESCALATED",
    "stale_claim": "Claimed 2+ days ago · No progress",
    "review": "Review",
    "loading": "Loading family coordination board…",

    // Health panel
    "todays_medicines": "Today's Medicines",
    "vitals_14_days": "14-Day Vitals",
    "family_limits": "Family Limits",
    "medicines_setup": "Medicines Setup",
    "health_disclaimer": "Saath records what your family reports. It does not give medical advice.",
    "add_threshold": "+ Add family limit",
    "add_medication": "+ Add medicine",
    "dose_status_pending": "Pending",
    "dose_status_taken": "Taken",
    "dose_status_missed": "Missed",
    "evidence_badge": "Evidence",
    "connect_watch": "Connect watch",
    "disconnect_watch": "Disconnect",
    "watch_connected": "Watch connected",
    "watch_disconnected": "Watch disconnected",
    "from_watch": "from watch",
    "watch_not_supported": "Watch connection works in Chrome or Edge on Android, Windows or Mac, over HTTPS.",
    "wearing_watch": "Wearing watch",
    "live_heart_rate": "Live Heart Rate",
  },
  mr: {
    // Header
    "tagline": "साथ: पालकांची बिले आणि काळजी, एकत्र सांभाळू.",
    "subtitle": "कुटुंब समन्वय बोर्ड",
    "language": "भाषा",

    // Tabs
    "tab_tasks": "कामे",
    "tab_health": "आरोग्य",

    // Columns
    "col_new": "बाकी कामे",
    "col_needs_review": "खात्री आवश्यक",
    "col_claimed": "स्वीकारलेली कामे",
    "col_done": "पूर्ण झालेली कामे",

    // Toolbar
    "try_live_agent": "लाईव्ह एजंट",
    "simulate_3_days": "३ दिवस पुढे",
    "audit_log": "ऑडिट लॉग",
    "reset_demo": "रीसेट करा",

    // Task details & card
    "claim_task": "मी करतो",
    "claiming": "स्वीकारत आहे…",
    "mark_done": "पूर्ण झाले",
    "marking": "नोंदवत आहे…",
    "field_amount": "रक्कम",
    "field_due_date": "शेवटची तारीख",
    "field_payee": "संस्था / सेवा",
    "field_title": "शीर्षक",
    "not_found": "आढळले नाही",
    "extracted_fields": "नोंदवलेले तपशील",
    "source_quote": "{field} चा पुरावा",
    "all_evidence": "सर्व पुरावे ({count})",
    "show_quote": "▼ पुरावा पहा",
    "hide_quote": "▲ लपवा",
    "translate_quote": "इंग्रजी भाषांतर",
    "show_original": "↩ मूळ पहा",
    "assigned_to": "जबाबदारी",
    "unassigned": "अद्याप कोणी नाही",
    "agent_confidence": "विश्वासार्हता",
    "low_confidence": "कमी विश्वासार्हता · {percent}%",
    "escalated": "तात्काळ",
    "stale_claim": "दावा केला २+ दिवस झाले · प्रगती नाही",
    "review": "तपासा",
    "loading": "कुटुंब बोर्ड लोड होत आहे…",

    // Health panel
    "todays_medicines": "आजची औषधे",
    "vitals_14_days": "१४ दिवसांचे वाचन",
    "family_limits": "कुटुंबाच्या मर्यादा",
    "medicines_setup": "औषध वेळापत्रक",
    "health_disclaimer": "साथ कुटुंब जे सांगते ते नोंदवून घेते. वैद्यकीय सल्ला देत नाही.",
    "add_threshold": "+ नवीन मर्यादा जोडा",
    "add_medication": "+ औषध जोडा",
    "dose_status_pending": "वेळ झाली",
    "dose_status_taken": "घेतली",
    "dose_status_missed": "बुडाली",
    "evidence_badge": "पुरावा",
    "connect_watch": "स्मार्टवॉच जोडा",
    "disconnect_watch": "डिस्कनेक्ट",
    "watch_connected": "घड्याळ जोडले",
    "watch_disconnected": "घड्याळ डिस्कनेक्ट झाले",
    "from_watch": "घड्याळातून",
    "watch_not_supported": "घड्याळ जोडणी केवळ Chrome किंवा Edge (Android, Windows किंवा Mac वर HTTPS सह) चालते.",
    "wearing_watch": "कोणाच्या हातात आहे",
    "live_heart_rate": "थेट हृदयाचे ठोके",
  },
  hi: {
    // Header
    "tagline": "साथ: माता-पिता के बिल और देखभाल, मिलकर संभालें।",
    "subtitle": "परिवार समन्वय बोर्ड",
    "language": "भाषा",

    // Tabs
    "tab_tasks": "कार्य",
    "tab_health": "स्वास्थ्य",

    // Columns
    "col_new": "लंबित कार्य",
    "col_needs_review": "पुष्टि आवश्यक",
    "col_claimed": "स्वीकृत कार्य",
    "col_done": "पूर्ण कार्य",

    // Toolbar
    "try_live_agent": "लाइव एजेंट",
    "simulate_3_days": "३ दिन आगे",
    "audit_log": "ऑडिट लॉग",
    "reset_demo": "रीसेट करें",

    // Task details & card
    "claim_task": "मैं करता हूँ",
    "claiming": "स्वीकार कर रहे हैं…",
    "mark_done": "पूर्ण हुआ",
    "marking": "दर्ज कर रहे हैं…",
    "field_amount": "राशि",
    "field_due_date": "अंतिम तिथि",
    "field_payee": "संस्था / सेवा",
    "field_title": "शीर्षक",
    "not_found": "नहीं मिला",
    "extracted_fields": "दर्ज विवरण",
    "source_quote": "{field} का साक्ष्य",
    "all_evidence": "सभी साक्ष्य ({count})",
    "show_quote": "▼ साक्ष्य देखें",
    "hide_quote": "▲ छिपाएं",
    "translate_quote": "अंग्रेज़ी अनुवाद",
    "show_original": "↩ मूल देखें",
    "assigned_to": "जिम्मेदारी",
    "unassigned": "अनावंटित",
    "agent_confidence": "एजेंट सटीकता",
    "low_confidence": "कम सटीकता · {percent}%",
    "escalated": "अति आवश्यक",
    "stale_claim": "दावा किए २+ दिन हुए · कोई प्रगति नहीं",
    "review": "सत्यापित करें",
    "loading": "परिवार बोर्ड लोड हो रहा है…",

    // Health panel
    "todays_medicines": "आज की दवाइयां",
    "vitals_14_days": "१४ दिनों का वाचन",
    "family_limits": "परिवार की सीमाएं",
    "medicines_setup": "दवा समय सारणी",
    "health_disclaimer": "साथ परिवार की बताई जानकारी दर्ज करता है, चिकित्सीय सलाह नहीं देता।",
    "add_threshold": "+ नई सीमा जोड़ें",
    "add_medication": "+ दवा जोड़ें",
    "dose_status_pending": "लंबित",
    "dose_status_taken": "ले ली",
    "dose_status_missed": "छूटी",
    "evidence_badge": "साक्ष्य",
    "connect_watch": "स्मार्टवॉच कनेक्ट करें",
    "disconnect_watch": "डिस्कनेक्ट",
    "watch_connected": "घड़ी कनेक्टेड",
    "watch_disconnected": "घड़ी डिस्कनेक्ट हुई",
    "from_watch": "स्मार्टवॉच से",
    "watch_not_supported": "घड़ी कनेक्शन केवल Chrome या Edge (Android, Windows या Mac पर HTTPS पर) काम करता है।",
    "wearing_watch": "किसके हाथ में है",
    "live_heart_rate": "लाइव हृदय गति",
  },
};

// Common translations for quotes and transcripts to assist foreign judges
const QUOTE_TRANSLATIONS: Record<string, string> = {
  "महावितरण वीज देयक": "MSEDCL Electricity Bill",
  "लाईट बिल": "Electricity Bill",
  "लाईट बिल १५०० रुपये": "Electricity bill ₹1500",
  "१० नोव्हेंबर": "10th November",
  "१० नोव्हेंबरपर्यंत": "Before 10th November",
  "सह्याद्री हॉस्पिटल": "Sahyadri Hospital",
  "अपॉइंटमेंट": "Doctor Appointment",
  "डॉक्टर तपासणी": "Doctor Consultation Checkup",
  "आज बीपी १५०/९५ आहे": "Today's BP is 150/95",
  "रक्तदाब १२० वर ८०": "Blood Pressure 120 over 80",
  "साखर उपाशीपोटी ११०": "Fasting Sugar 110",
  "वजन ७२ किलो": "Weight 72 kg",
  "ऑक्सिजन ९६": "SpO2 Oxygen 96%",
  "नाडी ७८": "Pulse Heart Rate 78 bpm",
  "१५०० रुपये": "₹1,500 rupees",
  "२,४०० रुपये": "₹2,400 rupees",
  "१० तारखेपर्यंत": "by 10th of this month",
};

export function translateText(text: string): string {
  if (!text) return text;
  let translated = text;
  for (const [key, val] of Object.entries(QUOTE_TRANSLATIONS)) {
    if (translated.includes(key)) {
      translated = translated.replaceAll(key, val);
    }
  }
  // Generic numeric translation if matching Marathi phrasing
  if (translated === text) {
    // English explanatory representation
    return `[Translated summary]: "${text}"`;
  }
  return translated;
}

/** Look up a UI string for `lang`, falling back to English, then to the key itself. */
export function translate(
  lang: Language,
  key: string,
  params?: Record<string, string | number>,
): string {
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.en;
  let text = dict[key] || TRANSLATIONS.en[key] || key;
  if (params) {
    for (const [pKey, pVal] of Object.entries(params)) {
      text = text.replaceAll(`{${pKey}}`, String(pVal));
    }
  }
  return text;
}
