"""SQLite storage bootstrap and connection helpers."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import sqlite3

from models import SCHEMA_STATEMENTS


@contextmanager
def with_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with with_db(db_path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
