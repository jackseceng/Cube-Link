"""Turso query and connection management module"""

import logging
from datetime import datetime, timezone
from os import environ
from re import IGNORECASE, search

import turso.sync
from dotenv import load_dotenv

load_dotenv()

url = environ["ENDPOINT"]
auth_token = environ["TOKEN"]
DB_PATH = "/tmp/urls.db"


def _create_connection():
    """Creates and returns a new database connection."""
    try:
        conn = turso.sync.connect(DB_PATH, remote_url=url, auth_token=auth_token)
        conn.pull()
        return conn
    except Exception as e:
        logging.error("Failed to create database connection or pull replica: %s", e)
        raise


def _coerce_blob(value, field_name: str) -> bytes:
    """Coerce a database BLOB value to bytes.

    pyturso may return BLOB columns as bytes, memoryview, or (in some driver
    versions) a base64-encoded string.  Stringifying an arbitrary object with
    ``bytes(str(obj), 'utf-8')`` produces garbage such as ``b'<memory at
    0x…>'``, which silently corrupts Fernet decryption.  This helper handles
    all known return types safely.
    """
    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        logging.debug("BLOB field '%s' returned as memoryview — converting", field_name)
        return bytes(value)
    if isinstance(value, bytearray):
        logging.debug("BLOB field '%s' returned as bytearray — converting", field_name)
        return bytes(value)
    if isinstance(value, str):
        # Some driver versions return BLOBs as base64 strings.
        logging.warning(
            "BLOB field '%s' returned as str — attempting base64 decode. "
            "Raw value (first 60 chars): %.60r",
            field_name,
            value,
        )
        try:
            import base64 as _base64

            return _base64.b64decode(value)
        except Exception as decode_err:
            logging.error(
                "BLOB field '%s': base64 decode failed (%s). "
                "Falling back to raw UTF-8 encoding — decryption will likely fail.",
                field_name,
                decode_err,
            )
            return value.encode("utf-8")
    logging.error(
        "BLOB field '%s' has unexpected type %s — coercion may be incorrect.",
        field_name,
        type(value).__name__,
    )
    return bytes(value)


def get_link(hashsum: str):
    """Get entries that match provided path, return output string or bool False if fail"""
    conn = _create_connection()
    try:
        result_set = conn.execute(
            "SELECT url, salt FROM urls WHERE hashsum = ?", (hashsum,)
        )
        row = result_set.fetchone()

        if row:
            logging.debug(
                "get_link raw types — url: %s, salt: %s",
                type(row[0]).__name__,
                type(row[1]).__name__,
            )
            url_data = _coerce_blob(row[0], "url")
            salt_data = _coerce_blob(row[1], "salt")
            return url_data, salt_data
        logging.info("get_link: no row found for hashsum %s", hashsum)
        return False, False
    except Exception as e:
        logging.error("Error on get_link: %s", e)
        return False, False
    finally:
        if conn:
            conn.close()


def insert_link(hashsum: str, url: bytes, salt: bytes):
    """Insert an entry under the specified path, return bool outcome"""
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
        # Match case-insensitively — the driver may return the column name in
        # any case (e.g. "urls.HASHSUM" vs "urls.hashsum").
        if search(r"UNIQUE constraint failed: urls\.hashsum", str(e), IGNORECASE):
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
