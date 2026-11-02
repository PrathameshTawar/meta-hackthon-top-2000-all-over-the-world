"""
Centralized Internationalization (i18n) for Saath.
Single-language consistency: avoids confusing bilingual mixes (e.g. '✅ Claim / मी करतो').
Supports Marathi ('mr'), Hindi ('hi'), and English ('en').
"""
import re
from typing import Optional

SUPPORTED_LANGUAGES = ("mr", "hi", "en")
DEFAULT_LANGUAGE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    # Buttons
    "btn_claim": {
        "en": "Claim Task",
        "mr": "मी करतो",
        "hi": "मैं करता हूँ",
    },
    "btn_done": {
        "en": "Mark Done",
        "mr": "पूर्ण झाले",
        "hi": "पूर्ण हुआ",
    },
    "btn_correct": {
        "en": "Correct",
        "mr": "बरोबर",
        "hi": "सही",
    },
    "btn_wrong": {
        "en": "Wrong",
        "mr": "चूक",
        "hi": "गलत",
    },
    "btn_view_board": {
        "en": "View Board",
        "mr": "बोर्ड पहा",
        "hi": "बोर्ड देखें",
    },
    "btn_dose_taken": {
        "en": "Taken ✅",
        "mr": "घेतली ✅",
        "hi": "ले ली ✅",
    },

    # Language Switch
    "choose_language_prompt": {
        "en": "Please choose your preferred language:",
        "mr": "कृपया तुमची भाषा निवडा:",
        "hi": "कृपया अपनी पसंदीदा भाषा चुनें:",
    },
    "language_changed": {
        "en": "Language set to English. ✅",
        "mr": "भाषा मराठी निवडली आहे. ✅",
        "hi": "भाषा हिंदी चुनी गई है। ✅",
    },

    # System & Webhooks
    "unregistered_user": {
        "en": "You are not registered yet. Please ask your family to add you to the Saath board.",
        "mr": "तुम्ही अजून नोंदणीकृत नाही. कृपया तुमच्या कुटुंबातील कोणाला सांगा की तुम्हाला जोडावे.",
        "hi": "आप अभी पंजीकृत नहीं हैं। कृपया अपने परिवार से कहें कि वे आपको जोड़ें।",
    },
    "task_claimed_ack": {
        "en": "✅ Task #{task_id} ('{title}') has been claimed by you on the family board.\nWhen finished, tap Mark Done.",
        "mr": "✅ काम #{task_id} ('{title}') तुम्ही स्वीकारले आहे.\nकाम झाल्यावर 'पूर्ण झाले' दाबा.",
        "hi": "✅ काम #{task_id} ('{title}') आपने स्वीकार कर लिया है।\nपूरा होने पर 'पूर्ण हुआ' दबाएं।",
    },
    "task_already_claimed": {
        "en": "⚠️ This task has already been claimed by another sibling.",
        "mr": "⚠️ हे काम आधीच दुसऱ्या भावंडाने स्वीकारले आहे.",
        "hi": "⚠️ यह काम पहले ही दूसरे भाई/बहन ने ले लिया है।",
    },
    "task_already_yours": {
        "en": "You have already claimed this task.",
        "mr": "हे काम आधीच तुम्ही स्वीकारले आहे.",
        "hi": "यह काम आपने पहले ही स्वीकार कर लिया है।",
    },
    "task_done_ack": {
        "en": "✔️ '{title}' marked as done. Parents have been notified. 🙏",
        "mr": "✔️ '{title}' काम पूर्ण झाल्याचे नोंदवले आहे. पालकांना कळवले आहे. 🙏",
        "hi": "✔️ '{title}' काम पूरा दर्ज किया गया है। माता-पिता को सूचित कर दिया गया है। 🙏",
    },
    "task_already_done": {
        "en": "✔️ This task is already marked done. Parents were already notified. 🙏",
        "mr": "✔️ हे काम आधीच पूर्ण झाले आहे. पालकांना आधीच कळवले आहे. 🙏",
        "hi": "✔️ यह काम पहले ही पूरा हो चुका है। माता-पिता को सूचित किया जा चुका है। 🙏",
    },
    "not_your_household": {
        "en": "⚠️ This task does not belong to your household.",
        "mr": "⚠️ हे काम तुमच्या कुटुंबाचे नाही.",
        "hi": "⚠️ यह काम आपके परिवार का नहीं है।",
    },
    "confirm_verified_ack": {
        "en": "✅ Information confirmed! Task added to the family board. 🙏",
        "mr": "✅ माहितीची पुष्टी झाली! काम कुटुंब बोर्डवर जोडले आहे. 🙏",
        "hi": "✅ जानकारी की पुष्टि हो गई! काम परिवार के बोर्ड में जोड़ दिया गया है। 🙏",
    },
    "confirm_cancelled_ack": {
        "en": "❌ Okay, we cancelled this task. Please send again if needed. 🙏",
        "mr": "❌ ठीक आहे, आम्ही हे काम रद्द केले आहे. कृपया पुन्हा पाठवा. 🙏",
        "hi": "❌ ठीक है, हमने यह काम रद्द कर दिया है। कृपया ज़रूरत पड़ने पर दोबारा भेजें। 🙏",
    },
    "please_verify_title": {
        "en": "❓ Please verify extracted details for family board:",
        "mr": "❓ कृपया कुटुंब बोर्डसाठी तपशील तपासा:",
        "hi": "❓ कृपया परिवार बोर्ड के लिए विवरण सत्यापित करें:",
    },
    "why_verification_needed": {
        "en": "Why verification is needed:",
        "mr": "खात्रीची आवश्यकता:",
        "hi": "सत्यापन की आवश्यकता क्यों है:",
    },
    "parent_reassurance": {
        "en": "🙏 Document received! The children are verifying details to handle it, don't worry! 😊",
        "mr": "🙏 तुमचे बिल/माहिती मिळाली आहे. कुटुंबातील मुले याची खात्री करून काम पूर्ण करत आहेत, काळजी करू नका! 😊",
        "hi": "🙏 आपका दस्तावेज़ प्राप्त हुआ। बच्चे इसकी पुष्टि करके काम पूरा कर रहे हैं, चिंता न करें! 😊",
    },
    "parent_default_received": {
        "en": "Your message was received. We will update you shortly.",
        "mr": "तुमचा संदेश मिळाला. आम्ही लवकरच कळवतो.",
        "hi": "आपका संदेश प्राप्त हुआ। हम शीघ्र ही सूचित करेंगे।",
    },
    "no_pending_tasks": {
        "en": "No pending tasks right now! Everything is settled. 🙏",
        "mr": "सध्या कोणतीही कामे बाकी नाहीत! सर्व कामे पूर्ण झाली आहेत. 🙏",
        "hi": "फिलहाल कोई काम बाकी नहीं है! सभी काम पूरे हो चुके हैं। 🙏",
    },
    "pending_tasks_header": {
        "en": "📋 Current pending family tasks:",
        "mr": "📋 सध्या बाकी असलेली कामे:",
        "hi": "📋 वर्तमान में लंबित कार्य:",
    },
    "invalid_media_format": {
        "en": "Please send a clear photo (JPEG/PNG) or voice note. PDF is not supported for this type.",
        "mr": "कृपया बिलाचा स्पष्ट फोटो (JPEG/PNG) किंवा व्हॉईस नोट पाठवा. PDF सध्या समर्थित नाही.",
        "hi": "कृपया स्पष्ट फोटो (JPEG/PNG) या वॉयस नोट भेजें। PDF समर्थित नहीं है।",
    },
}


