"""Skill names that mean the same thing.

Matching checks every name, so "AWS" also finds "Amazon Web Services".
"""

# Each key is a skill; its values are the other names it is known by. Links work both ways.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "AWS": ("Amazon Web Services",),
    "GCP": ("Google Cloud",),
    "JavaScript": ("JS",),
    "TypeScript": ("TS",),
    "PostgreSQL": ("Postgres",),
    "SQL Server": ("MS SQL",),
    "Power BI": ("PowerBI",),
    "Excel": ("Microsoft Excel", "MS Excel"),
    "Kubernetes": ("K8s",),
    "Machine learning": ("ML",),
    "CI/CD": ("continuous integration",),
    ".NET": ("dotnet",),
    "Node.js": ("NodeJS",),
    "React": ("React.js",),
}

_LINKS: dict[str, dict[str, str]] = {}
for _name, _others in SYNONYMS.items():
    for _other in _others:
        _LINKS.setdefault(_name.casefold(), {})[_other.casefold()] = _other
        _LINKS.setdefault(_other.casefold(), {})[_name.casefold()] = _name


def variants(skill: str) -> list[str]:
    """The skill as given first, then every name linked to it, directly or through another name."""
    name = skill.strip()
    seen = {name.casefold()}
    found = [name]
    queue = [name.casefold()]
    while queue:
        current = queue.pop(0)
        for key, display in _LINKS.get(current, {}).items():
            if key not in seen:
                seen.add(key)
                found.append(display)
                queue.append(key)
    return found
