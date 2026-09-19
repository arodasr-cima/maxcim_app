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


def generate(client, consonante, **extra):
    payload = {"consonante": consonante, "count": 10, **extra}
    return client.post("/api/bits/generate", json=payload)


def test_consonants_are_the_22_letters_in_two_rows_of_eleven():
    rows = app_module.BITS_CONSONANT_ROWS
    assert [len(row) for row in rows] == [11, 11]
    letters = app_module.BITS_CONSONANTS
    assert len(letters) == len(set(letters)) == 22
    assert not set(letters) & set("AEIOU")
    assert "Ñ" in letters and "CH" not in letters


def test_words_that_do_not_start_with_the_chosen_consonant_are_dropped(client, fake_bits):
    fake_bits(["mano", "mesa", "pelota", "sol", "oso", "Mapa", "luna"])

    body = generate(client, "M").get_json()

    assert [item["palabra"] for item in body["items"]] == ["mano", "mesa", "Mapa"]


def test_prompt_names_only_the_chosen_consonant(client, fake_bits):
    models = fake_bits(["mano"])

    generate(client, "M")

    prompt = models.prompts[0]
    assert "primera letra" in prompt
    assert ": m. De las 10 palabras" in prompt
    assert "consonantes indicadas" not in prompt
    assert "sílabas objetivo" not in prompt


@pytest.mark.parametrize("sent, letter", [("m", "M"), (" ñ ", "Ñ"), ("Z", "Z")])
def test_title_shows_the_normalized_consonant(client, fake_bits, sent, letter):
    fake_bits([f"{letter.lower()}ala"])

    body = generate(client, sent).get_json()

    assert body["title"] == f"Bits: consonante {letter}"


def test_enye_words_match_even_when_the_model_sends_a_decomposed_n(client, fake_bits):
    decomposed = unicodedata.normalize("NFD", "ñandú")
    assert decomposed[0] == "n"
    fake_bits([decomposed, "nube", "ñoño"])

    only_enye = generate(client, "Ñ").get_json()["items"]
    only_n = generate(client, "N").get_json()["items"]

    assert [item["palabra"] for item in only_enye] == [decomposed, "ñoño"]
    assert [item["palabra"] for item in only_n] == ["nube"]


def test_error_when_no_word_starts_with_the_consonant(client, fake_bits):
    fake_bits(["oso", "ala"])

    response = generate(client, "M")

    assert response.status_code == 502
    assert "palabras" in response.get_json()["error"]


@pytest.mark.parametrize("invalid", [["M"], ["M", "S"], "MS", "A", "1", "", None, 3])
def test_only_a_single_consonant_letter_is_accepted(client, fake_bits, invalid):
    models = fake_bits(["mano"])

    response = generate(client, invalid)

    assert response.status_code == 400
    assert models.prompts == []


def test_audience_is_fixed_but_the_teacher_chooses_how_many_words(client, fake_bits):
    models = fake_bits(["mano"])

    generate(client, "M", count=6, grade_level="quinto de secundaria", cantidad_silabas=7)

    prompt = models.prompts[0]
    assert "niños de inicial de 5 años" in prompt
    assert "quinto de secundaria" not in prompt
    assert "Escribe exactamente 6 palabras" in prompt


def test_prompt_asks_for_a_ninety_ten_syllable_mix_of_the_chosen_count(client, fake_bits):
    models = fake_bits(["mano"])

    generate(client, "M", count=10)
    generate(client, "M", count=20)

    assert "9 deben tener EXACTAMENTE 2 sílabas y 1 EXACTAMENTE 3 sílabas" in models.prompts[0]
    assert "18 deben tener EXACTAMENTE 2 sílabas y 2 EXACTAMENTE 3 sílabas" in models.prompts[1]


@pytest.mark.parametrize("count, expected", [
    (10, (9, 1)), (20, (18, 2)), (5, (4, 1)), (2, (1, 1)), (1, (1, 0)), (15, (13, 2)),
])
def test_syllable_mix_is_about_ninety_ten_with_at_least_one_of_three(count, expected):
    assert app_module.bits_syllable_mix(count) == expected


def test_bits_form_offers_one_radio_per_consonant_in_two_rows(client):
    html = client.get("/material").get_data(as_text=True)

    assert html.count('class="consonant-picker__row"') == 2
    assert 'class="consonant-picker" role="radiogroup"' in html
    for letter in app_module.BITS_CONSONANTS:
        assert f'role="radio" data-consonant="{letter}" aria-checked="false"' in html
    assert "aria-pressed" not in html


def test_bits_form_asks_for_consonant_word_count_and_optional_details(client):
    html = client.get("/material").get_data(as_text=True)

    for removed in ('id="bitsGrade"', 'id="bitsSyllableCount"', 'id="bitsSyllables"'):
        assert removed not in html
    default = app_module.BITS_DEFAULT_WORDS
    assert f'id="bitsCount" required min="1" max="{app_module.MAX_BITS_PER_REQUEST}"' in html
    assert f'value="{default}"' in html
    assert 'id="bitsDetails"' in html
