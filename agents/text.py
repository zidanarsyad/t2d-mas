"""Text helpers Scout-Feedback uses to turn casual user feedback into a structured ticket.

Feedback arrives in casual Indonesian, English, or a mix ("udh 3x coba bayar tp
aplikasinya fc"). These rules are deliberately simple and explainable: a slang map,
small keyword lists and a few regular expressions.
"""
from __future__ import annotations

import re

# Common chat abbreviations and spellings, mapped to one standard form so the
# triage cues and the duplicate search see the same words.
SLANG = {
    "gk": "tidak", "gak": "tidak", "ga": "tidak", "nggak": "tidak", "ngga": "tidak", "enggak": "tidak",
    "tdk": "tidak", "g": "tidak", "gabisa": "tidak bisa", "gbs": "tidak bisa", "gbisa": "tidak bisa",
    "udh": "sudah", "udah": "sudah", "sdh": "sudah", "blm": "belum", "bgt": "banget", "yg": "yang",
    "dgn": "dengan", "krn": "karena", "tp": "tapi", "pake": "pakai", "lg": "lagi", "aja": "saja",
    "sm": "sama", "trs": "terus", "jd": "jadi", "dr": "dari", "utk": "untuk", "tlg": "tolong",
    "fc": "force close", "lemot": "lambat", "eror": "error", "kepotong": "terpotong",
    "nutup": "menutup", "ketutup": "tertutup", "ilang": "hilang", "gimana": "bagaimana",
    "knp": "kenapa", "gmn": "bagaimana", "cs": "customer service", "pls": "please", "plz": "please",
    "cant": "can't", "dont": "don't", "doesnt": "doesn't", "wont": "won't",
}
_WORD = re.compile(r"[a-z0-9']+")
_REDUPLICATION = re.compile(r"^([a-z]{2,})2$")  # "masuk2" means "masuk-masuk"

ID_WORDS = {
    "yang", "dan", "tidak", "saya", "aku", "bisa", "sudah", "belum", "saat", "pas", "kok", "dong", "ya",
    "banget", "aplikasi", "tolong", "mohon", "kenapa", "padahal", "terus", "lagi", "ini", "itu", "di",
    "ke", "dari", "untuk", "dengan", "sama", "mau", "gimana", "bagaimana", "pakai", "masuk", "bayar",
    "kakak", "kak", "min", "gan", "sih", "nih", "deh", "jadi", "tapi", "karena", "udah", "nggak",
}
EN_WORDS = {
    "the", "and", "not", "when", "after", "please", "my", "is", "was", "to", "for", "with", "this", "it",
    "i", "can't", "cannot", "keeps", "every", "time", "since", "update", "app", "again", "just", "but",
    "have", "has", "been", "of", "on", "in", "you", "your", "we", "our", "customers", "users", "doesn't",
}

COMPONENT_CUES = {
    # Words that point to the part of the product (and the squad) a message is about.
    "payment": ("bayar", "pembayaran", "checkout", "check out", "qris", "saldo", "gopay", "ovo",
                "dana", "e wallet", "ewallet", "kartu kredit", "virtual account", "va", "transfer",
                "refund", "tagihan", "invoice", "invoices", "pajak", "ppn", "tax", "payment", "pay",
                "paid", "charged", "card", "debited", "keranjang", "cart"),
    "login": ("login", "log in", "masuk akun", "otp", "kode verifikasi", "verification code", "password",
              "sandi", "akun terkunci", "sign in", "signin", "2fa", "logout"),
    "search": ("cari", "pencarian", "search", "hasil pencarian", "filter", "kata kunci"),
    "delivery": ("kirim", "pengiriman", "paket", "kurir", "resi", "tracking", "track order", "lacak",
                 "ongkir", "delivery", "shipping", "courier", "parcel"),
    "promo": ("promo", "voucher", "gratis ongkir", "diskon", "cashback", "kupon", "coupon", "discount"),
    "notification": ("notif", "notifikasi", "push notification", "pemberitahuan", "notification",
                     "email konfirmasi"),
    "account": ("profil", "profile", "alamat", "address", "ubah data", "data diri", "foto profil",
                "simpan", "save button"),
    # The generic bucket: app-wide quality problems with no specific feature named.
    "app": ("crash", "force close", "keluar sendiri", "menutup sendiri", "tertutup sendiri", "lambat",
            "lama banget", "loading", "hang", "freeze", "slow", "baterai", "battery", "dark mode",
            "tampilan", "ui", "foto produk", "chat ke penjual", "chat penjual"),
}
_VERSION = re.compile(r"\b(?:v|versi|version|ver|app)\s*\.?\s*(\d{1,2}\.\d{1,3}(?:\.\d{1,3})?)\b", re.I)
_DEVICE = re.compile(
    r"\b(iphone\s?\d{1,2}(?:\s?(?:pro max|pro|plus|mini))?|samsung(?:\s?galaxy)?\s?[a-z]\d{1,3}\w*|"
    r"(?:xiaomi|redmi|poco|oppo|vivo|realme|infinix)\s?[a-z0-9]{1,6}(?:\s?(?:pro|note))?|pixel\s?\d{1,2})",
    re.I)
