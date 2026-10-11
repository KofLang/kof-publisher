#!/usr/bin/env python3
"""Build a LEGACY publisher database (schema from BEFORE publication.topic_id).

Usage: make_legacy_db.py <path-to-db>

This exists so the migration test can produce a genuinely old database: the Kof
`Store` only ever creates the CURRENT schema, so a legacy file cannot be made
from Kof itself. The schema below is the historical one — 16 columns, no
topic_id — plus one real row, so the test can prove the migration adds the
column IN PLACE without losing history.

TEST FIXTURE ONLY.
"""
import sqlite3
import sys

LEGACY_DDL = """
CREATE TABLE publication (
    id VARCHAR(255) PRIMARY KEY,
    company VARCHAR(255),
    topic VARCHAR(255),
    content TEXT,
    status VARCHAR(255),
    created_at VARCHAR(255),
    scheduled_at VARCHAR(255),
    published_at VARCHAR(255),
    target VARCHAR(255),
    model VARCHAR(255),
    context_version VARCHAR(255),
    recurrence_id VARCHAR(255),
    external_id VARCHAR(255),
    error TEXT,
    occurrence_key VARCHAR(255),
    attempts INTEGER
)
"""


def main():
    path = sys.argv[1]
    conn = sqlite3.connect(path)
    conn.execute(LEGACY_DDL)
    conn.execute(
        "INSERT INTO publication VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "pub-legacy",
            "Mel Santos",
            "tema antigo",
            "texto antigo publicado antes da migracao",
            "published",
            "2026-01-01T06:00:00-03:00",
            "",
            "2026-01-01T06:00:00-03:00",
            "linkedin",
            "modelo-antigo",
            "digest-antigo",
            "",
            "ext-legacy",
            "",
            "pub-legacy",
            1,
        ),
    )
    conn.commit()
    conn.close()
    print("ok")


if __name__ == "__main__":
    main()
