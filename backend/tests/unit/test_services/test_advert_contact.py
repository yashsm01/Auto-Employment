from app.services.advert_contact import AdvertContact, advert_contact, applies_on_site_only


def test_advert_contact_reads_a_named_contact_with_phone():
    description = (
        "Great team to join. Talk to Jane Example, Talent Partner, jane@example.co.nz "
        "or call 09 555 1234 to apply."
    )

    assert advert_contact(description) == AdvertContact(
        name="Jane Example", role="Talent Partner", email="jane@example.co.nz",
        phone="09 555 1234",
    )


def test_advert_contact_ignores_a_bare_company_name():
    assert advert_contact("Contact Example Freight Tech for details.") is None
    assert advert_contact("Talk to Example Freight about the role.") is None
    assert advert_contact("Build pipelines with Python. Apply online.") is None


def test_site_only_phrases_and_jobs_govt_nz():
    assert applies_on_site_only("Please APPLY ONLINE ONLY through our site.", None)
    assert applies_on_site_only("Apply only through our careers page.", None)
    assert applies_on_site_only("Applications through SEEK only.", None)
    assert applies_on_site_only("Only applications submitted on the form are read.", None)
    assert applies_on_site_only("Please do not contact us about this role.", None)
    assert applies_on_site_only("No direct approaches to staff.", None)
    assert applies_on_site_only("No direct contact, please.", None)
    assert applies_on_site_only("No direct applications by email.", None)
    assert applies_on_site_only("Apply online. No agencies or direct contact, please.", None)
    assert applies_on_site_only("Apply via our careers site only.", None)
    assert not applies_on_site_only("No agencies, please.", None)
    assert not applies_on_site_only("No recruitment agencies thanks.", None)
    assert not applies_on_site_only("Send your CV to jobs@x.co.nz. No agencies.", None)
    assert applies_on_site_only("Send your CV to jobs@freight.example.", "https://www.jobs.govt.nz/job/1")
    assert not applies_on_site_only("Send your CV to jobs@freight.example.", None)
    assert not applies_on_site_only("Build pipelines. Apply online.", "https://freight.example/jobs")


def test_a_job_title_is_not_read_as_a_person():
    contact = advert_contact("Contact Hiring Manager, Jane Smith at jane@x.co.")

    assert contact == AdvertContact(name="Jane Smith", role="Hiring Manager",
                                    email="jane@x.co", phone=None)


def test_a_company_name_with_nothing_to_contact_them_by_is_not_a_contact():
    assert advert_contact("Talk to Example Freight, Auckland") is None
    assert advert_contact("Talk to Example Services, Auckland.", company="Example Services") is None


def test_a_named_contact_with_a_phone_still_works():
    assert advert_contact("Contact Jane Smith, Talent Partner, on 021 555 0101") == AdvertContact(
        name="Jane Smith", role="Talent Partner", email=None, phone="021 555 0101")