_PLATFORM = (("android", "Android"), ("ios", "iOS"), ("iphone", "iOS"), ("ipad", "iOS"),
             ("chrome", "Web"), ("browser", "Web"), ("website", "Web"), ("desktop", "Web"), ("web", "Web"))
_REPRO_CUES = ("saat", "pas", "ketika", "waktu", "setelah", "abis", "habis", "tiap kali", "setiap",
               "when", "after", "every time", "whenever", "since", "sejak")


def normalize_for_matching(text: str) -> str:
    """Lowercase, expand slang and join hyphenated words ("force-close" -> "force close")."""
    lowered = str(text or "").lower().replace("-", " ").replace("_", " ")
    words = []
    for word in _WORD.findall(lowered):
        doubled = _REDUPLICATION.match(word)
        if doubled:  # written reduplication: "masuk2" -> "masuk masuk"
            words += [doubled.group(1)] * 2
        else:
            words.append(word)
    return " ".join(SLANG.get(word, word) for word in words)


def detect_language(text: str) -> str:
    """Return "id", "en" or "mixed" by counting common Indonesian and English words."""
    words = _WORD.findall(str(text or "").lower())
    indonesian = sum(word in ID_WORDS or word in SLANG for word in words)
    english = sum(word in EN_WORDS for word in words)
    if indonesian == english == 0:
        return "en"
    share = indonesian / (indonesian + english)
    return "id" if share >= 0.75 else "en" if share <= 0.25 else "mixed"


def derive_title(text: str, limit: int = 80) -> str:
    """Use the first sentence as a title, trimmed at a word boundary."""
    clean = re.sub(r"[^\w\s.,:;!?'/%()&+-]", " ", str(text or ""))
    clean = re.sub(r"\s+", " ", clean).strip()
    first = re.split(r"(?<=[.!?])\s+|\n", clean, maxsplit=1)[0].strip(" .!?")
    title = first if len(first) >= 12 else clean
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return title[:1].upper() + title[1:] if title else "Feedback without text"


def extract_app_version(text: str) -> str | None:
    match = _VERSION.search(str(text or ""))
    return match.group(1) if match else None


def extract_device_platform(text: str) -> tuple[str | None, str | None]:
    """Return (device, platform) mentioned in the text, if any."""
    lowered = str(text or "").lower()
    device_match = _DEVICE.search(str(text or ""))
    device = device_match.group(1).strip() if device_match else None
    platform = next((name for cue, name in _PLATFORM if re.search(rf"\b{cue}\b", lowered)), None)
    if platform is None and device:
        platform = "iOS" if device.lower().startswith("iphone") else "Android"
    return device, platform


def extract_repro_hints(text: str, limit: int = 3) -> list[str]:
    """Sentences that describe when the problem happens ("saat bayar pakai QRIS ...")."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n", str(text or "")) if part.strip()]
    hints = [sentence for sentence in sentences
             if any(re.search(rf"\b{cue}\b", sentence.lower()) for cue in _REPRO_CUES)]
    return [hint[:160] for hint in hints[:limit]]


def guess_component(text: str) -> tuple[str, float, list[str]]:
    """Return (component, confidence, matched cues); "other" when nothing matches.

    A named feature (payment, login, search, ...) beats the generic "app" bucket,
    because "slow" or "crash" describe the symptom, not where it happens. Among
    features, the one mentioned most wins; on a tie, the one mentioned first wins,
    because people usually lead with what they are complaining about.
    """
    normalized = f" {normalize_for_matching(text)} "
    found: dict[str, list[tuple[int, str]]] = {}
    for component, cues in COMPONENT_CUES.items():
        for cue in cues:
            start = normalized.find(f" {cue} ")
            while start != -1:
                found.setdefault(component, []).append((start, cue))
                start = normalized.find(f" {cue} ", start + 1)
    if not found:
        return "other", 0.0, []

    def rank(name: str) -> tuple[int, int, int]:
        mentions = found[name]
        return (name != "app", len(mentions), -min(position for position, _cue in mentions))

    best = max(found, key=rank)
    total = sum(len(mentions) for mentions in found.values())
    cues = sorted({cue for _position, cue in found[best]})
    return best, round(len(found[best]) / total, 2), cues
