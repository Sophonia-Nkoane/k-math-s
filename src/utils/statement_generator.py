import os
import json
import sys
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StatementGenerator:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            # Running in a frozen/compiled environment
            BASE_DIR = os.path.join(os.path.expanduser("~"), "KMaths Learner Payment System")
            CONFIG_DIR = os.path.join(BASE_DIR, 'config')
        else:
            # Running in a normal Python environment
            CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'ui', 'config')
            
        self.config_file = os.path.join(CONFIG_DIR, 'statement_counter.json')
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        self.counter_data = self.load_counter()

    def generate_statement_number(self, is_new=False):
        """Unified method for generating statement numbers."""
        try:
            current_date = datetime.now()
            month_year = self._get_statement_month_year(current_date)
            
            if is_new:
                return f"STM-{month_year}-001"

            if month_year != self.counter_data.get('last_month'):
                self.counter_data['last_month'] = month_year
                self.counter_data['last_sequence'] = 1
            else:
                self.counter_data['last_sequence'] += 1

            sequence = f"{self.counter_data['last_sequence']:03d}"
            statement_number = f"STM-{month_year}-{sequence}"
            
            self.save_counter()
            return statement_number
            
        except Exception as e:
            logger.error(f"Error generating statement number: {e}")
            return f"STM-ERROR-{datetime.now().strftime('%Y%m')}-001"

    def _get_statement_month_year(self, date):
        """Calculate statement month/year based on current date."""
        if date.day < 25:
            if date.month == 1:
                return f"{date.year-1}12"
            return f"{date.year}{date.month-1:02d}"
        return f"{date.year}{date.month:02d}"

    def load_counter(self):
        """Load counter state from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return {'last_month': '', 'last_sequence': 0}
        except Exception as e:
            logger.error(f"Error loading counter state: {e}")
            return {'last_month': '', 'last_sequence': 0}

    def save_counter(self):
        """Save counter state to file."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.counter_data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving counter state: {e}")
