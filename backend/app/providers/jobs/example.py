"""Invented jobs, used until a real source has API keys. Shown as example data in the UI."""

from app.schemas.job import JobDraft


def _job(external_id: str, title: str, company: str, location: str, region: str, **extra):
    return JobDraft(
        source="example",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        region=region,
        **extra,
    )


EXAMPLE_JOBS = (
    _job(
        "ex-1", "Junior Python Developer", "Example Freight Tech", "Auckland CBD, Auckland",
        "Auckland", salary_min=75000, salary_max=85000,
        description="Build Python and FastAPI services with SQL and Git for NZ importers.",
    ),
    _job(
        "ex-2", "Backend Engineer", "Demo Payments", "Auckland CBD, Auckland", "Auckland",
        salary_min=95000, salary_max=110000,
        description="Python, SQL, REST APIs and Git. Some AWS is a bonus.",
    ),
    _job(
        "ex-3", "Automation Engineer", "Sample Retail", "Remote", "",
        description="Automate operations with Python, REST APIs and Git.",
    ),
    _job(
        "ex-4", "Data Analyst", "Sample Health NZ", "Wellington Central, Wellington", "Wellington",
        salary_min=70000, salary_max=80000,
        description="Reporting with SQL, Python, Excel and Power BI.",
    ),
    _job(
        "ex-5", "Integration Developer", "Example Logistics", "Lower Hutt, Wellington",
        "Wellington", description="Connect partner systems with REST APIs, Python and MuleSoft.",
    ),
    _job(
        "ex-6", "Senior Python Developer", "Demo Insurance", "Auckland CBD, Auckland", "Auckland",
        description="Lead a Python team.",
    ),
    _job(
        "ex-7", "Support Engineer", "Demo Energy", "Christchurch Central, Canterbury",
        "Canterbury", description="Support Python tools and SQL reports.",
    ),
    _job(
        "ex-8", "Python Developer", "Sample Defence Systems", "Wellington Central, Wellington",
        "Wellington", description="Python and FastAPI. Must be a New Zealand citizen.",
    ),
)


class ExampleJobSource:
    name = "example"

    def search(self, keywords: str) -> list[JobDraft]:
        return list(EXAMPLE_JOBS)
