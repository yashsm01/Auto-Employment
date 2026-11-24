from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.schemas.resume import BoardEntry, ProfileUpdate, ResumeProfile, SearchPreferences


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


def load_view_row(conn: psycopg.Connection, profile_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        select p.regions, p.work_rights, p.salary_min, p.avoid_keywords, p.shortlist_threshold,
               r.content, rp.titles, rp.skills, rp.tools, rp.industries, rp.seniority,
               rp.search_queries, coalesce(s.data_sources -> 'boards', '[]') as boards
        from profiles p
        join resumes r on r.profile_id = p.id and r.kind = 'base'
        join resume_profiles rp on rp.resume_id = r.id
        left join settings s on s.profile_id = p.id
        where p.id = %s
        order by r.created_at desc
        limit 1
        """,
        (profile_id,),
    ).fetchone()


def load_boards(conn: psycopg.Connection, profile_id: UUID | str) -> list[BoardEntry]:
    row = conn.execute(
        "select coalesce(data_sources -> 'boards', '[]') as boards "
        "from settings where profile_id = %s",
        (profile_id,),
    ).fetchone()
    return [BoardEntry(**board) for board in row["boards"]] if row else []


def has_example_resume(conn: psycopg.Connection, profile_id: UUID | str) -> bool:
    row = conn.execute(
        """
        select r.content ->> 'example' = 'true' as example
        from resumes r
        where r.profile_id = %s and r.kind = 'base'
        order by r.created_at desc
        limit 1
        """,
        (profile_id,),
    ).fetchone()
    return bool(row and row["example"])


def clear_example_data(conn: psycopg.Connection, profile_id: UUID) -> None:
    """Remove invented jobs and settings. Real jobs and companies are untouched."""
    companies = [
        row["company_id"]
        for row in conn.execute(
            "select distinct company_id from jobs "
            "where source = 'example' and company_id is not null"
        ).fetchall()
    ]
    conn.execute("delete from jobs where source = 'example'")
    conn.execute(
        """
        delete from companies c
        where c.id = any(%s) and not exists (select 1 from jobs j where j.company_id = c.id)
        """,
        (companies,),
    )
    conn.execute(
        "delete from resumes where profile_id = %s and kind = 'base' "
        "and content ->> 'example' = 'true'",
        (profile_id,),
    )
    conn.execute(
        "update profiles set work_rights = null, salary_min = null where id = %s", (profile_id,)
    )


def add_base_resume(
    conn: psycopg.Connection,
    profile_id: UUID,
    content: dict[str, Any],
    file_path: str,
    resume: ResumeProfile,
) -> None:
    row = conn.execute(
        """
        insert into resumes (profile_id, kind, content, file_path)
        values (%s, 'base', %s, %s)
        returning id
        """,
        (profile_id, Jsonb(content), file_path),
    ).fetchone()
    conn.execute(
        """
        insert into resume_profiles (resume_id, titles, skills, tools, industries, seniority)
        values (%s, %s, %s, %s, %s, %s)
        """,
        (
            row["id"],
            resume.titles,
            Jsonb([skill.model_dump() for skill in resume.skills]),
            resume.tools,
            resume.industries,
            resume.seniority,
        ),
    )
    conn.execute(
        "update profiles set target_roles = %s where id = %s", (resume.titles, profile_id)
    )


def update_profile(conn: psycopg.Connection, profile_id: UUID, update: ProfileUpdate) -> None:
    conn.execute(
        """
        update profiles set
            target_roles = %s, regions = %s, work_rights = %s, salary_min = %s,
            avoid_keywords = %s, shortlist_threshold = %s
        where id = %s
        """,
        (
            update.titles, update.regions, update.work_rights, update.salary_min,
            update.avoid_keywords, update.shortlist_threshold, profile_id,
        ),
    )
    conn.execute(
        """
        update resume_profiles set
            titles = %s, skills = %s, tools = %s, search_queries = %s, updated_at = now()
        where resume_id = (
            select id from resumes
            where profile_id = %s and kind = 'base'
            order by created_at desc
            limit 1
        )
        """,
        (
            update.titles,
            Jsonb([skill.model_dump() for skill in update.skills]),
            update.tools,
            update.search_queries,
            profile_id,
        ),
    )
    boards = [board.model_dump() for board in update.boards]
    conn.execute(
        """
        insert into settings (profile_id, data_sources) values (%s, %s)
        on conflict (profile_id) do update set
            data_sources = settings.data_sources || excluded.data_sources,
            updated_at = now()
        """,
        (profile_id, Jsonb({"boards": boards})),
    )
