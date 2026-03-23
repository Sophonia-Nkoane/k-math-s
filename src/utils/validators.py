import re
from datetime import datetime

def validate_email(email):
    """Validates an email address format."""
    if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False
    return True

def validate_contact_number(contact):
    """Validates a contact number format (South African style)."""
    if contact and not re.match(r"^0\d{2}-\d{3}-\d{4}$", contact):
        return False
    return True

def validate_name(name):
    """Validates a name format (allows letters, spaces, hyphens, apostrophes)."""
    if name and not re.match(r"^[A-Za-z\s\-']+$", name):
        return False
    return True

def validate_dob(dob):
    """Validates a date of birth format (YYYY-MM-DD)."""
    try:
        datetime.strptime(dob, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def validate_learner_data(
    # Learner basic info
    name, surname, dob, gender, country_code, contact, email,
    # Academic info
    grade, subjects, payment_option, term,
    # Parent 1
    p1_title, p1_name, p1_surname, p1_code, p1_contact, p1_email,
    # Parent 2
    p2_title, p2_name, p2_surname, p2_code, p2_contact, p2_email,
    # Guardian
    g_title, g_name, g_surname, g_code, g_contact, g_email,
    # Options validation
    valid_payment_options,
    # Family validation
    family_enabled=False,
    family_name=None,
    is_manual_amount=False
):
    """
    Validates all input data for adding or updating a learner.
    Returns an error message string if validation fails, otherwise None.
    """
    # Required Learner Fields (remove email from required fields)
    req_stud = {"Name": name, "Surname": surname, "DOB": dob, "Gender": gender,
                "Country Code": country_code, "Contact Number": contact,
                "Grade": grade, "Subjects": subjects,
                "Payment Option": payment_option, "Payment Term": term}
    for field, value in req_stud.items():
        if not value:
            return f"Learner {field} is required."

    # Family validation (only if enabled)
    if family_enabled and family_name == "-- Select Family --":
        return "Please select a valid family or disable family selection"

    # --- Parent/Guardian Core Logic ---
    parent1_provided = bool(p1_name or p1_surname or p1_contact or p1_email)
    parent1_required_fields = [p1_name, p1_surname, p1_code, p1_contact]
    parent1_complete = all(fld for fld in parent1_required_fields if fld)

    guardian_provided = bool(g_name or g_surname or g_contact or g_email)
    guardian_required_fields = [g_name, g_surname, g_code, g_contact]
    guardian_complete = all(fld for fld in guardian_required_fields if fld)

    if not parent1_complete and not guardian_complete:
        if parent1_provided or guardian_provided:
            return "Please complete all required fields (Name, Surname, Code, Contact) for either Parent 1 OR Guardian."
        else:
            return "Either Parent 1 details OR Guardian details are required."

    # --- Detailed Field Validations ---

    # Learner Fields
    if not validate_name(name): return "Invalid Learner Name format."
    if not validate_name(surname): return "Invalid Learner Surname format."
    if not validate_dob(dob): return "Invalid Learner DOB format (YYYY-MM-DD)."
    if not validate_contact_number(contact): return "Invalid Learner Contact format (0XX-XXX-XXXX)."
    if email and not validate_email(email): return "Invalid Learner Email format."

    # Parent 1 Fields (if provided and required fields are present)
    if parent1_provided:
        if not parent1_complete: # Should be caught above, but double-check
            return "Parent 1 requires Name, Surname, Code, and Contact if any details are provided."
        if not validate_name(p1_name): return "Invalid Parent 1 Name format."
        if not validate_name(p1_surname): return "Invalid Parent 1 Surname format."
        if not validate_contact_number(p1_contact): return "Invalid Parent 1 Contact format (0XX-XXX-XXXX)."
        if p1_email and not validate_email(p1_email): return "Invalid Parent 1 Email format."

    # Parent 2 Fields (if any detail provided)
    parent2_provided = bool(p2_name or p2_surname or p2_contact or p2_email)
    if parent2_provided:
        if not all([p2_name, p2_surname, p2_code, p2_contact]):
             return "Parent 2 requires Name, Surname, Code, and Contact if any details are provided."
        if not validate_name(p2_name): return "Invalid Parent 2 Name format."
        if not validate_name(p2_surname): return "Invalid Parent 2 Surname format."
        if not validate_contact_number(p2_contact): return "Invalid Parent 2 Contact format (0XX-XXX-XXXX)."
        if p2_email and not validate_email(p2_email): return "Invalid Parent 2 Email format."

    # Guardian Fields (if provided and required fields are present)
    if guardian_provided:
        if not guardian_complete: # Should be caught above, but double-check
            return "Guardian requires Name, Surname, Code, and Contact if any details are provided."
        if not validate_name(g_name): return "Invalid Guardian Name format."
        if not validate_name(g_surname): return "Invalid Guardian Surname format."
        if not validate_contact_number(g_contact): return "Invalid Guardian Contact format (0XX-XXX-XXXX)."
        if g_email and not validate_email(g_email): return "Invalid Guardian Email format."

    # Payment Option Validation (using provided valid options)
    if not is_manual_amount and payment_option not in valid_payment_options:
        return f"Selected Payment Option '{payment_option}' is invalid for the chosen Grade ({grade}) and Subjects ({subjects}). Please re-select."
    elif is_manual_amount:
        try:
            float(payment_option)
        except (ValueError, TypeError):
            return "Manual amount must be a valid number."

    return None # All validations passed
