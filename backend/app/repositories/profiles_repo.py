from uuid import UUID

import psycopg

from app.schemas.resume import ResumeProfile, SearchPreferences


def first_profile_id(conn: psycopg.Connection) -> UUID | None:
    row = conn.execute("select id from profiles order by created_at, id limit 1").fetchone()
    return row["id"] if row else None


def load_search_context(
    conn: psycopg.Connection, profile_id: UUID | str
) -> tuple[ResumeProfile, SearchPreferences] | None:
    """Load the newest base resume profile and the user's search preferences."""
    row = conn.execute(
        """
        select p.regions, p.work_rights, p.salary_min, p.avoid_keywords, p.shortlist_threshold,
               rp.titles, rp.skills, rp.tools, rp.industries, rp.seniority, rp.search_queries
        from profiles p
        join resumes r on r.profile_id = p.id and r.kind = 'base'
        join resume_profiles rp on rp.resume_id = r.id
        where p.id = %s
        order by r.created_at desc
        limit 1
        """,
        (profile_id,),
    ).fetchone()
    if row is None:
        return None

    resume = ResumeProfile(
        titles=row["titles"],
        skills=row["skills"],
        tools=row["tools"],
        industries=row["industries"],
        seniority=row["seniority"],
        search_queries=row["search_queries"],
    )
    prefs = SearchPreferences(
        regions=row["regions"],
        work_rights=row["work_rights"],
        salary_min=row["salary_min"],
        avoid_keywords=row["avoid_keywords"],
        shortlist_threshold=row["shortlist_threshold"],
    )
    return resume, prefs
