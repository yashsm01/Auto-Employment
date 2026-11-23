"""Employer records. Phase 1 uses details from the job post. NZBN and Places come next."""

import psycopg

from app.repositories import companies_repo, jobs_repo
from app.schemas.job import JobDraft, StoredJob
from app.services.lead_service import job_hash


def store_jobs(conn: psycopg.Connection, jobs: list[JobDraft]) -> list[StoredJob]:
    stored = []
    for job in jobs:
        company_id = companies_repo.upsert_from_job(conn, job)
        companies_repo.add_job_post_facts(conn, company_id, job)
        job_id = jobs_repo.insert(conn, job, company_id, job_hash(job))
        if job_id is not None:
            stored.append(StoredJob(job_id=job_id, draft=job))
    return stored
