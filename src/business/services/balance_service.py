from datetime import date, datetime
from typing import Optional, List, Dict, Any

class BalanceService:

    def get_billing_period(self, today: date) -> (int, int):
        billing_year = today.year
        if today.month in [12, 1]:  # December or January
            billing_year -= 1

        current_month_num = today.month
        if current_month_num > 11:  # December
            current_month_num = 11
        elif current_month_num == 1:  # January
            current_month_num = 11
        
        return billing_year, current_month_num

    def calculate_family_balance(
        self,
        family_info: Dict[str, Any],
        learners_data: List[Dict[str, Any]],
        family_payments: float,
        today: date
    ) -> float:
        total_charges = 0.0
        billing_year, current_month_num = self.get_billing_period(today)

        payment_mode = family_info.get('payment_mode', 'individual_discount')
        family_discount_percent = float(family_info.get('discount_percentage', 0.0) or 0.0)
        family_discount_multiplier = (100.0 - family_discount_percent) / 100.0

        for i, learner_data in enumerate(learners_data):
            is_new = learner_data.get('is_new_learner')
            apply_adm = learner_data.get('apply_admission_fee')
            adm_fee_db = learner_data.get('adm_reg_fee')
            monthly_fee_db = learner_data.get('monthly_fee')
            start_date_str = learner_data.get('start_date')

            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date(billing_year, 2, 1)
            except (ValueError, TypeError):
                start_date = date(billing_year, 2, 1)

            # Admission Fee
            raw_adm_fee = float(adm_fee_db or 0.0)
            adm_fee = 0.0
            if is_new and apply_adm and raw_adm_fee > 0:
                if payment_mode == 'single_coverage':
                    adm_fee = raw_adm_fee if i == 0 else 0.0
                else:
                    adm_fee = raw_adm_fee * family_discount_multiplier
            total_charges += adm_fee

            # Monthly Fees
            raw_monthly_fee = float(monthly_fee_db or 0.0)
            monthly_fee = 0.0
            if raw_monthly_fee > 0:
                if payment_mode == 'single_coverage':
                    monthly_fee = raw_monthly_fee if i == 0 else 0.0
                else:
                    monthly_fee = raw_monthly_fee * family_discount_multiplier

                if monthly_fee > 0:
                    start_month = max(start_date.month, 2)
                    end_month = min(current_month_num, 11)
                    
                    for month_num in range(start_month, end_month + 1):
                        total_charges += monthly_fee
        
        return total_charges - family_payments

    def calculate_learner_balance(
        self,
        learner_info: Dict[str, Any],
        learner_payments: float,
        term_discount_percentage: float,
        today: date
    ) -> float:
        total_charges = 0.0
        billing_year, current_month_num = self.get_billing_period(today)

        is_new = learner_info.get('is_new_learner')
        apply_adm = learner_info.get('apply_admission_fee')
        adm_fee_db = learner_info.get('adm_reg_fee')
        monthly_fee_db = learner_info.get('monthly_fee')
        start_date_str = learner_info.get('start_date')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date(billing_year, 2, 1)
        except (ValueError, TypeError):
            start_date = date(billing_year, 2, 1)

        discount_multiplier = (100.0 - term_discount_percentage) / 100.0

        # Admission Fee
        raw_adm_fee = float(adm_fee_db or 0.0)
        if is_new and apply_adm and raw_adm_fee > 0:
            total_charges += raw_adm_fee

        # Monthly Fees
        raw_monthly_fee = float(monthly_fee_db or 0.0)
        if raw_monthly_fee > 0:
            monthly_fee = raw_monthly_fee * discount_multiplier

            start_month = max(start_date.month, 2)
            end_month = min(current_month_num, 11)
            
            for month_num in range(start_month, end_month + 1):
                total_charges += monthly_fee

        return total_charges - learner_payments