def t(key: str, lang: Optional[str] = "en", **kwargs) -> str:
    """Lookup localized string with template parameter formatting."""
    lang_code = (lang or "en").lower().strip()
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = "en"

    entry = TRANSLATIONS.get(key)
    if not entry:
        return key

    raw_str = entry.get(lang_code) or entry.get("en") or entry.get("mr", key)
    if kwargs:
        try:
            return raw_str.format(**kwargs)
        except Exception:
            return raw_str
    return raw_str


def is_language_command(text: str) -> bool:
    """Return True if message requests changing language."""
    clean = text.strip().lower()
    return clean in {
        "भाषा", "भाषा बदला", "language", "change language",
        "select language", "switch language", "bhasha", "bhasha badla"
    }


def detect_language(text: str) -> str:
    """
    Detects language based on script and vocabulary markers:
    Returns 'mr' (Marathi), 'hi' (Hindi), or 'en' (English).
    """
    if not text:
        return "mr"

    # Check for Devanagari unicode range (0x0900 - 0x097F)
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    if not has_devanagari:
        return "en"

    text_lower = text.lower()

    # Marathi vocabulary markers
    mr_markers = [
        "आहे", "नाही", "कधी", "करा", "होय", "बदला", "बाकी", "साखर",
        "रक्तदाब", "घेतली", "केले", "का", "तुमचे", "आमचे", "दिले",
        "सांगा", "पहा", "आले", "असेल", "झाले", "करावे", "कोण",
    ]
    # Hindi vocabulary markers
    hi_markers = [
        "है", "नहीं", "कब", "करो", "हाँ", "बदलो", "बचा", "चीनी",
        "ले ली", "किया", "क्या", "आपका", "हमारा", "दिया", "बिजली",
        "बताओ", "देखो", "आया", "होगा", "हुआ", "करना", "कौन",
    ]

    words = set(re.findall(r"[\u0900-\u097F]+", text_lower))
    mr_score = sum(1 for m in mr_markers if m in words or m in text_lower)
    hi_score = sum(1 for m in hi_markers if m in words or m in text_lower)

    if hi_score > mr_score:
        return "hi"
    return "mr"
