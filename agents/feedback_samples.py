"""Mock user feedback for the live demo, written the way real users write.

The messages imitate an Indonesian e-commerce app (the report's case study): casual
Indonesian with English tech words, some all-English messages, typos, slang, emoji,
star ratings, crash-reporter summaries and customer-service forwards. A few contain
fake contact details so the PII masking is visible. Some messages describe the same
problem in different words, so the duplicate search has something to find.

The `expected_*` labels and `cluster` are hidden answers used only by tests and
documentation; GET /feedback/inbox never returns them. The evaluation harness does
not use these messages (it keeps agents/synthetic_data.py, so report numbers stay
reproducible).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

CHANNELS = ("app_store_review", "email", "portal_form", "cs_chat", "slack", "crash_reporter")
WIB = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class FeedbackSample:
    feedback_id: str
    channel: str
    author: str
    text: str
    expected_component: str
    expected_severity: str
    title: str | None = None            # emails and forms have a subject; chats and reviews do not
    metadata: dict[str, Any] = field(default_factory=dict)
    cluster: str | None = None          # messages about the same underlying problem
    flash_sale: bool = False            # part of the 10.10 flash-sale burst scenario

    def public(self, received_at: str) -> dict[str, Any]:
        """The inbox view: what a support tool would show, without the hidden answers."""
        return {"feedback_id": self.feedback_id, "channel": self.channel, "author": self.author,
                "received_at": received_at, "title": self.title, "text": self.text,
                "metadata": dict(self.metadata)}


S = FeedbackSample
SAMPLES: tuple[FeedbackSample, ...] = (
    # --- Flash sale 10.10: paying crashes the app, money taken but no order -----------------
    S("FB-001", "crash_reporter", "crash-bot · user note",
      "Aplikasi langsung nutup sendiri pas aku pencet Bayar di flash sale jam 20.03, saldo GoPay "
      "kepotong tapi pesanan nggak muncul. Udah 2x kejadian 😭",
      "payment", "Critical", metadata={"app_version": "4.18.2", "platform": "Android", "device": "Redmi Note 12"},
      cluster="pay-crash", flash_sale=True),
    S("FB-002", "app_store_review", "rinaaa_s",
      "Aplikasi langsung nutup sendiri pas aku pencet Bayar di flash sale jam 20.03!! Saldo GoPay "
      "kepotong tapi pesanan nggak muncul. Udah 2x kejadian, tolong cepet dicek 😭",
      "payment", "Critical", metadata={"rating": 1, "app_version": "4.18.2", "platform": "Android"},
      cluster="pay-crash", flash_sale=True),
    S("FB-003", "cs_chat", "Pelanggan via live chat",
      "Halo kak, aplikasinya nutup sendiri pas aku pencet Bayar di flash sale, saldo GoPay udah "
      "kepotong tapi pesanan nggak muncul di riwayat. Gimana ini kak?",
      "payment", "Critical", metadata={"platform": "Android"}, cluster="pay-crash", flash_sale=True),
    S("FB-004", "app_store_review", "yoga.r",
      "App crashed right when I tapped Pay during the 10.10 flash sale. My GoPay balance was charged "
      "but there is no order. 1 star until this is fixed.",
      "payment", "Critical", metadata={"rating": 1, "app_version": "4.18.2", "platform": "Android"},
      cluster="pay-crash", flash_sale=True),
    S("FB-005", "slack", "#cs-escalation",
      "CS escalation: wave of 'payment failed / app closed' reports since 20:00 during the flash sale, "
      "mostly Android 4.18.2. Many users say the e-wallet balance was deducted without an order.",
      "payment", "Critical", title="Flash sale payment crashes", cluster="pay-crash", flash_sale=True),
    S("FB-006", "crash_reporter", "crash-bot",
      "Crash spike on checkout: IllegalStateException at PaymentSheet.onConfirm, 2,143 reports in "
      "4 minutes (Android 14, app version 4.18.2).",
      "payment", "High", title="Crash spike: PaymentSheet.onConfirm",
      metadata={"app_version": "4.18.2", "platform": "Android", "occurrences": 2143}, flash_sale=True),
    S("FB-007", "slack", "#cs-escalation",
      "Tim CS: banyak pelanggan komplain tidak bisa checkout sejak jam 8 malam, sebagian besar "
      "pengguna Android. Yang pakai iPhone aman.",
      "payment", "High", title="Banyak gagal checkout sejak 20.00", flash_sale=True),
    S("FB-008", "app_store_review", "dimas_pratama",
      "Bayar pakai QRIS selalu gagal pas flash sale, muncul error 'transaksi tidak dapat diproses'. "
      "Pakai VA BCA bisa sih tapi barangnya keburu habis 🙃",
      "payment", "High", metadata={"rating": 2, "platform": "Android"}, flash_sale=True),

    # --- Login and OTP -----------------------------------------------------------------------
    S("FB-010", "email", "andi.w",
      "Selamat malam, sudah 3 kali saya minta kode OTP untuk login tapi SMS-nya tidak masuk sama "
      "sekali. Nomor saya 0812-3456-7890, mohon dibantu. Terima kasih.",
      "login", "High", title="Kode OTP tidak masuk", cluster="otp"),
    S("FB-011", "app_store_review", "bellaaa",
      "OTP gak masuk2 dari tadi, gabisa login sama sekali. Udah coba kirim ulang tetep ga ada SMS nya",
      "login", "High", metadata={"rating": 1, "platform": "Android"}, cluster="otp"),
    S("FB-012", "cs_chat", "Pelanggan via WhatsApp",
      "kak kode OTP nya gak masuk2, jadi gabisa login sama sekali. udah coba kirim ulang 3x tetep ga ada SMS",
      "login", "High", cluster="otp"),
    S("FB-013", "portal_form", "m.hartono",
      "Not receiving the OTP code when logging in on iPhone 13 (iOS 18). I tried resend 5 times, "
      "nothing arrives.",
      "login", "High", title="OTP not received", metadata={"platform": "iOS", "device": "iPhone 13"},
      cluster="otp"),
    S("FB-014", "app_store_review", "nadia.k",
      "After updating to version 4.18.2 I can't log in anymore, it just spins forever on the login screen.",
      "login", "High", metadata={"rating": 2, "app_version": "4.18.2", "platform": "iOS"}),
    # The idea report's worked example (section 3.1): A and B describe the same problem, C does not.
    S("FB-015", "portal_form", "user-4471", "Aplikasi crash saat login, koneksi timeout.",
      "login", "High", title="Aplikasi crash saat login", cluster="login-crash"),
    S("FB-016", "portal_form", "user-5102", "Login gagal, aplikasi force-close, sering timeout.",
      "login", "High", title="Login gagal dan force close", cluster="login-crash"),
    S("FB-017", "email", "sari.dewi",
      "Akun saya terkunci setelah salah password 3x. Tolong hubungi saya di sari.dewi@mailbox.example "
      "atau 0857 1122 3344.",
      "login", "Medium", title="Akun terkunci"),

    # --- Account and profile -----------------------------------------------------------------
    S("FB-020", "portal_form", "user-1187", "Tombol 'Simpan' di halaman profil tidak berfungsi.",
      "account", "Medium", title="Tombol Simpan di profil"),
    S("FB-021", "app_store_review", "fajar_h",
      "Gabisa simpan alamat baru, tombol Simpan diklik ga ada respon. Pakai iPhone 11.",
      "account", "Medium", metadata={"rating": 3, "platform": "iOS", "device": "iPhone 11"}),
    S("FB-022", "email", "hendra.s",
      "Saya bisa lihat alamat dan nomor HP orang lain di halaman pesanan saya!! Ini data bocor parah, "
      "mohon segera ditangani.",
      "account", "Critical", title="Data pelanggan lain terlihat"),
    S("FB-023", "email", "laura.m",
      "Hi team, the Track order page shows another customer's name and address instead of mine. "
      "This looks like a serious privacy breach.",
      "delivery", "Critical", title="Wrong customer data on Track order"),

    # --- Payments outside the flash sale -----------------------------------------------------
    S("FB-030", "email", "pt.maju.jaya",
      "I was charged twice for the same order (Rp 1.250.000 each) using my BCA virtual account. "
      "Please refund one of them.",
      "payment", "Critical", title="Double charge on order"),
    S("FB-031", "app_store_review", "tika_ayu",
      "Status pembayaran 'menunggu' terus padahal sudah transfer VA dari 2 jam lalu. Kok lama ya?",
      "payment", "Medium", metadata={"rating": 3}),
    S("FB-032", "cs_chat", "Pelanggan via live chat",
      "Refund pesanan yang dibatalkan belum masuk ke saldo, udah 7 hari kerja kak.",
      "payment", "Medium"),
    S("FB-033", "email", "finance@tokokita.example",
      "Our invoices show PPN 11% instead of 12% since this month. Our finance team needs corrected "
      "invoices for the tax report.",
      "payment", "Medium", title="Wrong tax rate on invoices"),
    S("FB-034", "app_store_review", "rizky.p",
      "Barang di keranjang suka ilang sendiri setelah logout terus login lagi. Nyebelin.",
      "login", "Medium", metadata={"rating": 2}),

    # --- Search --------------------------------------------------------------------------------
    S("FB-040", "app_store_review", "melati88",
      "Pencarian lemot banget sekarang, ketik 'sepatu' aja loading lama hampir 10 detik.",
      "search", "Medium", metadata={"rating": 3}, cluster="search-slow"),
    S("FB-041", "app_store_review", "bayu_n",
      "Pencarian lemot bgt skrg, ketik 'sepatu' doang loadingnya lama banget hampir 10 detik.",
      "search", "Medium", metadata={"rating": 2}, cluster="search-slow"),
    S("FB-042", "portal_form", "putri.l",
      "Would be nice to filter search results by seller rating.",
      "search", "Low", title="Feature request: filter by seller rating"),

    # --- Promo and vouchers --------------------------------------------------------------------
    S("FB-050", "email", "wulan.p",
      "Voucher gratis ongkir 10.10 tidak bisa dipakai, muncul tulisan 'voucher tidak berlaku' padahal "
      "minimal belanja sudah terpenuhi.",
      "promo", "Medium", title="Voucher ongkir tidak bisa dipakai", cluster="voucher"),
    S("FB-051", "app_store_review", "gilang.r",
      "voucher gratis ongkir gak bisa dipake, katanya voucher tidak berlaku padahal udh lewat min belanja",
      "promo", "Medium", metadata={"rating": 2}, cluster="voucher"),
    S("FB-052", "cs_chat", "Pelanggan via WhatsApp",
      "Cashback 10.10 belum masuk ke saldo saya padahal sudah lewat 3 hari.",
      "promo", "Medium"),

    # --- Delivery ------------------------------------------------------------------------------
    S("FB-060", "app_store_review", "ahmad.f",
      "Resi JNE sudah 3 hari tidak update di aplikasi, padahal di web JNE paketnya sudah sampai kota tujuan.",
      "delivery", "Medium", metadata={"rating": 3}),
    S("FB-061", "portal_form", "user-2290",
      "Ongkir di keranjang beda sama di halaman pembayaran, selisih Rp 9.000.",
      "delivery", "Medium", title="Ongkir berbeda"),

    # --- Notifications -------------------------------------------------------------------------
    S("FB-070", "app_store_review", "citra_w",
      "Notif promo masuk tiap 5 menit, ganggu banget. Udah matiin di setting tetep muncul.",
      "notification", "Medium", metadata={"rating": 2}),
    S("FB-071", "email", "joko.s",
      "Email konfirmasi pesanan tidak pernah sampai, padahal pesanan sudah dibayar.",
      "notification", "Medium", title="Email konfirmasi tidak masuk"),

    # --- General app quality ------------------------------------------------------------------
    S("FB-080", "app_store_review", "ratna.d",
      "Abis update ke versi 4.18.2 aplikasinya ga bisa dibuka sama sekali, langsung keluar sendiri. "
      "HP Samsung A52.",
      "app", "High", metadata={"rating": 1, "app_version": "4.18.2", "platform": "Android",
                                "device": "Samsung A52"}),
    S("FB-081", "app_store_review", "kevin.t",
      "Since the last update the app drains my battery even in the background.",
      "app", "Medium", metadata={"rating": 3}),
    S("FB-082", "app_store_review", "dewi_ani",
      "Foto produk lama banget munculnya, padahal sinyal 4G full.",
      "app", "Medium", metadata={"rating": 3}),
    S("FB-083", "portal_form", "user-3315",
      "Ada typo di halaman checkout: 'Pembayran' harusnya 'Pembayaran'.",
      "payment", "Low", title="Typo di halaman checkout"),
    S("FB-084", "app_store_review", "hana.s",
      "Aplikasinya bagus, belanja jadi gampang 👍 Cuma request dark mode dong biar mata ga capek malem2.",
      "app", "Low", metadata={"rating": 5}),
    S("FB-085", "app_store_review", "bimo.a",
      "Fitur chat ke penjual error terus, pesannya ga kekirim.",
      "app", "Medium", metadata={"rating": 2}),
    S("FB-086", "portal_form", "user-7781",
      "The order history page takes more than 10 seconds to load on the website and sometimes times out.",
      "app", "Medium", title="Order history is slow", metadata={"platform": "Web"}),
)
_BY_ID = {sample.feedback_id: sample for sample in SAMPLES}
_BASE_TIME = datetime(2026, 10, 10, 20, 3, tzinfo=WIB)  # the 10.10 flash sale


def get(feedback_id: str) -> FeedbackSample | None:
    return _BY_ID.get(feedback_id)


def background_texts() -> list[str]:
    """Every message, used to fit the duplicate search's document frequencies."""
    return [f"{sample.title or ''} {sample.text}" for sample in SAMPLES]


def inbox(seed: int = 42, count: int = 8, scenario: str = "all") -> list[dict[str, Any]]:
    """A seeded, time-ordered batch of messages as a support inbox would show them."""
    pool = [sample for sample in SAMPLES if sample.flash_sale] if scenario == "flash_sale" else list(SAMPLES)
    rng = random.Random(f"inbox:{scenario}:{seed}")
    chosen = rng.sample(pool, min(max(count, 1), len(pool)))
    items = []
    for sample in chosen:
        if sample.flash_sale:  # the burst arrives within minutes of 20:03
            received = _BASE_TIME + timedelta(seconds=rng.randrange(0, 600))
        else:
            received = _BASE_TIME + timedelta(days=rng.randrange(1, 9), minutes=rng.randrange(0, 1440))
        items.append(sample.public(received.isoformat()))
    return sorted(items, key=lambda item: item["received_at"])
