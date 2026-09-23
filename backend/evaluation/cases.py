"""Curated semantic-ranking evaluation cases against the real dataset.

This is NOT ML training or fine-tuning. Each case pairs a hard-filter
request with a free-text `preferences` string and states what the dataset's
own description text supports about the expected outcome. Two levels of
expectation are used, deliberately:

- `expected_first`: used only where the source descriptions make the
  relative order unambiguous to a human reader (e.g. one contractor's
  description explicitly says "only dance and entertainment", another
  explicitly says "calm, business-style hosting") — checked strictly.
- `expected_in_top`: used where the dataset supports a *plausible* semantic
  match but not a provably exclusive ranking — checked as "appears in the
  top 3", not first place. This avoids pretending there is ground-truth
  relevance where the data doesn't support one.

Re-run `evaluation/run.py` after any change to the embedding model, the
canonical semantic document (`build_semantic_document`), or the segmentation
logic in `app.services.evidence`, to catch regressions.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EvalCase:
    name: str
    intent: str
    city: str
    event_date: date
    event_format: str
    category: str
    budget_kzt: int
    preferences: str
    rationale: str
    duration_hours: int | None = None
    language: str | None = None
    # Strict: this id must rank first among the eligible pool.
    expected_first: str | None = None
    # Soft: at least one of these ids must appear in the top 3.
    expected_in_top: frozenset[str] | None = None


CASES: list[EvalCase] = [
    EvalCase(
        name="calm_intelligent_unobtrusive_host",
        intent="calm / intelligent / unobtrusive presenter",
        city="Алматы",
        event_date=date(2026, 10, 10),
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
        preferences="спокойная деловая интеллигентная подача, корпоративный стиль",
        rationale=(
            "HK-88430 explicitly states 'интеллигентный юмор', corporate/business "
            "events focus; HK-77838 explicitly says 'интеллигентной, располагающей и "
            "ненавязчивой подачей'. Contrasts with HK-29829, whose entire description "
            "is 'только развлечения и танцы' (pure entertainment/dance)."
        ),
        expected_in_top=frozenset({"HK-88430", "HK-77838"}),
    ),
    EvalCase(
        name="active_entertainment_dancing_host",
        intent="active entertainment / dancing",
        city="Алматы",
        event_date=date(2026, 10, 10),
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=700_000,
        preferences="яркое шоу с танцами и развлечениями",
        rationale=(
            "HK-29829's entire description is 'Без долгих речей... Только "
            "развлечения и танцы' — the only host profile in the eligible pool at "
            "this budget/date whose stated focus is entertainment and dancing, "
            "versus HK-88430's stated corporate/business focus."
        ),
        expected_first="HK-29829",
    ),
    EvalCase(
        name="corporate_business_audience_host",
        intent="corporate / business audience",
        city="Алматы",
        event_date=date(2026, 10, 5),
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_200_000,
        preferences="деловая аудитория, крупный бизнес-форум",
        rationale=(
            "HK-44733 explicitly names 'крупные бизнес форумы на 3000 человек' and "
            "corporate/conference project history (NEXT MBA)."
        ),
        expected_in_top=frozenset({"HK-44733", "HK-88430"}),
    ),
    EvalCase(
        name="documentary_wedding_photography",
        intent="documentary wedding photography",
        city="Астана",
        event_date=date(2026, 10, 5),
        event_format="свадьба",
        category="Фотограф",
        budget_kzt=500_000,
        preferences="документальная репортажная свадебная съёмка без постановки",
        rationale=(
            "HK-61323 explicitly names 'свадебный фотожурнализм' (wedding "
            "photojournalism) / documentary style in its description — the only "
            "explicit documentary-style claim among eligible Астана wedding "
            "photographers at this date/budget."
        ),
        expected_in_top=frozenset({"HK-61323"}),
    ),
    EvalCase(
        name="aesthetic_emotional_photography",
        intent="aesthetic / emotional photography",
        city="Алматы",
        event_date=date(2026, 11, 20),
        event_format="свадьба",
        category="Фотограф",
        budget_kzt=1_000_000,
        preferences="эстетичные эмоциональные кадры, настроение и атмосфера, не шаблонная красота",
        rationale=(
            "HK-91112 explicitly foregrounds 'эстетику и эмоций', 'не про позы, а "
            "про состояние'. HK-30583 also foregrounds 'эстетика, атмосфера, "
            "детали'. Neither HK-76268 nor HK-53108 use this vocabulary as "
            "centrally."
        ),
        expected_in_top=frozenset({"HK-91112", "HK-30583"}),
    ),
    EvalCase(
        name="premium_event_decor",
        intent="premium event decor",
        city="Алматы",
        event_date=date(2026, 10, 15),
        event_format="свадьба",
        category="Декоратор",
        budget_kzt=2_500_000,
        preferences="премиальный декор под ключ, индивидуальная концепция",
        rationale=(
            "HK-11484 explicitly says 'премиум-уровня', 'под ключ', 'индивидуальная "
            "концепция'; HK-90004 also says 'премиум-уровня' and 'индивидуальным "
            "эскизом'. HK-90003 is decor but does not use premium/bespoke language."
        ),
        expected_in_top=frozenset({"HK-11484", "HK-90004"}),
    ),
    EvalCase(
        name="modern_minimalist_decor",
        intent="modern minimalistic decor",
        city="Алматы",
        event_date=date(2026, 10, 15),
        event_format="корпоратив",
        category="Декоратор",
        budget_kzt=2_500_000,
        preferences="современный минималистичный декор, световые инсталляции",
        rationale=(
            "HK-90003 explicitly describes 'световые и объёмные инсталляции: "
            "неоновые вывески, шар-гирлянды' — the only decorator profile centered "
            "on lighting/installation-style modern decor rather than bespoke "
            "premium concepts."
        ),
        expected_in_top=frozenset({"HK-90003"}),
    ),
    EvalCase(
        name="national_traditional_performance",
        intent="national / traditional performance",
        city="Алматы",
        event_date=date(2026, 10, 5),
        event_format="той",
        category="Национальный ансамбль",
        budget_kzt=600_000,
        preferences="национальный казахский колорит, традиционное выступление",
        rationale=(
            "All eligible candidates share the 'Национальный ансамбль' category "
            "and Kazakh national framing (HK-92824, HK-36965, HK-39301, HK-19103) — "
            "the dataset does not clearly differentiate a *more* national profile "
            "among them, so only membership in the eligible pool is checked."
        ),
        expected_in_top=frozenset({"HK-92824", "HK-36965", "HK-39301", "HK-19103"}),
    ),
    EvalCase(
        name="interactive_photo_booth",
        intent="interactive photo booth",
        city="Алматы",
        event_date=date(2026, 10, 15),
        event_format="свадьба",
        category="Фото и видеобудки",
        budget_kzt=500_000,
        preferences="интерактивная фотобудка с моментальной печатью для гостей",
        rationale=(
            "HK-90009 explicitly describes 'интерактивная фотобудка с мгновенной "
            "печатью'; HK-35846 also emphasizes 'интерактивные фото/видеозоны' as "
            "one of its three offerings. Both use 'интерактив*' vocabulary "
            "directly."
        ),
        expected_in_top=frozenset({"HK-90009", "HK-35846"}),
    ),
    EvalCase(
        name="business_forum_vs_dance_reversed",
        intent="business audience preference on a mixed-style pool",
        city="Алматы",
        event_date=date(2026, 10, 10),
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=700_000,
        preferences="серьёзный деловой стиль без развлекательной программы",
        rationale=(
            "Same eligible pool as active_entertainment_dancing_host "
            "({HK-88430, HK-29829}). KNOWN LIMITATION found by this harness: with "
            "negated phrasing ('без развлекательной программы') the E5 model still "
            "ranks the dance/entertainment profile (HK-29829) first — it does not "
            "reliably handle negation, a documented limitation of dense embedding "
            "similarity generally. Kept as a soft/documented case rather than a "
            "strict one so the evaluation records the limitation instead of forcing "
            "a ranking the model doesn't actually produce. See docs/spec.md "
            "'Limitations of semantic similarity'."
        ),
        expected_in_top=frozenset({"HK-88430", "HK-29829"}),
    ),
    EvalCase(
        name="live_band_premium_sound",
        intent="premium live band sound",
        city="Алматы",
        event_date=date(2026, 10, 15),
        event_format="свадьба",
        category="Лайв-бэнд",
        budget_kzt=2_000_000,
        preferences="премиальное живое звучание, джазовый состав",
        rationale=(
            "Live-band candidates are grouped by qualitative differences in the "
            "dataset (jazz vs. general covers) — checked softly since the "
            "exact wording varies per profile and isn't uniformly explicit."
        ),
        expected_in_top=None,
    ),
    EvalCase(
        name="gift_and_souvenir_corporate_branding",
        intent="corporate branded gifts/souvenirs",
        city="Алматы",
        event_date=date(2026, 10, 15),
        event_format="корпоратив",
        category="Подарки и сувениры",
        budget_kzt=200_000,
        preferences="брендированный корпоративный мерч с логотипом компании",
        rationale=(
            "HK-90005/HK-60927 describe sweets/souvenir craft without explicit "
            "corporate-branding language in the eligible-at-this-date pool — "
            "recorded to detect regressions in a category with less distinctive "
            "vocabulary, not to assert a strong expected winner."
        ),
        expected_in_top=None,
    ),
]
