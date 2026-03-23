# src/domain/models/learner_dto.py

from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class LearnerDTO:
    acc_no: Optional[str]
    name: str
    surname: str
    dob: str
    gender: str
    country_code: str
    contact_number: str
    email: str
    grade: int
    subjects_count: int
    payment_option: str
    payment_option_id: Optional[int]
    is_new_learner: bool
    apply_admission_fee: bool
    family_id: Optional[int]
    term_id: Optional[int]
    due_day_of_month: int
    billing_start_date: str
    due_days_of_month: List[int] = field(default_factory=list)
    scheduled_payment_dates: List[str] = field(default_factory=list)
    contacts: List[dict] = field(default_factory=list)
    parent_id: Optional[int] = None
    parent2_id: Optional[int] = None
    guardian_id: Optional[int] = None
    manual_amount_enabled: bool = False
    manual_amount: Optional[float] = None
    skip_initial_fee: bool = False
    custom_admission_amount_enabled: bool = False
    custom_admission_amount: Optional[float] = None
    progress_percentage: Optional[float] = None
