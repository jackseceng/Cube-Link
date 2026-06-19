"""Turso query and connection management module"""

import logging
from datetime import datetime, timezone
from os import environ
from re import search

import turso.sync
from dotenv import load_dotenv

load_dotenv()

url = environ["ENDPOINT"]
auth_token = environ["TOKEN"]
DB_PATH = "/tmp/urls.db"


def _create_connection():
    """Creates and returns a new database connection."""
    conn = turso.sync.connect(DB_PATH, remote_url=url, auth_token=auth_token)
    conn.pull()
    return conn


def get_link(hashsum: str):
    """Get entries that match provided path, return output string or bool False if fail"""
    conn = _create_connection()
    try:
        result_set = conn.execute(
            "SELECT url, salt FROM urls WHERE hashsum = ?", (hashsum,)
        )
        row = result_set.fetchone()

        if row:
            # Ensure data is returned as bytes, adjust if your schema stores them differently
            url_data = (
                row[0] if isinstance(row[0], bytes) else bytes(str(row[0]), "utf-8")
            )
            salt_data = (
                row[1] if isinstance(row[1], bytes) else bytes(str(row[1]), "utf-8")
            )
            return url_data, salt_data
        return False, False
    except Exception as e:  # Use specific or general exception
        logging.error("Error on get_link: %s", e)
        return False, False
    finally:
        if conn:
            conn.close()


def insert_link(hashsum: str, url: bytes, salt: bytes):
    """Insert an entry under the specified path, return bool outcome"""
    unique_error = "UNIQUE constraint failed: urls.HASHSUM"
    conn = _create_connection()
    try:
        # Insert entry
        lastclick = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO urls(hashsum, url, salt, clicks, lastclick) VALUES (?, ?, ?, 0, ?);",
            (hashsum, url, salt, lastclick),
        )
        conn.commit()
        return True, None
    except Exception as e:  # Changed from Error to a more general Exception
        if search(unique_error, str(e)):
            logging.warning("Entry already exists: %s", e)
            return False, "non-unique"
        logging.error("Error on insert_link: %s", e)
        return False, str(e)
    finally:
        if conn:
            conn.close()


def increment_click(hashsum: str):
    """Increment the click count and update the last click timestamp for a given link"""
    conn = _create_connection()
    try:
        lastclick = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE urls SET clicks = clicks + 1, lastclick = ? WHERE hashsum = ?",
            (lastclick, hashsum),
        )
        conn.commit()
        return True, None
    except Exception as e:
        logging.error("Error on increment_click: %s", e)
        return False, str(e)
    finally:
        if conn:
            conn.close()


def get_stats(hashsum: str):
    """Get click count and last click time for a given link"""
    conn = _create_connection()
    try:
        result_set = conn.execute(
            "SELECT clicks, lastclick FROM urls WHERE hashsum = ?", (hashsum,)
        )
        row = result_set.fetchone()

        if row:
            clicks = row[0]
            lastclick = row[1]
            return clicks, lastclick
        return None, None
    except Exception as e:
        logging.error("Error on get_stats: %s", e)
        return None, None
    finally:
        if conn:
            conn.close()
