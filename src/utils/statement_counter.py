import logging
from datetime import datetime
from data.database_manager import DatabaseManager


def _table_columns(cursor, table_name: str) -> set[str]:
    inspection_queries = (
        (f"PRAGMA table_info({table_name})", "name", 1),
        (f"SHOW COLUMNS FROM {table_name}", "Field", 0),
    )
    last_error = None

    for query, key, index in inspection_queries:
        try:
            cursor.execute(query)
            columns = {
                str(_row_value(row, key, index, "") or "")
                for row in (cursor.fetchall() or [])
                if str(_row_value(row, key, index, "") or "")
            }
            if columns:
                return columns
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return set()


def _ensure_statement_counter_table(cursor) -> set[str]:
    try:
        columns = _table_columns(cursor, "statement_counters")
        if columns:
            return columns
    except Exception:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS statement_counters (
            learner_id VARCHAR(64) PRIMARY KEY,
            current_statement_month_year VARCHAR(16),
            number_for_current_month INTEGER,
            next_global_sequence_for_learner INTEGER,
            year_count INTEGER,
            last_statement_year INTEGER,
            last_statement_period INTEGER
        )
        """
    )
    return _table_columns(cursor, "statement_counters")


def _resolve_sequence_column(columns: set[str]) -> str:
    if "next_global_sequence_for_learner" in columns:
        return "next_global_sequence_for_learner"
    if "next_global_sequence_for_student" in columns:
        return "next_global_sequence_for_student"
    return "next_global_sequence_for_learner"

def _get_billing_period() -> tuple:
    """
    Determines the current billing period number (1-10) and year based on the date.
    NEW SEMESTER STRUCTURE:
    Semester 1 (Jan-Jun): Periods 1-4
        - Jan-Feb = Period 1 (combined)
        - Mar = Period 2
        - Apr = Period 3
        - May = Period 4
        - Jun = Break (uses Period 4)
    Semester 2 (Jul-Dec): Periods 6-10
        - Jul = Period 6
        - Aug = Period 7
        - Sep = Period 8
        - Oct = Period 9
        - Nov = Period 10
        - Dec = Break (uses Period 10)
    
    Returns a tuple of (period_number, year, is_new_year_started)
    """
    now = datetime.now()
    month = now.month

    is_new_year = (month == 1)

    # Semester 1: Jan-Jun -> Periods 1-4 (Jan-Feb combined as Period 1)
    if month == 1 or month == 2:  # Jan-Feb combined as Period 1
        return 1, now.year, is_new_year
    elif month == 3:  # Mar as Period 2
        return 2, now.year, False
    elif month == 4:  # Apr as Period 3
        return 3, now.year, False
    elif month == 5:  # May as Period 4
        return 4, now.year, False
    elif month == 6:  # June break, use Period 4
        return 4, now.year, False

    # Semester 2: Jul-Dec -> Periods 6-10
    elif month == 7:  # Jul as Period 6
        return 6, now.year, False
    elif month == 8:  # Aug as Period 7
        return 7, now.year, False
    elif month == 9:  # Sep as Period 8
        return 8, now.year, False
    elif month == 10:  # Oct as Period 9
        return 9, now.year, False
    elif month == 11:  # Nov as Period 10
        return 10, now.year, False
    elif month == 12:  # Dec break, use Period 10
        return 10, now.year, False

    # This should not be reached for a valid month.
    return 0, now.year, False

def _row_value(row, key: str, index: int, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[index]
    except Exception:
        return default


def _positive_int(value, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _derive_next_sequence(row) -> int:
    """Derive the next unique per-account statement sequence from legacy rows."""
    stored_next_sequence = _positive_int(
        _row_value(row, "next_global_sequence_for_learner", 3),
        default=0,
    )
    if stored_next_sequence:
        return stored_next_sequence

    legacy_year_count = _positive_int(_row_value(row, "year_count", 4), default=1)
    legacy_period = _positive_int(_row_value(row, "last_statement_period", 6), default=0)
    legacy_statement_number = ((legacy_year_count - 1) * 10) + legacy_period
    if legacy_statement_number > 0:
        return legacy_statement_number + 1

    return 1

def get_next_statement_number(db_manager: DatabaseManager, learner_id: str) -> str:
    """
    Gets the statement number for a specific learner or family account.
    The number stays fixed for the current calendar month and only advances
    when a new month starts for that account.
    """
    if not learner_id:
        logging.error("Learner ID cannot be empty when getting next statement number.")
        raise ValueError("Learner ID must be provided.")

    now = datetime.now()
    period, year, _ = _get_billing_period()
    current_month_year = now.strftime("%Y%m")

    with db_manager.get_connection() as conn:
        c = conn.cursor()
        columns = _ensure_statement_counter_table(c)
        sequence_column = _resolve_sequence_column(columns)

        c.execute("SELECT * FROM statement_counters WHERE learner_id = ?", (learner_id,))
        learner_info = c.fetchone()

        if learner_info is None:
            statement_number = 1
            current_month_count = 1
            c.execute(
                """
                INSERT INTO statement_counters (
                    learner_id,
                    current_statement_month_year,
                    number_for_current_month,
                    {sequence_column},
                    year_count,
                    last_statement_year,
                    last_statement_period
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """.format(sequence_column=sequence_column),
                (learner_id, current_month_year, current_month_count, 2, 1, year, period),
            )
        else:
            previous_month_year = str(
                _row_value(learner_info, "current_statement_month_year", 1, "")
                or ""
            )
            next_sequence = _derive_next_sequence(learner_info)

            if previous_month_year == current_month_year:
                statement_number = max(1, next_sequence - 1)
            else:
                statement_number = next_sequence
                current_month_count = 1
                c.execute(
                    """
                    UPDATE statement_counters
                    SET current_statement_month_year = ?,
                        number_for_current_month = ?,
                        {sequence_column} = ?,
                        last_statement_year = ?,
                        last_statement_period = ?
                    WHERE learner_id = ?
                    """.format(sequence_column=sequence_column),
                    (current_month_year, current_month_count, statement_number + 1, year, period, learner_id),
                )

    logging.info(
        "Using statement number %03d for account %s in %s.",
        statement_number,
        learner_id,
        current_month_year,
    )
    return f"{statement_number:03d}"
