# src/domain/services/fee_service.py

import logging

class FeeService:
    def __init__(self, payment_repository, learner_repository, family_repository):
        self.payment_repository = payment_repository
        self.learner_repository = learner_repository
        self.family_repository = family_repository
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_fees_display(self, option, subjects, grade, is_new, apply_adm, learner_acc_no=None, family_id=None):
        """Shows the applicable monthly fee, considering family discounts and modes."""
        if not learner_acc_no or not all([option, subjects is not None, grade is not None]):
            return "R 0.00"

        try:
            payment_options = self.payment_repository.get_payment_options()

            def get_base_fee(opt, subs, grd):
                lookup_key = (opt, subs, grd)
                if lookup_key in payment_options:
                    return payment_options[lookup_key].get('monthly_fee', 0)
                
                if opt == "MANUAL":
                    manual_key = ("MANUAL", subs, grd)
                    if manual_key in payment_options:
                        return payment_options[manual_key].get('monthly_fee', 0)
                
                return 0

            learner_base_monthly_fee = get_base_fee(option, subjects, grade)

            if family_id is None:
                family_id = self.learner_repository.get_family_id_for_learner(learner_acc_no)

            if family_id:
                family_data = self.family_repository.get_family_details_for_statement(family_id)

                if family_data:
                    payment_mode = family_data['payment_mode']
                    family_discount_percent = family_data.get('discount_percentage', 0.0)

                    if payment_mode == 'single_coverage':
                        active_family_learners = self.learner_repository.get_active_learners_in_family(family_id)
                        
                        if not active_family_learners:
                            return "R 0.00"
                        
                        learner_fees = []
                        for learner in active_family_learners:
                            acc, _, _, _, _, _, _, s_grade, s_subs, s_opt, _, _, _, _ = learner[:14]
                            fee = get_base_fee(s_opt, s_subs, s_grade)
                            learner_fees.append((acc, fee))
                        
                        learner_fees.sort(key=lambda x: x[1], reverse=True)
                        
                        if learner_fees and learner_acc_no == learner_fees[0][0]:
                            return f"R {learner_fees[0][1]:.2f}"
                        else:
                            return "R 0.00"

                    elif payment_mode == 'individual_discount':
                        family_discount_multiplier = (100.0 - family_discount_percent) / 100.0
                        fee_after_family_discount = learner_base_monthly_fee * family_discount_multiplier

                        term_id = self.payment_repository.get_active_term_for_learner(learner_acc_no)
                        term_discount_percent = self.payment_repository.get_term_discount(term_id)

                        term_multiplier = (100.0 - term_discount_percent) / 100.0
                        final_fee = fee_after_family_discount * term_multiplier
                        return f"R {final_fee:.2f}"

                    else:
                        self.logger.warning(f"Unknown payment_mode '{payment_mode}' for family {family_id}")

            if learner_base_monthly_fee > 0:
                term_id = self.payment_repository.get_active_term_for_learner(learner_acc_no)
                term_discount = self.payment_repository.get_term_discount(term_id)

                term_multiplier = (100.0 - term_discount) / 100.0
                final_fee = learner_base_monthly_fee * term_multiplier
                return f"R {final_fee:.2f}"
            else:
                return "R 0.00"

        except Exception as e:
            self.logger.error(f"Error calculating fees display for {learner_acc_no}: {e}")
            return "R 0.00"
