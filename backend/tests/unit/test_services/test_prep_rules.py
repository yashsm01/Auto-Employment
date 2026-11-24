import pytest

from app.schemas.prep import EvidenceItem, Fact, PageSource, WriteDraft
from app.services.prep_service import (
    Budget,
    assemble_pack,
    call_model,
    cost_nzd,
    directions_link,
    missing_kinds,
    normalise,
    verify_facts,
)
from tests.fakes import ScriptedLLM


def page(source_id: str, text: str, kind: str = "website") -> PageSource:
    return PageSource(id=source_id, url=f"https://example.co.nz/{source_id}", title="Page",
                      kind=kind, text=text)


def fact(source_id: str, quote: str, kind: str = "about") -> Fact:
    return Fact(kind=kind, text=f"Fact from {quote}", source_id=source_id, quote=quote)


def make_draft(**overrides) -> WriteDraft:
    return WriteDraft(**overrides)


def test_quote_must_appear_in_its_page():
    pages = {"s1": page("s1", "We build freight software for NZ ports.")}

    kept, dropped = verify_facts(
        [fact("s1", "freight software for NZ ports"), fact("s1", "won an award")], pages
    )

    assert [f.quote for f in kept] == ["freight software for NZ ports"]
    assert [f.quote for f in dropped] == ["won an award"]


def test_quote_with_unknown_source_or_over_25_words_is_dropped():
    words = " ".join(f"word{i}" for i in range(26))
    pages = {"s1": page("s1", words)}

    kept, dropped = verify_facts([fact("s9", "word1"), fact("s1", words)], pages)

    assert kept == []
    assert len(dropped) == 2


def test_macrons_and_curly_quotes_still_match():
    pages = {"s1": page("s1", "Based in Whangārei, working with “Ngāi Tahu” partners’ teams.")}

    kept, _ = verify_facts([fact("s1", 'working with "Ngāi Tahu" partners\' teams')], pages)

    assert len(kept) == 1


def test_whitespace_and_case_do_not_matter():
    assert normalise("  We   BUILD\n apps ") == "we build apps"


def test_budget_stops_at_each_limit_and_says_why():
    budget = Budget()

    assert [budget.allow("query") for _ in range(5)] == [True, True, True, True, False]
    assert budget.stopped_by == "Stopped searching after 4 searches."


@pytest.mark.parametrize(
    ("kind", "limit", "message"),
    [
        ("page", 6, "Stopped reading after 6 pages."),
        ("explore", 3, "Stopped exploring after 3 extra steps."),
        ("model", 12, "Stopped at the spending limit for one run."),  # 2 kept for writing
    ],
)
def test_every_budget_limit_has_a_reason(kind, limit, message):
    budget = Budget()
    for _ in range(limit):
        assert budget.allow(kind)

    assert budget.allow(kind) is False
    assert budget.stopped_by == message


def test_can_checks_without_spending():
    budget = Budget(max_explore=1)

    assert budget.can("explore") is True
    assert budget.can("explore") is True
    assert budget.explore == 0
    assert budget.stopped_by is None


def test_budget_refuses_model_calls_past_the_cost_ceiling():
    budget = Budget()
    budget.record("claude-sonnet-5-5", 10_000, 10_000)  # 0.02 + 0.10 = US$0.12

    assert budget.cost_usd == pytest.approx(0.12)
    assert budget.allow("model") is False
    assert budget.stopped_by == "Stopped at the spending limit for one run."


def test_haiku_is_priced_lower_and_unknown_models_as_sonnet():
    budget = Budget()
    budget.record("claude-haiku-5-5", 1_000_000, 1_000_000)
    assert budget.cost_usd == pytest.approx(0.60)

    unknown = Budget()
    unknown.record("some-new-model", 1_000_000, 0)
    assert unknown.cost_usd == pytest.approx(2.00)


def test_call_model_records_usage_and_returns_the_result():
    llm = ScriptedLLM("answer")
    budget = Budget()

    def call():
        llm.parse(system="s", user="u", schema=str)
        llm.input_tokens += 1_000_000
        return "answer"

    assert call_model(budget, llm, "claude-haiku-5-5", call) == "answer"
    assert budget.model_calls == 1
    assert budget.cost_usd == pytest.approx(0.10)


