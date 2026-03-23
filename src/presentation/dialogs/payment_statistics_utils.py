import calendar
from datetime import datetime


ACTIVE_LEARNERS_COUNT_QUERY = "SELECT COUNT(*) FROM Learners WHERE is_active = 1"
MONTHLY_COLLECTED_TOTAL_QUERY = (
    "SELECT COALESCE(SUM(amount), 0) as total_collected "
    "FROM Payments "
    "WHERE strftime('%Y-%m', date) = ? AND payment_type = 'tuition'"
)
PROJECTED_TOTAL_QUERY = """
    WITH ActiveLearners AS (
        SELECT DISTINCT s.acc_no, s.payment_option, s.subjects_count, s.grade, s.family_id, f.payment_mode, f.discount_percentage
        FROM Learners s
        JOIN LearnerPayments sp ON s.acc_no = sp.learner_id
        LEFT JOIN Families f ON s.family_id = f.family_id
        WHERE s.is_active = 1 AND sp.start_date <= ? AND (sp.end_date IS NULL OR sp.end_date >= ?)
    )
    SELECT COALESCE(
        SUM(
            CASE
                WHEN a.payment_mode = 'single_coverage' THEN (
                    SELECT MAX(po2.monthly_fee)
                    FROM ActiveLearners a2
                    JOIN PaymentOptions po2 ON a2.payment_option = po2.option_name
                        AND a2.subjects_count = po2.subjects_count
                        AND a2.grade = po.grade
                    WHERE a2.family_id = a.family_id
                )
                ELSE po.monthly_fee * (1 - COALESCE(a.discount_percentage, 0)/100.0)
            END
        ),
        0
    ) as total_projected
    FROM ActiveLearners a
    LEFT JOIN PaymentOptions po
        ON a.payment_option = po.option_name
        AND a.subjects_count = po.subjects_count
        AND a.grade = po.grade
"""

ACTIVE_LEARNERS_FOR_MONTH_QUERY = """
    SELECT s.acc_no, s.name, s.surname, s.family_id, s.grade,
           COALESCE(po.monthly_fee, 0) as base_fee,
           COALESCE(f.discount_percentage, 0) as discount_percentage,
           COALESCE(f.payment_mode, 'individual') as payment_mode
    FROM Learners s
    JOIN LearnerPayments sp ON s.acc_no = sp.learner_id
    LEFT JOIN Families f ON s.family_id = f.family_id
    LEFT JOIN PaymentOptions po ON s.payment_option = po.option_name AND s.subjects_count = po.subjects_count AND s.grade = po.grade
    WHERE s.is_active = 1 AND sp.start_date <= ? AND (sp.end_date IS NULL OR sp.end_date >= ?)
"""

PAYMENTS_BY_LEARNER_QUERY = """
    SELECT learner_id, COALESCE(SUM(amount),0)
    FROM Payments
    WHERE payment_type = 'tuition' AND strftime('%Y-%m', date) = ?
    GROUP BY learner_id
"""

PAYMENTS_BY_FAMILY_QUERY = """
    SELECT COALESCE(s.family_id, '') as family_id, COALESCE(SUM(p.amount),0)
    FROM Payments p
    JOIN Learners s ON p.learner_id = s.acc_no
    WHERE p.payment_type = 'tuition' AND strftime('%Y-%m', p.date) = ?
    GROUP BY s.family_id
"""

LAST_PAYMENT_BY_LEARNER_QUERY = """
    SELECT learner_id, MAX(date) as last_payment_date
    FROM Payments
    WHERE payment_type = 'tuition'
    GROUP BY learner_id
"""


def iter_recent_months(selected_year, selected_month, months=12):
    for i in range(months - 1, -1, -1):
        month = selected_month - i
        year = selected_year
        if month <= 0:
            month += 12
            year -= 1
        month_key = f"{year}-{month:02d}"
        month_label = f"{calendar.month_name[month]} {year}"
        yield year, month, month_key, month_label


def month_bounds(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def previous_month(year, month):
    if month > 1:
        return year, month - 1
    return year - 1, 12


def format_last_payment_date(value):
    if not value or value == "N/A":
        return "N/A"
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return value


def parse_min_due_amount(raw_text):
    if not raw_text:
        return 0.0
    try:
        clean_text = raw_text.replace("R", "").replace(",", "").strip()
        return float(clean_text)
    except ValueError:
        return 0.0
