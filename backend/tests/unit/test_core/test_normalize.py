import pytest

from app.core.normalize import contains_term, parse_annual_salary


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$75,000 - $85,000", (75000, 85000)),
        ("NZ$75–85k", (75000, 85000)),
        ("$95k to $110k", (95000, 110000)),
        ("$90k", (90000, 90000)),
        ("$110,000 plus 3% KiwiSaver", (110000, 110000)),
        ("5 weeks leave and $80,000", (80000, 80000)),
        ("$30 per hour", (None, None)),
        ("$35.50 - $40 an hour", (None, None)),
        ("Competitive", (None, None)),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_annual_salary(text, expected):
    assert parse_annual_salary(text) == expected


@pytest.mark.parametrize(
    ("text", "term", "expected"),
    [
        ("We use C# and .NET daily", "C#", True),
        ("We use C# and .NET daily", ".NET", True),
        ("Java developers wanted", "JavaScript", False),
        ("JavaScript developer", "Java", False),
        ("Strong PostgreSQL skills", "SQL", False),
        ("Build REST APIs", "REST API", True),
        ("Power BI dashboards", "power bi", True),
        ("Leading a small team", "lead", False),
        ("Team lead needed", "lead", True),
    ],
)
def test_contains_term_respects_word_boundaries(text, term, expected):
    assert contains_term(text, term) is expected
