"""Scout-Feedback: turning casual user messages into clean, masked tickets."""
import asyncio

from agents import feedback_samples
from agents.text import (derive_title, detect_language, extract_app_version, extract_device_platform,
                         extract_repro_hints, guess_component, normalize_for_matching)


def test_slang_and_written_reduplication_are_normalized():
    assert normalize_for_matching("OTP gak masuk2, gabisa login") == "otp tidak masuk masuk tidak bisa login"
    assert normalize_for_matching("Aplikasi force-close") == "aplikasi force close"


def test_language_title_version_device_and_steps():
    assert detect_language("Aplikasi langsung nutup sendiri pas aku pencet Bayar") == "id"
    assert detect_language("App crashed right when I tapped Pay during the sale") == "en"
    assert derive_title("Gabisa simpan alamat baru, tombol Simpan diklik ga ada respon. Pakai iPhone 11.") \
        == "Gabisa simpan alamat baru, tombol Simpan diklik ga ada respon"
    assert extract_app_version("Abis update ke versi 4.18.2 aplikasinya ga bisa dibuka") == "4.18.2"
    assert extract_app_version("Refund Rp 1.250.000 belum masuk") is None  # prices are not versions
    assert extract_device_platform("HP Samsung A52, Android 14") == ("Samsung A52", "Android")
    assert extract_repro_hints("Saldo hilang. Terjadi saat bayar pakai QRIS.") == ["Terjadi saat bayar pakai QRIS."]


def test_component_guess_matches_the_hand_labelled_corpus():
    misses = [sample.feedback_id for sample in feedback_samples.SAMPLES
              if guess_component(f"{sample.title or ''} {sample.text}")[0] != sample.expected_component]
    assert misses == []


def test_inbox_is_seeded_time_ordered_and_hides_the_answers():
    first = feedback_samples.inbox(seed=7, count=6)
    assert first == feedback_samples.inbox(seed=7, count=6)
    assert [item["received_at"] for item in first] == sorted(item["received_at"] for item in first)
    assert all(set(item) == {"feedback_id", "channel", "author", "received_at", "title", "text", "metadata"}
               for item in first)
    burst = feedback_samples.inbox(seed=1, count=20, scenario="flash_sale")
    assert burst and all(feedback_samples.get(item["feedback_id"]).flash_sale for item in burst)
    languages = {detect_language(sample.text) for sample in feedback_samples.SAMPLES}
    assert {"id", "en"} <= languages


def test_intake_masks_contact_details_and_normalizes_the_ticket(make_pipeline):
    pipeline = make_pipeline()
    ticket = asyncio.run(pipeline.create_ticket(feedback_id="FB-017"))  # an e-mail with an address and a phone
    intake = ticket["agent_outputs"]["intake"]
    assert intake["pii_masked"] == {"emails": 1, "phones": 1, "tokens": 0}
    assert "<EMAIL>" in ticket["body"] and "<PHONE>" in ticket["body"]
    assert "sari.dewi@mailbox.example" not in str(pipeline.audit.events)
    assert ticket["title"] == "Akun terkunci" and ticket["component"] == "login"
    assert ticket["channel"] == "email" and ticket["severity"] == "Unknown"  # triage has not run yet

    review = asyncio.run(pipeline.create_ticket(feedback_id="FB-080"))  # an app-store review, no title
    assert review["title_derived"] is True and review["app_version"] == "4.18.2"
    assert review["platform"] == "Android" and review["language"] == "id"
