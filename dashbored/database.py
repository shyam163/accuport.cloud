"""
Database connection management for Accuport Dashboard
- accubase.sqlite: READ-ONLY (vessel data) / READ-WRITE (admin operations)
- users.sqlite: READ-WRITE (user management)
"""
import sqlite3
from contextlib import contextmanager

# Database file paths
ACCUBASE_DB = 'accubase.sqlite'
USERS_DB = 'users.sqlite'

@contextmanager
def get_accubase_connection():
    """
    Get READ-ONLY connection to accubase.sqlite
    This database contains vessel measurements and should never be modified
    """
    conn = sqlite3.connect(f'file:{ACCUBASE_DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_accubase_write_connection():
    """
    Get READ-WRITE connection to accubase.sqlite
    This is used ONLY for admin operations (creating vessels)
    Regular queries should use get_accubase_connection() which is read-only
    """
    conn = sqlite3.connect(ACCUBASE_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_users_connection():
    """
    Get READ-WRITE connection to users.sqlite
    This database contains user authentication and authorization data
    """
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def dict_from_row(row):
    """Convert sqlite3.Row to dictionary"""
    if row is None:
        return None
    return dict(zip(row.keys(), row))

def list_from_rows(rows):
    """Convert list of sqlite3.Row to list of dictionaries"""
    return [dict_from_row(row) for row in rows]
