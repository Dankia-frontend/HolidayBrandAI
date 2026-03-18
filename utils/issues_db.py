# Issues Database Helpers
import mysql.connector
from config.config import db_config
from .logger import get_logger

log = get_logger("IssuesDB")


def create_issue(
    issue_title: str,
    issue_description: str,
    location_id: str,
    park_name: str,
    date: str,
):
    """
    Create a new issue entry.
    Returns: dict with id and all fields of the created issue, or None on failure.
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        query = """
            INSERT INTO issues (issue_title, issue_description, location_id, park_name, date)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(
            query,
            (issue_title, issue_description, location_id, park_name, date),
        )
        issue_id = cursor.lastrowid
        conn.commit()

        cursor.execute(
            """
            SELECT id, issue_title, issue_description, location_id, park_name, date
            FROM issues
            WHERE id = %s
            """,
            (issue_id,),
        )
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        log.exception(f"Error creating issue: {e}")
        if conn is not None:
            conn.close()
        return None


def get_all_issues():
    """
    Retrieve all issues.
    Returns: list of dicts with issue data.
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, issue_title, issue_description, location_id, park_name, date
        FROM issues
        ORDER BY id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_issue(issue_id: int):
    """
    Retrieve an issue by id.
    Returns: dict with issue data or None if not found.
    """
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, issue_title, issue_description, location_id, park_name, date
        FROM issues
        WHERE id = %s
        """,
        (issue_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row
