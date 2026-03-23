from datetime import datetime, date, timedelta
import calendar
import logging
from typing import Dict, Any, List, Optional

from data.database_manager import DatabaseManager
from data.repositories.learner_repository import LearnerRepository
from data.repositories.payment_repository import PaymentRepository
from data.repositories.family_repository import FamilyRepository
from utils.statement_counter import get_next_statement_number
from utils.settings_manager import SettingsManager

# --- Helper functions moved from the legacy statement dialog module. ---
def _get_billing_month_year(d: date):
    """
    Returns the billing month and year for a given calendar date.
    Jan/Feb are treated as one billing period shown as Feb, and Nov/Dec as one
    billing period shown as Nov.
    """
    if d.month == 1:
        return 2, d.year
    if d.month == 12:
        return 11, d.year
    return d.month, d.year


def _format_billing_period_label(month: int, year: int) -> str:
    if month == 2:
        return f"Jan/Feb {year}"
    if month == 11:
        return f"Nov/Dec {year}"
    return f"{calendar.month_name[month]} {year}"

def _format_recipient_line(p1_title, p1_name, p1_surname, p2_title, p2_name, p2_surname, g_title, g_name, g_surname):
    """Formats the main recipient line using initials and surname."""
    p1_initial = f"{p1_name[0]}." if p1_name else ""
    p2_initial = f"{p2_name[0]}." if p2_name else ""
    g_initial = f"{g_name[0]}." if g_name else ""

    p1_formatted = f"{p1_title or ''} {p1_initial} {p1_surname or ''}".strip() if p1_initial else ""
    p2_formatted = f"{p2_title or ''} {p2_initial} {p2_surname or ''}".strip() if p2_initial else ""
    g_formatted = f"{g_title or ''} {g_initial} {g_surname or ''}".strip() if g_initial else ""

    if p1_formatted:
        if p2_formatted:
            # Check if surnames are the same (or p2 surname is missing)
            if not p2_surname or p1_surname == p2_surname:
                p1_part = f"{p1_title or ''} {p1_initial}".strip()
                p2_part = f"{p2_title or ''} {p2_initial}".strip()
                # Use p1's surname if p2's is missing or same
                surname_to_use = p1_surname or '' 
                return f"{p1_part} and {p2_part} {surname_to_use}".strip()
            else: # Different surnames
                return f"{p1_formatted} and {p2_formatted}"
        elif g_formatted:
            return f"{p1_formatted} (Parent) / {g_formatted} (Guardian)"
        else:
            return p1_formatted
    elif g_formatted:
        return f"{g_formatted} (Guardian)"
    else:
        if any([p1_name, p1_surname, p2_name, p2_surname, g_name, g_surname]):
             return "Account Holder"
        else:
             return "The Parent/Guardian"


def _format_recipient_role(p1_name, p2_name, g_name):
    """Formats the role description (Parent/Parents/Guardian)"""
    if p1_name or p2_name: # Check if *any* parent name exists
        if p1_name and p2_name:
            return "Parents of"
        else: # Only one parent name exists or only one parent entry provided
            return "Parent of"
    elif g_name:
        return "Guardian of"
    else:
        return "Parent/Guardian of"


