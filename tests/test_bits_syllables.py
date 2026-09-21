import json
import unicodedata
from types import SimpleNamespace

import pytest

import app as app_module


class BitsModels:
    def __init__(self, words):
        self.words = words
        self.prompts = []

    def generate_content(self, *, contents, **_kwargs):
        self.prompts.append(contents)
        return SimpleNamespace(text=json.dumps({"palabras": self.words}))


@pytest.fixture()
def fake_bits(monkeypatch):
    def install(words):
        models = BitsModels(words)
        monkeypatch.setattr(app_module, "gemini_client", SimpleNamespace(models=models))
        return models
    return install


def generate(client, silabas, **extra):
    payload = {"silabas": silabas, "count": 10, **extra}
    return client.post("/api/bits/generate", json=payload)


def test_words_that_do_not_start_with_any_chosen_syllable_are_dropped(client, fake_bits):
    fake_bits(["mano", "mesa", "pelota", "sol", "oso", "Mapa", "luna"])

    body = generate(client, "ma").get_json()

    assert [item["palabra"] for item in body["items"]] == ["mano", "Mapa"]


def test_a_word_matching_any_of_several_syllables_is_kept(client, fake_bits):
    fake_bits(["mano", "sapo", "luna", "oso"])

    body = generate(client, "ma, sa").get_json()

    assert [item["palabra"] for item in body["items"]] == ["mano", "sapo"]


def test_prompt_names_all_the_chosen_syllables(client, fake_bits):
    models = fake_bits(["mano"])

    generate(client, "ma, sa")

    prompt = models.prompts[0]
    assert "primera sílaba" in prompt
    assert ": ma, sa. Reparte las 10 palabras" in prompt


@pytest.mark.parametrize("sent, expected", [
    ("m", "m"), (" MA ", "ma"), ("ma,  se", "ma, se"),
])
def test_title_shows_the_normalized_syllables(client, fake_bits, sent, expected):
    fake_bits(["mano"])

    body = generate(client, sent).get_json()

    assert body["title"] == f"Bits: sílabas {expected}"


def test_syllables_match_even_when_the_model_sends_a_decomposed_accent(client, fake_bits):
    decomposed = unicodedata.normalize("NFD", "ñoño")
    fake_bits([decomposed, "nube"])

    only_enye = generate(client, "ño").get_json()["items"]
    only_n = generate(client, "nu").get_json()["items"]

    assert [item["palabra"] for item in only_enye] == [decomposed]
    assert [item["palabra"] for item in only_n] == ["nube"]


def test_error_when_no_word_starts_with_any_syllable(client, fake_bits):
    fake_bits(["oso", "ala"])

    response = generate(client, "ma")

    assert response.status_code == 502
    assert "palabras" in response.get_json()["error"]


@pytest.mark.parametrize("invalid", [None, 3, {}, "", "   ", [], ["", "  "]])
def test_at_least_one_syllable_is_required(client, fake_bits, invalid):
    models = fake_bits(["mano"])

    response = generate(client, invalid)

    assert response.status_code == 400
    assert "sílaba" in response.get_json()["error"]
    assert models.prompts == []


def test_syllable_list_is_capped_deduped_and_lowercased(client, fake_bits):
    models = fake_bits(["mano"])
    many = ", ".join(["ma", "MA", " ma ", "me", "mi", "mo", "mu", "pa", "pe"])

    generate(client, many)

    prompt = models.prompts[0]
    assert prompt.count(": ma, me, mi, mo, mu, pa.") == 1


def test_audience_is_fixed_but_the_teacher_chooses_how_many_words(client, fake_bits):
    models = fake_bits(["mano"])

    generate(client, "ma", count=6, grade_level="quinto de secundaria")

    prompt = models.prompts[0]
    assert "niños de inicial de 5 años" in prompt
    assert "quinto de secundaria" not in prompt
    assert "Escribe exactamente 6 palabras" in prompt


def test_prompt_asks_for_a_ninety_ten_syllable_mix_of_the_chosen_count(client, fake_bits):
    models = fake_bits(["mano"])

    generate(client, "ma", count=10)
    generate(client, "ma", count=20)

    assert "9 deben tener EXACTAMENTE 2 sílabas y 1 EXACTAMENTE 3 sílabas" in models.prompts[0]
    assert "18 deben tener EXACTAMENTE 2 sílabas y 2 EXACTAMENTE 3 sílabas" in models.prompts[1]


@pytest.mark.parametrize("count, expected", [
    (10, (9, 1)), (20, (18, 2)), (5, (4, 1)), (2, (1, 1)), (1, (1, 0)), (15, (13, 2)),
])
def test_syllable_mix_is_about_ninety_ten_with_at_least_one_of_three(count, expected):
    assert app_module.bits_syllable_mix(count) == expected


@pytest.mark.parametrize("raw, expected", [
    ("ma, me  mi", ["ma", "me", "mi"]),
    (["MA", " Me ", "ma"], ["ma", "me"]),
    ("a" * 20, ["a" * 10]),
])
def test_normalize_bits_syllables_splits_dedupes_and_caps(raw, expected):
    assert app_module.normalize_bits_syllables(raw) == expected


def test_normalize_bits_syllables_caps_the_list_length():
    many = ", ".join(f"s{i}" for i in range(20))
    assert len(app_module.normalize_bits_syllables(many)) == app_module.MAX_BITS_SYLLABLES


def test_bits_form_has_a_free_text_syllables_field_instead_of_a_consonant_picker(client):
    html = client.get("/material").get_data(as_text=True)

    assert 'id="bitsSyllables"' in html
    assert "consonant-picker" not in html
    assert 'data-consonant' not in html


def test_bits_form_asks_for_syllables_word_count_and_optional_details(client):
    html = client.get("/material").get_data(as_text=True)

    for removed in ('id="bitsGrade"', 'id="bitsSyllableCount"'):
        assert removed not in html
    default = app_module.BITS_DEFAULT_WORDS
    assert f'id="bitsCount" required min="1" max="{app_module.MAX_BITS_PER_REQUEST}"' in html
    assert f'value="{default}"' in html
    assert 'id="bitsDetails"' in html
