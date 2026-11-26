from uuid import UUID

import psycopg

from app.repositories import profiles_repo, resumes_repo


def _key(skill: str) -> str:
    return skill.strip().casefold()


def decisions(conn: psycopg.Connection, profile_id: UUID | str) -> dict[str, str]:
    rows = conn.execute(
        "select skill_key, decision from skill_decisions where profile_id = %s", (profile_id,)
    ).fetchall()
    return {row["skill_key"]: row["decision"] for row in rows}


def declined_names(conn: psycopg.Connection, profile_id: UUID | str) -> list[str]:
    """The skills the user marked Not me, as they were typed."""
    rows = conn.execute(
        "select skill from skill_decisions where profile_id = %s and decision = 'no' "
        "order by skill",
        (profile_id,),
    ).fetchall()
    return [row["skill"] for row in rows]


def was_added(conn: psycopg.Connection, profile_id: UUID | str, skill: str) -> bool:
    """True when a "have" answer really added the skill, so undoing it may remove the skill."""
    row = conn.execute(
        "select added from skill_decisions where profile_id = %s and skill_key = %s",
        (profile_id, _key(skill)),
    ).fetchone()
    return bool(row and row["added"])


def set_decision(
    conn: psycopg.Connection,
    profile_id: UUID | str,
    skill: str,
    decision: str | None,
    added: bool = False,
) -> None:
    """Store "have" or "no" for a skill. None deletes the decision.

    `added` is True only for a "have" that added the skill to the resume profile or master CV.
    """
    key = _key(skill)
    if decision is None:
        conn.execute(
            "delete from skill_decisions where profile_id = %s and skill_key = %s",
            (profile_id, key),
        )
        return
    conn.execute(
        """
        insert into skill_decisions (profile_id, skill_key, skill, decision, added)
        values (%s, %s, %s, %s, %s)
        on conflict (profile_id, skill_key) do update
            set skill = excluded.skill, decision = excluded.decision, added = excluded.added,
                decided_at = now()
        """,
        (profile_id, key, skill.strip(), decision, added),
    )


def profile_skill_names(conn: psycopg.Connection, profile_id: UUID | str) -> list[str]:
    """The resume profile's skills, then its tools, without repeats."""
    base = resumes_repo.latest_base(conn, profile_id)
    terms = profiles_repo.resume_terms(conn, base["id"]) if base else None
    if terms is None:
        return []
    names = [skill["name"] for skill in terms["skills"] or []] + list(terms["tools"] or [])
    unique: dict[str, str] = {}
    for name in names:
        cleaned = name.strip()
        if cleaned:
            unique.setdefault(cleaned.casefold(), cleaned)
    return list(unique.values())