class StatementDocumentService:
    def __init__(self, db_manager: DatabaseManager, learner_repository: LearnerRepository, 
                 payment_repository: PaymentRepository, family_repository: FamilyRepository):
        self.db_manager = db_manager
        self.learner_repository = learner_repository
        self.payment_repository = payment_repository
        self.family_repository = family_repository

    @staticmethod
    def _row_value(row: Any, key: str, default: Any = None) -> Any:
        if row is None:
            return default
        if isinstance(row, dict):
            return row.get(key, default)
        try:
            return row[key]
        except Exception:
            return default

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        text = str(value or "").strip()
        if not text:
            return date.today()

        for fmt, width in (("%Y-%m-%d", 10), ("%Y-%m-%d %H:%M:%S", 19)):
            try:
                return datetime.strptime(text[:width], fmt).date()
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(text.replace("T", " ")).date()
        except ValueError:
            return date.today()

    @staticmethod
    def _resolve_admission_fee(base_fee: Any, custom_enabled: Any, custom_amount: Any) -> float:
        if bool(custom_enabled) and custom_amount not in (None, ""):
            try:
                return float(custom_amount)
            except (TypeError, ValueError):
                pass
        try:
            return float(base_fee or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _get_semester_info(self, statement_date: date) -> Dict[str, Any]:
        """
        Determine the current semester based on the statement date and only
        include billing periods from the semester start up to the generated month.
        """
        current_month = statement_date.month

        if current_month <= 6:
            semester_name = "Semester 1"
            semester_months = [2] if current_month <= 2 else [2] + list(range(3, current_month + 1))
            semester_year = statement_date.year
        else:
            semester_name = "Semester 2"
            semester_end_month = 11 if current_month >= 11 else current_month
            semester_months = list(range(7, semester_end_month + 1))
            semester_year = statement_date.year

        return {
            "semester_name": semester_name,
            "semester_months": semester_months,
            "semester_year": semester_year
        }

    def _trim_semester_months_for_start(
        self,
        semester_months: List[int],
        semester_year: int,
        statement_date: date,
        visible_start_date: Optional[date],
    ) -> List[int]:
        if not visible_start_date:
            return semester_months

        start_billing_month, start_billing_year = _get_billing_month_year(visible_start_date)
        current_billing_month, current_billing_year = _get_billing_month_year(statement_date)

        if start_billing_year != semester_year or start_billing_year != current_billing_year:
            return semester_months

        trimmed_months = [month for month in semester_months if month >= start_billing_month and month <= current_billing_month]
        return trimmed_months or semester_months

    def _calculate_transactions_and_balance(
        self,
        raw_transactions: List[Dict[str, Any]],
        statement_date: date,
        visible_start_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Sorts raw transactions and calculates running balance, grouping by month
        and providing a balance brought forward for each month.
        Also calculates total charges and total payments for semester summary.
        Renders billing periods from the semester start up to the generated
        month, and starts from the learner/family billing start when that falls
        inside the current semester.
        """
        raw_transactions.sort(key=lambda t: (t['date'], 0 if t['type'] == 'charge' else 1))
        
        # Get semester info
        semester_info = self._get_semester_info(statement_date)
        semester_year = semester_info["semester_year"]
        semester_months = self._trim_semester_months_for_start(
            semester_info["semester_months"],
            semester_year,
            statement_date,
            visible_start_date,
        )
        
        monthly_summaries = []
        current_running_balance = 0.0
        total_charges = 0.0
        total_payments = 0.0
        balance_brought_forward_from_previous = 0.0

        # First, calculate balance from previous periods (for balance brought forward)
        for item in raw_transactions:
            item_month, item_year = _get_billing_month_year(item['date'])
            
            # Check if transaction is from a previous semester
            is_previous_semester = False
            if item_year < semester_year:
                is_previous_semester = True
            elif item_year == semester_year:
                if item_month not in semester_months:
                    is_previous_semester = True
            
            if is_previous_semester:
                item_amount = float(item.get('amount', 0.0))
                balance_brought_forward_from_previous += item_amount
        
        # Filter transactions for current semester only
        semester_transactions = []
        for item in raw_transactions:
            item_month, item_year = _get_billing_month_year(item['date'])
            
            # Include transaction if it's in the current semester
            if item_year == semester_year and item_month in semester_months:
                semester_transactions.append(item)

        # Group transactions by month
        transactions_by_month = {}
        for item in semester_transactions:
            billing_month, billing_year = _get_billing_month_year(item['date'])
            month_key = (billing_year, billing_month)
            if month_key not in transactions_by_month:
                transactions_by_month[month_key] = []
            transactions_by_month[month_key].append(item)

        # Start with balance brought forward from previous semester
        current_running_balance = balance_brought_forward_from_previous
        overall_balance_brought_forward = balance_brought_forward_from_previous

        semester_month_keys = [(semester_year, month_num) for month_num in semester_months]

        for i, month_key in enumerate(semester_month_keys):
            month_year = month_key[0]
            month_num = month_key[1]

            month_transactions = transactions_by_month.get(month_key, [])
            month_balance_brought_forward = current_running_balance

            month_processed_transactions = []
            for item in month_transactions:
                item_amount = float(item.get('amount', 0.0))
                current_running_balance += item_amount
                
                # Track total charges and payments for this semester
                if item['type'] == 'charge':
                    total_charges += item_amount
                else:
                    total_payments += abs(item_amount)

                date_obj = item['date']
                processed_item = {
                    'date_str': date_obj.strftime('%d/%m/%Y'),
                    'desc': item['desc'],
                    'charge_amt': item_amount if item['type'] == 'charge' else 0.0,
                    'payment_amt': abs(item_amount) if item['type'] == 'payment' else 0.0,
                    'running_balance': current_running_balance # Running balance up to this transaction
                }
                month_processed_transactions.append(processed_item)
            
            monthly_summaries.append({
                "month_year_str": _format_billing_period_label(month_num, month_year),
                "balance_brought_forward": month_balance_brought_forward,
                "balance_brought_forward_formatted": f"R {month_balance_brought_forward:,.2f}",
                "transactions": month_processed_transactions,
                "has_transactions": bool(month_processed_transactions),
                "closing_balance": current_running_balance,
                "closing_balance_formatted": f"R {current_running_balance:,.2f}"
            })

            if i == 0:
                overall_balance_brought_forward = month_balance_brought_forward

        final_amount_due = current_running_balance
        total_due_formatted = f"R {abs(final_amount_due):,.2f}"

        return {
            "monthly_summaries": monthly_summaries,
            "final_amount_due": final_amount_due,
            "total_due_formatted": total_due_formatted,
            "balance_brought_forward_overall": overall_balance_brought_forward,
            "total_charges": total_charges,
            "total_payments": total_payments,
            "semester_name": semester_info["semester_name"],
            "semester_year": semester_year
        }

    def _get_due_date_info(self, final_amount_due: float, current_monthly_fee: float, 
                          grace_period_days: int, due_day: int, scheduled_due_date: Optional[date] = None) -> Dict[str, Any]:
        """Calculates and formats due date information."""
        statement_now = datetime.now()
        statement_date = statement_now.date()
        statement_day = statement_now.day
        statement_month = statement_now.month
        statement_year = statement_now.year

        if scheduled_due_date is not None:
            base_due_date = scheduled_due_date
        else:
            due_date_month = statement_month
            due_date_year = statement_year

            if due_day <= statement_day:
                due_date_month += 1
                if due_date_month > 12:
                    due_date_month = 1
                    due_date_year += 1
            
            last_day_of_month = calendar.monthrange(due_date_year, due_date_month)[1]
            effective_due_day = min(due_day, last_day_of_month)

            base_due_date = date(due_date_year, due_date_month, effective_due_day)

        is_final_statement_period = statement_month in [11, 12]
        final_statement_due_date = date(statement_year, 11, 10)

        if final_amount_due > 0:
            if is_final_statement_period:
                due_date = final_statement_due_date
            else:
                due_date = base_due_date + timedelta(days=grace_period_days)
        else:
            due_date = base_due_date

        overdue_amount_class = ""
        amount_due_message = ""
        amount_due_class = ""
        due_date_notice = ""

        if final_amount_due > 0:
            if is_final_statement_period:
                amount_due_class = "amount-due"
                overdue_amount_class = "overdue-amount-red"
                if statement_date > due_date:
                    amount_due_message = "Overdue Amount"
                    due_date_notice = f"Final payment was due by {due_date.strftime('%d-%b-%Y')}"
                elif final_amount_due > current_monthly_fee:
                    amount_due_message = "Overdue Amount"
                    due_date_notice = f"Final payment due by {due_date.strftime('%d-%b-%Y')}"
                else:
                    amount_due_message = "Final Amount Due"
                    due_date_notice = f"Final payment due by {due_date.strftime('%d-%b-%Y')}"
            elif final_amount_due > 2 * current_monthly_fee:
                overdue_amount_class = "overdue-amount-red"
                amount_due_message = "Overdue Amount"
                amount_due_class = "amount-due"
                due_date_notice = f"Due by {due_date.strftime('%d-%b-%Y')}"
            elif final_amount_due > current_monthly_fee:
                overdue_amount_class = "overdue-amount-amber"
                amount_due_message = "Overdue Amount"
                amount_due_class = "amount-due"
                due_date_notice = f"Due by {due_date.strftime('%d-%b-%Y')}"
            else:
                amount_due_message = "Amount Due"
                amount_due_class = "amount-due"
                due_date_notice = f"Due by {due_date.strftime('%d-%b-%Y')}"
        elif final_amount_due < 0:
            amount_due_message = "Credit of"
            amount_due_class = "amount-credit"
        else:
            amount_due_message = "Account Up-to-Date"
            amount_due_class = "amount-uptodate"

        return {
            "statement_date_str": statement_date.strftime("%d-%b-%Y"),
            "due_date_str": due_date.strftime("%d-%b-%Y"),
            "due_date_notice": due_date_notice,
            "amount_due_message": amount_due_message,
            "amount_due_class": amount_due_class,
            "overdue_amount_class": overdue_amount_class,
            "billing_year": statement_year
        }


    def get_learner_statement_data(self, acc_no: str, current_username: str) -> Dict[str, Any]:
        """Prepares all data needed to render an individual learner statement."""
        settings = SettingsManager()
        grace_period_days = settings.get_system_setting("grace_period_days", 3)

        learner_details = self.learner_repository.get_learner_details_for_statement(acc_no)
        if not learner_details:
            logging.error(f"Could not fetch learner details for Acc No: {acc_no}.")
            return {}

        # Unpack learner details (using names for clarity)
        (acc_no_db, name, surname, grade, is_new_db, apply_adm, learner_payment_option,
         p1_title, p1_name, p1_surname,
         p2_title, p2_name, p2_surname,
         g_title, g_name, g_surname,
         adm_fee_from_db, skip_initial_fee_db, custom_admission_amount_enabled_db, custom_admission_amount_db) = learner_details
        
        apply_adm = bool(apply_adm)
        skip_initial_fee = bool(skip_initial_fee_db)

        statement_number = get_next_statement_number(self.db_manager, learner_id=acc_no)

        raw_transactions = []
        payment_history = self.learner_repository.get_learner_payment_history(acc_no)
        visible_start_date = None
        if payment_history:
            start_dates = [
                self._coerce_date(self._row_value(history_item, 'start_date'))
                for history_item in payment_history
                if self._row_value(history_item, 'start_date')
            ]
            if start_dates:
                visible_start_date = min(start_dates)

        for i, history_item in enumerate(payment_history):
            item_start_date = self._coerce_date(self._row_value(history_item, 'start_date'))
            item_end_raw = self._row_value(history_item, 'end_date')
            item_end_date = self._coerce_date(item_end_raw) if item_end_raw else date.today()
            monthly_fee_val = float(self._row_value(history_item, 'monthly_fee', 0.0) or 0.0)
            adm_reg_fee_val = self._resolve_admission_fee(
                adm_fee_from_db,
                custom_admission_amount_enabled_db,
                custom_admission_amount_db,
            )

            if i == 0: # First payment period
                # Admission Fee and First Installment
                if apply_adm:
                    if skip_initial_fee:
                        raw_transactions.append({
                            'date': item_start_date,
                            'type': 'charge',
                            'desc': f"Admission Fee - {item_start_date.strftime('%B %Y')}",
                            'amount': adm_reg_fee_val
                        })
                    else:
                        raw_transactions.append({
                            'date': item_start_date,
                            'type': 'charge',
                            'desc': f"Admission Fee + Installment Fee - {item_start_date.strftime('%B %Y')}",
                            'amount': adm_reg_fee_val + monthly_fee_val
                        })
                else: # No admission fee
                    if not skip_initial_fee:
                        raw_transactions.append({
                            'date': item_start_date,
                            'type': 'charge',
                            'desc': f"Installment Fee - {item_start_date.strftime('%B %Y')}",
                            'amount': monthly_fee_val
                        })
                
                # Set tracker for subsequent months
                current_date_tracker = item_start_date.replace(day=1) + timedelta(days=32) # Move to next month safely
                current_date_tracker = current_date_tracker.replace(day=1)

            else: # Subsequent payment periods, just start from its start_date
                current_date_tracker = item_start_date.replace(day=1)

            # Loop through the rest of the months for this payment period
            while current_date_tracker <= item_end_date:
                billing_month_name = current_date_tracker.strftime('%B %Y')
                
                # Default description for the installment fee
                desc = f"Installment Fee - {billing_month_name}"
                charge_date = current_date_tracker

                if current_date_tracker.month == 1: # January charge often covers Jan/Feb
                    desc = f"Installment Fee - Jan/Feb {current_date_tracker.year}"
                    charge_date = current_date_tracker.replace(month=2, day=1)
                elif current_date_tracker.month == 11: # November charge often covers Nov/Dec
                    desc = f"Last Installment Fee - Nov/Dec {current_date_tracker.year}"
                    charge_date = current_date_tracker.replace(month=11, day=1)

                if not (i == 0 and current_date_tracker == item_start_date):
                    raw_transactions.append({
                        'date': charge_date,
                        'type': 'charge',
                        'desc': desc,
                        'amount': monthly_fee_val
                    })
                
                # Move to the next month
                next_month = current_date_tracker.month + 1
                next_year = current_date_tracker.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                current_date_tracker = current_date_tracker.replace(year=next_year, month=next_month, day=1)

        # Process payments
        payments = self.payment_repository.get_payment_history_for_learner(acc_no)
        for pmt in payments:
            try:
                pmt_date_str = pmt.get('date')
                if pmt_date_str:
                    pmt_date = self._coerce_date(pmt_date_str)
                    try:
                        pmt_amount = float(pmt.get('amount', 0.0))
                        raw_transactions.append({
                            'date': pmt_date,
                            'type': 'payment',
                            'desc': "Payment Received",
                            'amount': -abs(pmt_amount)
                        })
                    except (ValueError, TypeError):
                        logging.warning(f"Invalid payment amount for {acc_no}: {pmt}")
            except Exception as e:
                logging.warning(f"Could not process payment record for {acc_no}: {e}")

        # Call the refactored _calculate_transactions_and_balance
        balance_data = self._calculate_transactions_and_balance(
            raw_transactions,
            datetime.now().date(),
            visible_start_date=visible_start_date,
        )
        monthly_summaries = balance_data['monthly_summaries']
        final_amount_due = balance_data['final_amount_due']
        total_due_formatted = balance_data['total_due_formatted']

        due_day = 1
        current_monthly_fee = float(self._row_value(payment_history[-1], 'monthly_fee', 0.0) or 0.0) if payment_history else 0.0

        try:
            fetched_day = int(self.payment_repository.get_due_day_for_learner(acc_no) or 1)
            if 1 <= fetched_day <= 31:
                due_day = fetched_day
        except (AttributeError, TypeError, ValueError):
            logging.warning(f"Invalid due day for {acc_no}")

        scheduled_due_date = None
        try:
            scheduled_due_date = self.payment_repository.get_next_scheduled_payment_date_for_learner(
                acc_no,
                reference_date=datetime.now().date(),
            )
        except AttributeError:
            scheduled_due_date = None

        due_date_info = self._get_due_date_info(
            final_amount_due,
            current_monthly_fee,
            grace_period_days,
            due_day,
            scheduled_due_date=scheduled_due_date,
        )

        payment_terms_display = ""
        active_term_id = self.payment_repository.get_active_term_for_learner(acc_no)
        if active_term_id is not None:
            active_term_name = self.payment_repository.get_term_name_by_id(active_term_id)
            if active_term_name:
                payment_terms_display = active_term_name

        # --- Semester Closing Balance Calculation ---
        stm_date = datetime.now().date()
        semester_info = self._get_semester_info(stm_date)
        sem_year = semester_info['semester_year']
        current_month = stm_date.month
        
        # Define full semester months for target calculation (5 months duration)
        if current_month <= 6:
            sem_months_full = [2, 3, 4, 5, 6]
        else:
            sem_months_full = [7, 8, 9, 10, 11]

        # Calculate Total Semester Obligation:
        # Sum of all charges already generated for this semester + projected future charges for this semester
        sem_total_obligation = 0.0
        charged_months = set()
        for tx in raw_transactions:
            if tx.get('type') == 'charge':
                tx_date = tx.get('date')
                if tx_date:
                    tx_m, tx_y = _get_billing_month_year(tx_date)
                    if tx_y == sem_year and tx_m in sem_months_full:
                        sem_total_obligation += float(tx.get('amount', 0.0))
                        charged_months.add(tx_m)
        
        # Add projected future charges for any month in the semester that hasn't been charged yet
        # AND is on or after the learner's start month (to handle mid-semester starters correctly)
        start_m, start_y = (0, 0)
        if visible_start_date:
            start_m, start_y = _get_billing_month_year(visible_start_date)

        missing_months_count = 0
        for m in sem_months_full:
            if m not in charged_months:
                # If they started before this year, or this year but before/on this month
                if sem_year > start_y or (sem_year == start_y and m >= start_m):
                    missing_months_count += 1
        
        sem_total_obligation += missing_months_count * current_monthly_fee
        
        # Payments: Sum of all payments in this semester
        sem_payments_total = 0.0
        for pmt in payments:
            try:
                pmt_date_str = pmt.get('date')
                if pmt_date_str:
                    pmt_date = self._coerce_date(pmt_date_str)
                    p_month, p_year = _get_billing_month_year(pmt_date)
                    if p_year == sem_year and p_month in sem_months_full:
                        sem_payments_total += float(pmt.get('amount', 0.0))
            except (ValueError, TypeError):
                continue
        
        sem_closing_balance = sem_total_obligation - sem_payments_total
        sem_closing_balance_formatted = f"R {sem_closing_balance:,.2f}"

        return {
            "statement_number": statement_number,
            "prepared_by_user": current_username or "System",
            "payment_terms_display": payment_terms_display,
            "semester_closing_balance": sem_closing_balance,
            "semester_closing_balance_formatted": sem_closing_balance_formatted,
            "recipient_line": _format_recipient_line(p1_title, p1_name, p1_surname, p2_title, p2_name, p2_surname, g_title, g_name, g_surname),
            "recipient_role": _format_recipient_role(p1_name, p2_name, g_name),
            "monthly_summaries": monthly_summaries, # Pass the new monthly summaries
            "final_amount_due": final_amount_due,
            "total_due_formatted": total_due_formatted,
            "payment_reference": f"{name} {surname} Gr{grade}",
            "is_family_statement": False,
            "discount_info": None,
            "learner_name": name,
            "learner_surname": surname,
            "learner_grade": grade,
            "learner_id_display": acc_no_db.split('-')[0] if acc_no_db and '-' in acc_no_db else acc_no,
            "total_charges": balance_data.get('total_charges', 0.0),
            "total_payments": balance_data.get('total_payments', 0.0),
            "semester_name": balance_data.get('semester_name', 'Semester 1'),
            "semester_year": balance_data.get('semester_year', datetime.now().year),
            "statement_period_label": f"{balance_data.get('semester_name', 'Semester 1')} {balance_data.get('semester_year', datetime.now().year)}",
            **due_date_info
        }

    def get_family_statement_data(self, family_id: int, current_username: str) -> Dict[str, Any]:
        """Prepares all data needed to render a family statement."""
        settings = SettingsManager()
        grace_period_days = settings.get_system_setting("grace_period_days", 3)
        statement_date = datetime.now().date()
        
        family_details = self.family_repository.get_family_and_learner_details_for_statement(family_id)
        if not family_details:
            logging.error(f"Could not fetch family details for Family ID: {family_id}.")
            return {}
            
        family_acc_no = family_details.get('account_no', f"FAM-{family_id}")
        payment_mode = family_details.get('payment_mode', 'individual_discount')
        p1_title = family_details.get('p1_title')
        p1_name = family_details.get('p1_name', 'N/A')
        p1_surname = family_details.get('p1_surname', '')
        p2_title = family_details.get('p2_title')
        p2_name = family_details.get('p2_name')
        p2_surname = family_details.get('p2_surname')
        g_title = family_details.get('g_title')
        g_name = family_details.get('g_name')
        g_surname = family_details.get('g_surname')
        learners_in_family = family_details.get('learners', [])

        statement_number = get_next_statement_number(self.db_manager, learner_id=family_acc_no)

        raw_transactions = []
        total_monthly_charges_for_family = 0.0
        visible_start_date = None

        # Retrieve statement settings
        bank_name = settings.get_statement_setting("bank_name", "N/A")
        account_holder = settings.get_statement_setting("account_holder", "N/A")
        account_number = settings.get_statement_setting("account_number", "N/A")
        statement_message = settings.get_statement_setting("statement_message", "")
        thank_you_message = settings.get_statement_setting("thank_you_message", "")
        email_contact = settings.get_statement_setting("email", "")
        email_contact = email_contact if email_contact else ""

        for learner in learners_in_family:
            acc_no = learner.get('acc_no')
            learner_payment_history = self.learner_repository.get_learner_payment_history(acc_no)
            learner_start_dates = [
                self._coerce_date(self._row_value(history_item, 'start_date'))
                for history_item in learner_payment_history
                if self._row_value(history_item, 'start_date')
            ]
            if learner_start_dates:
                learner_first_start = min(learner_start_dates)
                if visible_start_date is None or learner_first_start < visible_start_date:
                    visible_start_date = learner_first_start

            for i, history_item in enumerate(learner_payment_history):
                item_start_date = self._coerce_date(self._row_value(history_item, 'start_date'))
                item_end_raw = self._row_value(history_item, 'end_date')
                item_end_date = self._coerce_date(item_end_raw) if item_end_raw else date.today()
                monthly_fee_val = float(self._row_value(history_item, 'monthly_fee', 0.0) or 0.0)
                adm_reg_fee_val = self._resolve_admission_fee(
                    self._row_value(history_item, 'adm_reg_fee', 0.0),
                    self._row_value(history_item, 'custom_admission_amount_enabled', False),
                    self._row_value(history_item, 'custom_admission_amount'),
                )
                apply_adm = bool(self._row_value(history_item, 'apply_admission_fee', False))
                skip_initial_fee = bool(self._row_value(history_item, 'skip_initial_fee', False))

                if i == 0:
                    # Admission Fee and First Installment
                    if apply_adm:
                        if skip_initial_fee:
                            raw_transactions.append({
                                'date': item_start_date,
                                'type': 'charge',
                                'desc': f"Admission Fee ({learner.get('name', '')}) - {item_start_date.strftime('%B %Y')}",
                                'amount': adm_reg_fee_val,
                                'learner_acc_no': acc_no
                            })
                        else:
                            raw_transactions.append({
                                'date': item_start_date,
                                'type': 'charge',
                                'desc': f"Admission Fee + Installment Fee ({learner.get('name', '')}) - {item_start_date.strftime('%B %Y')}",
                                'amount': adm_reg_fee_val + monthly_fee_val,
                                'learner_acc_no': acc_no
                            })
                    else:
                        if not skip_initial_fee:
                            raw_transactions.append({
                                'date': item_start_date,
                                'type': 'charge',
                                'desc': f"Installment Fee ({learner.get('name', '')}) - {item_start_date.strftime('%B %Y')}",
                                'amount': monthly_fee_val,
                                'learner_acc_no': acc_no
                            })
                    
                    current_date_tracker = item_start_date.replace(day=1) + timedelta(days=32)
                    current_date_tracker = current_date_tracker.replace(day=1)

                else:
                    current_date_tracker = item_start_date.replace(day=1)

                while current_date_tracker <= item_end_date:
                    billing_month_name = current_date_tracker.strftime('%B %Y')
                    
                    desc = f"Installment Fee ({learner.get('name', '')}) - {billing_month_name}"
                    charge_date = current_date_tracker

                    if current_date_tracker.month == 1:
                        desc = f"Installment Fee ({learner.get('name', '')}) - Jan/Feb {current_date_tracker.year}"
                        charge_date = current_date_tracker.replace(month=2, day=1)
                    elif current_date_tracker.month == 11:
                        desc = f"Last Installment Fee ({learner.get('name', '')}) - Nov/Dec {current_date_tracker.year}"
                        charge_date = current_date_tracker.replace(month=11, day=1)

                    if not (i == 0 and current_date_tracker == item_start_date):
                        raw_transactions.append({
                            'date': charge_date,
                            'type': 'charge',
                            'desc': desc,
                            'amount': monthly_fee_val,
                            'learner_acc_no': acc_no
                        })
                    
                    next_month = current_date_tracker.month + 1
                    next_year = current_date_tracker.year
                    if next_month > 12:
                        next_month = 1
                        next_year += 1
                    current_date_tracker = current_date_tracker.replace(year=next_year, month=next_month, day=1)
            
            # Aggregate monthly fees for family (for amount due message calculation)
            learner_monthly_fee_for_comparison = self.payment_repository.get_monthly_fee_for_statement(acc_no)
            total_monthly_charges_for_family += learner_monthly_fee_for_comparison


        # Process family payments
        family_payments = self.payment_repository.get_payment_history_for_family(family_id)
        for pmt in family_payments:
            try:
                pmt_date_str = pmt.get('date')
                if pmt_date_str:
                    pmt_date = self._coerce_date(pmt_date_str)
                    try:
                        pmt_amount = float(pmt.get('amount', 0.0))
                        raw_transactions.append({
                            'date': pmt_date,
                            'type': 'payment',
                            'desc': "Payment Received (Family)",
                            'amount': -abs(pmt_amount)
                        })
                    except (ValueError, TypeError):
                        logging.warning(f"Invalid family payment amount for {family_id}: {pmt}")
            except Exception as e:
                logging.warning(f"Could not process family payment record for {family_id}: {e}")

        balance_data = self._calculate_transactions_and_balance(
            raw_transactions,
            statement_date,
            visible_start_date=visible_start_date,
        )
        monthly_summaries = balance_data['monthly_summaries']
        final_amount_due = balance_data['final_amount_due']
        total_due_formatted = balance_data['total_due_formatted']
        
        # Determine due day for the family
        due_day = int(self.family_repository.get_family_due_day(family_id) or 1)
        scheduled_due_date = None
        try:
            scheduled_due_date = self.family_repository.get_family_next_scheduled_payment_date(
                family_id,
                reference_date=statement_date,
            )
        except AttributeError:
            scheduled_due_date = None

        due_date_info = self._get_due_date_info(
            final_amount_due,
            total_monthly_charges_for_family,
            grace_period_days,
            due_day,
            scheduled_due_date=scheduled_due_date,
        )

        # --- Family Semester Closing Balance Calculation ---
        stm_date = datetime.now().date()
        semester_info = self._get_semester_info(stm_date)
        sem_year = semester_info['semester_year']
        current_month = stm_date.month
        
        if current_month <= 6:
            sem_months_full = [2, 3, 4, 5, 6]
        else:
            sem_months_full = [7, 8, 9, 10, 11]

        # Calculate Total Family Semester Obligation
        # We sum up (Already Charged in semester) + (Remaining months obligation per learner)
        sem_total_obligation = 0.0
        
        # 1. Sum existing charges in this semester
        learner_charged_months = {} # acc_no -> set of months
        for tx in raw_transactions:
            if tx.get('type') == 'charge':
                tx_date = tx.get('date')
                l_acc = tx.get('learner_acc_no')
                if tx_date:
                    tx_m, tx_y = _get_billing_month_year(tx_date)
                    if tx_y == sem_year and tx_m in sem_months_full:
                        sem_total_obligation += float(tx.get('amount', 0.0))
                        if l_acc:
                            if l_acc not in learner_charged_months: learner_charged_months[l_acc] = set()
                            learner_charged_months[l_acc].add(tx_m)
        
        # 2. Add projected future charges per learner based on their start date
        for learner in learners_in_family:
            l_acc = learner.get('acc_no')
            l_monthly_fee = self.payment_repository.get_monthly_fee_for_statement(l_acc)
            
            # Determine this learner's start date
            l_start_date = None
            l_history = self.learner_repository.get_learner_payment_history(l_acc)
            if l_history:
                l_starts = [self._coerce_date(self._row_value(h, 'start_date')) for h in l_history if self._row_value(h, 'start_date')]
                if l_starts: l_start_date = min(l_starts)
            
            if not l_start_date: continue
            l_start_m, l_start_y = _get_billing_month_year(l_start_date)
            
            l_charged = learner_charged_months.get(l_acc, set())
            
            l_missing_count = 0
            for m in sem_months_full:
                if m not in l_charged:
                    # If they started before this year, or this year but before/on this month
                    if sem_year > l_start_y or (sem_year == l_start_y and m >= l_start_m):
                        l_missing_count += 1
            
            sem_total_obligation += l_missing_count * l_monthly_fee
        
        sem_payments_total = 0.0
        for pmt in family_payments:
            try:
                pmt_date_str = pmt.get('date')
                if pmt_date_str:
                    pmt_date = self._coerce_date(pmt_date_str)
                    p_month, p_year = _get_billing_month_year(pmt_date)
                    if p_year == sem_year and p_month in sem_months_full:
                        sem_payments_total += float(pmt.get('amount', 0.0))
            except (ValueError, TypeError):
                continue
        
        sem_closing_balance = sem_total_obligation - sem_payments_total
        sem_closing_balance_formatted = f"R {sem_closing_balance:,.2f}"

        learner_list_display = ', '.join([f'{s.get("name", "N/A")} {s.get("surname", "")} Gr {s.get("grade", "?")}' for s in learners_in_family]) if learners_in_family else 'N/A'

        return {
            "statement_number": statement_number,
            "prepared_by_user": current_username or "System",
            "payment_terms_display": f"Family Account ({payment_mode.replace('_', ' ').title()})",
            "semester_closing_balance": sem_closing_balance,
            "semester_closing_balance_formatted": sem_closing_balance_formatted,
            "recipient_line": _format_recipient_line(p1_title, p1_name, p1_surname, p2_title, p2_name, p2_surname, g_title, g_name, g_surname),
            "recipient_role": _format_recipient_role(p1_name, p2_name, g_name),
            "monthly_summaries": monthly_summaries, # Pass the new monthly summaries
            "final_amount_due": final_amount_due,
            "amount_due_class": due_date_info["amount_due_class"], # Use from due_date_info
            "amount_due_message": due_date_info["amount_due_message"], # Use from due_date_info
            "total_due_formatted": total_due_formatted,
            "overdue_amount_class": due_date_info["overdue_amount_class"], # Use from due_date_info
            "bank_name": bank_name,
            "account_holder": account_holder,
            "account_number": account_number,
            "payment_reference": f"Family {family_acc_no}",
            "statement_message": statement_message,
            "email_contact": email_contact,
            "thank_you_message": thank_you_message,
            "is_family_statement": True,
            "family_acc_no": family_acc_no,
            "learner_list_display": learner_list_display,
            "total_charges": balance_data.get('total_charges', 0.0),
            "total_payments": balance_data.get('total_payments', 0.0),
            "semester_name": balance_data.get('semester_name', 'Semester 1'),
            "semester_year": balance_data.get('semester_year', datetime.now().year),
            "statement_period_label": f"{balance_data.get('semester_name', 'Semester 1')} {balance_data.get('semester_year', datetime.now().year)}",
            **due_date_info
        }