def test_call_model_returns_none_when_the_budget_refuses():
    budget = Budget(max_model_calls=0)

    assert call_model(budget, ScriptedLLM(), "claude-haiku-5-5", lambda: "never") is None


def test_the_pack_takes_employer_lines_only_from_verified_facts():
    facts = [
        fact("s2", "builds port software", kind="about"),
        fact("s2", "builds port software", kind="about"),  # same text twice
        fact("s4", "opened a Dunedin office", kind="news"),
        fact("s3", "$85,000 to $100,000", kind="pay"),
        fact("s1", "hybrid working", kind="practical"),
        fact("s5", "two interview rounds", kind="interview"),
    ]
    dropped = [fact("s2", "won an award")]

    pack = assemble_pack(make_draft(), facts, dropped, resume_text="", directions_url="https://maps/x")

    assert [(line.text, line.source_ids, line.quote) for line in pack.employer] == [
        ("Fact from builds port software", ["s2"], "builds port software"),
        ("Fact from opened a Dunedin office", ["s4"], "opened a Dunedin office"),
    ]
    assert pack.pay.text == "Fact from $85,000 to $100,000"
    assert [line.text for line in pack.practical] == ["Fact from hybrid working"]
    assert pack.directions_url == "https://maps/x"
    assert pack.could_not_verify == ["Fact from won an award"]


def test_the_pack_has_no_pay_without_a_verified_pay_fact():
    assert assemble_pack(make_draft(), [], [], resume_text="", directions_url=None).pay is None


def test_evidence_not_in_the_resume_is_marked_check():
    draft = make_draft(
        evidence=[
            EvidenceItem(requirement="SQL", evidence="Led a team of 40", status="matched"),
            EvidenceItem(requirement="Reports", evidence="wrote SQL REPORTS.", status="matched"),
            EvidenceItem(requirement="Go", evidence=None, status="gap"),
        ]
    )

    pack = assemble_pack(draft, [], [], resume_text="Wrote SQL reports.", directions_url=None)

    assert [item.status for item in pack.evidence] == ["check", "matched", "gap"]


def test_a_fact_whose_text_adds_a_number_is_dropped():
    text = "Xero has many staff in Wellington and serves 5.1 million customers."
    pages = {"s1": page("s1", text)}
    added = Fact(kind="about", text="Xero has 2,000 staff", source_id="s1", quote="has many staff")
    kept_number = Fact(kind="about", text="Serves 5.1 million customers", source_id="s1",
                       quote="serves 5.1 million customers")

    kept, dropped = verify_facts([added, kept_number], pages)

    assert kept == [kept_number]
    assert dropped == [added]


def test_facts_about_named_people_are_never_kept_or_shown():
    pages = {"s1": page("s1", "Chief executive Jane Example leads the company from Wellington.")}
    person = Fact(kind="about", text="Jane Example is the CEO", source_id="s1",
                  quote="Chief executive Jane Example leads the company")

    kept, dropped = verify_facts([person], pages)

    assert (kept, dropped) == ([], [])


def test_writing_keeps_a_reserve_when_other_calls_use_the_budget():
    budget = Budget(max_model_calls=4)

    assert [budget.allow("model") for _ in range(3)] == [True, True, False]
    assert budget.allow("write") is True
    assert budget.allow("write") is True
    assert budget.allow("write") is False


def test_other_calls_stop_early_so_writing_can_still_be_paid_for():
    budget = Budget()
    budget.record("claude-sonnet-5-5", 0, 7_000)  # US$0.07 spent

    assert budget.allow("model") is False
    assert budget.allow("write") is True


def test_missing_kinds_lists_needed_kinds_without_facts():
    facts = [fact("s1", "x", kind="about"), fact("s1", "y", kind="pay")]

    assert missing_kinds(facts, ["about", "news", "pay", "interview"]) == ["news", "interview"]


def test_directions_link_encodes_places():
    assert directions_link("Timaru", "12 Example St, Dunedin") == (
        "https://www.google.com/maps/dir/?api=1&origin=Timaru"
        "&destination=12+Example+St%2C+Dunedin"
    )
    assert directions_link(None, "Dunedin") == (
        "https://www.google.com/maps/dir/?api=1&destination=Dunedin"
    )
    assert directions_link("Timaru", None) is None


def test_cost_is_shown_in_nzd_to_two_places():
    assert cost_nzd(0.0431, 1.70) == 0.07
