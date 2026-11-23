import psycopg
from psycopg.rows import dict_row


def connect(database_url: str) -> psycopg.Connection:
    """Open a connection. Prepared statements are off so Supabase's pooler works."""
    return psycopg.connect(database_url, row_factory=dict_row, prepare_threshold=None)
