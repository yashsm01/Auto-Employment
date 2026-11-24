from app.chains.alert_chain import AlertExtractChain, AlertJobs
from app.chains.careers_chain import CareersPageChain
from app.chains.links import restore_link, shorten_links
from app.schemas.job import AlertJob
from tests.fakes import ScriptedLLM

LONG = "https://www.indeed.com/rc/clk?jk=abc123&from=ja&tk=" + "x" * 300


def test_long_links_become_short_labels():
    text, links = shorten_links(
        f"Python Developer {LONG}. Apply at {LONG} or https://b.example/job"
    )

    assert text == "Python Developer [link 1]. Apply at [link 1] or [link 2]"
    assert links == {"[link 1]": LONG, "[link 2]": "https://b.example/job"}


def test_markdown_links_keep_their_text():
    text, _ = shorten_links("[Careers](https://acme.co.nz/careers)")

    assert text == "[Careers]([link 1])"


def test_restore_link_maps_a_label_back():
    links = {"[link 1]": LONG}

    assert restore_link("[link 1]", links, "") == LONG
    assert restore_link("link 1", links, "") == LONG


def test_restore_link_drops_an_unknown_or_invented_link():
    original = "See /careers/python-developer"

    assert restore_link("[link 9]", {}, original) is None
    assert restore_link("https://invented.example/job", {}, original) is None
    assert restore_link("/careers/python-developer", {}, original) == "/careers/python-developer"
    assert restore_link(None, {}, original) is None


def _alert(url):
    return AlertJob(title="Python Developer", company="Example Co", url=url)


def test_alert_chain_sends_labels_and_returns_real_links():
    llm = ScriptedLLM(AlertJobs(jobs=[_alert("[link 1]")]))

    jobs = AlertExtractChain(llm).run(f"Python Developer at Example Co {LONG}")

    assert LONG not in llm.calls[0]["user"]
    assert "[link 1]" in llm.calls[0]["user"]
    assert "[link 3]" in llm.calls[0]["system"]
    assert jobs[0].url == LONG


def test_careers_chain_sends_labels_and_returns_real_links():
    page = (
        "Open roles: [Python Developer](https://acme.co.nz/jobs/python-developer?ref="
        + "y" * 200
        + ")"
    )
    llm = ScriptedLLM(AlertJobs(jobs=[_alert("[link 1]")]))

    jobs = CareersPageChain(llm).run("Example Co", "https://acme.co.nz/careers", page)

    assert "y" * 200 not in llm.calls[0]["user"]
    assert jobs[0].url.startswith("https://acme.co.nz/jobs/python-developer?ref=")
