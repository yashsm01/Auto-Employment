-- EXAMPLE DATA ONLY. Replace with your real profile once your resume is added.

insert into profiles (
    id, full_name, field, target_roles, regions, work_rights,
    salary_min, avoid_keywords, shortlist_threshold
) values (
    '00000000-0000-4000-8000-000000000001',
    'Example Candidate',
    'Software development',
    array['Python Developer', 'Backend Developer', 'Automation Engineer'],
    array['Auckland', 'Wellington', 'Remote NZ'],
    'open_visa',
    65000,
    array['senior', 'lead', 'sales'],
    70
) on conflict (id) do nothing;

insert into settings (profile_id)
values ('00000000-0000-4000-8000-000000000001')
on conflict (profile_id) do nothing;

insert into resumes (id, profile_id, kind, content) values (
    '00000000-0000-4000-8000-000000000002',
    '00000000-0000-4000-8000-000000000001',
    'base',
    '{"example": true, "summary": "Example developer profile used until a real resume is added."}'
) on conflict (id) do nothing;

insert into resume_profiles (resume_id, titles, skills, tools, industries, seniority) values (
    '00000000-0000-4000-8000-000000000002',
    array['Python Developer', 'Backend Developer', 'Automation Engineer'],
    '[
        {"name": "Python", "years": 2},
        {"name": "FastAPI", "years": 1},
        {"name": "SQL", "years": 2},
        {"name": "REST API", "years": 2},
        {"name": "Git", "years": 2},
        {"name": "Excel", "years": 3}
    ]',
    '{}',
    array['Logistics', 'Operations', 'Internal tools'],
    'junior to mid'
) on conflict (resume_id) do nothing;
