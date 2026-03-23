"""
Class List Generator for Learner Payment Management System
Generates printable class lists with learner information
Supports individual grade lists and whole school lists grouped by grade
"""

import os
from pathlib import Path
from datetime import datetime, date, timedelta
import calendar
import logging
from typing import List, Dict, Any, Optional


class ClassListGenerator:
    def __init__(self, base_dir=None):
        """Initialize the class list generator."""
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
        
        self.base_dir = Path(base_dir)
        self.template_path = self.base_dir / 'class_list_template.html'
        self.school_template_path = self.base_dir / 'school_list_template.html'
        self.logo_path = self.base_dir / 'src' / 'presentation' / 'resources' / 'statement_logo.png'
        
    def generate_class_list(self, grade, learners=None, output_path=None, month=None, year=None):
        """
        Generate a class list for a specific grade.
        
        Args:
            grade (str): The grade level (e.g., "1", "2", "Grade 1")
            learners (list): List of learner dictionaries with 'name' and 'surname' keys
            output_path (str): Optional custom output path
            month (int): Month number (1-12), defaults to current month
            year (int): Year, defaults to current year
            
        Returns:
            str: Path to the generated HTML file
        """
        try:
            # Use current month/year if not provided
            if month is None:
                month = datetime.now().month
            if year is None:
                year = datetime.now().year
            
            # Calculate weeks in month
            week_count = self._get_weeks_in_month(month, year)
            month_name = calendar.month_name[month]
            
            # Read the template
            if not self.template_path.exists():
                raise FileNotFoundError(f"Template not found: {self.template_path}")
                
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Replace placeholders
            html_content = template_content.replace('{{GRADE}}', str(grade))
            html_content = html_content.replace('{{WEEK_COUNT}}', str(week_count))
            html_content = html_content.replace('{{MONTH_YEAR}}', f"{month_name}\\{year}")
            
            # Generate week headers
            week_headers = ""
            for i in range(1, week_count + 1):
                week_headers += f'<th class="week-cell">Week {i}</th>'
            html_content = html_content.replace('{{WEEK_HEADERS}}', week_headers)
            
            # Handle logo path
            if self.logo_path.exists():
                logo_src = str(self.logo_path).replace('\\', '/')
                html_content = html_content.replace('logo_placeholder.png', logo_src)
            
            # Populate learner data
            html_content = self._populate_learner_data(html_content, learners, week_count)
            
            # Generate output filename
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"class_list_grade_{grade}_{month_name}_{year}_{timestamp}.html"
                output_path = self.base_dir / 'logs' / output_filename
            
            # Ensure output directory exists
            os.makedirs(output_path.parent, exist_ok=True)
            
            # Write the generated HTML
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logging.info(f"Class list generated: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logging.error(f"Failed to generate class list: {e}")
            raise
    
    def _get_weeks_in_month(self, month, year):
        """Calculate the number of weeks in a given month."""
        # Get the first day of the month
        first_day = date(year, month, 1)
        
        # Get the last day of the month
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        # Calculate weeks - if month spans more than 4 weeks, it has 5 weeks
        first_week = first_day.isocalendar()[1]
        last_week = last_day.isocalendar()[1]
        
        # Handle year boundary
        if last_week < first_week:  # December to January
            weeks = (52 - first_week + 1) + last_week
        else:
            weeks = last_week - first_week + 1
        
        # Most months have 4-5 weeks, ensure we return 4 or 5
        return min(max(weeks, 4), 5)
    
    def _populate_learner_data(self, html_content, learners, week_count):
        """Populate the HTML template with actual learner data."""
        learner_rows = ""
        
        if learners:
            for learner in learners:
                name = learner.get('name', '')
                surname = learner.get('surname', '')
                full_name = f"{name} {surname}".strip()
                
                # Create week cells
                week_cells = ""
                for i in range(week_count):
                    week_cells += '<td class="week-cell"></td>'
                
                learner_rows += f"""
            <tr class="signature-row">
                <td class="name-cell">{full_name}</td>
                {week_cells}
            </tr>"""
        
        # Add empty rows to reach minimum of 10 rows for a class list
        current_count = len(learners) if learners else 0
        while current_count < 10:
            week_cells = ""
            for i in range(week_count):
                week_cells += '<td class="week-cell"></td>'
            
            learner_rows += f"""
            <tr class="signature-row">
                <td class="name-cell"></td>
                {week_cells}
            </tr>"""
            current_count += 1
        
        # Replace the placeholder in the template
        html_content = html_content.replace('{{LEARNER_ROWS}}', learner_rows)
        
        return html_content
    
    def generate_from_database(self, db_manager, grade):
        """
        Generate class list directly from database for a specific grade.
        
        Args:
            db_manager: Database manager instance
            grade (str): Grade level to filter learners
            
        Returns:
            str: Path to generated HTML file
        """
        try:
            # Query learners by grade from database
            query = """
            SELECT name, surname 
            FROM Learners 
            WHERE grade = ? AND is_active = 1
            ORDER BY surname, name
            """
            
            learners_data = db_manager.execute_query(query, (grade,), fetchall=True)
            
            # Convert to list of dictionaries
            learners = [
                {'name': row[0], 'surname': row[1]} 
                for row in learners_data
            ]
            
            return self.generate_class_list(grade, learners)
            
        except Exception as e:
            logging.error(f"Failed to generate class list from database: {e}")
            raise
    
    def generate_school_list(self, db_manager, output_path=None, month=None, year=None, 
                            include_inactive=False, grades=None):
        """
        Generate a comprehensive school list grouped by grades.
        
        Creates a single document with all learners organized by grade,
        showing learners like:
        - Grade 1: Thabo, Thsepo
        - Grade 2: Ndali, Thabe
        - etc.
        
        Args:
            db_manager: Database manager instance
            output_path (str): Optional custom output path
            month (int): Month number (1-12), defaults to current month
            year (int): Year, defaults to current year
            include_inactive (bool): Whether to include inactive learners
            grades (list): Optional list of specific grades to include
            
        Returns:
            str: Path to the generated HTML file
        """
        try:
            # Use current month/year if not provided
            if month is None:
                month = datetime.now().month
            if year is None:
                year = datetime.now().year
            
            week_count = self._get_weeks_in_month(month, year)
            month_name = calendar.month_name[month]
            
            # Read the school template
            if not self.school_template_path.exists():
                raise FileNotFoundError(f"School template not found: {self.school_template_path}")
                
            with open(self.school_template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Get all learners grouped by grade
            grades_data = self._get_learners_by_grade(db_manager, include_inactive, grades)
            
            # Calculate totals
            total_learners = sum(len(learners) for learners in grades_data.values())
            total_grades = len(grades_data)
            
            # Replace basic placeholders
            html_content = template_content.replace('{{MONTH_YEAR}}', f"{month_name} {year}")
            html_content = html_content.replace('{{TOTAL_LEARNERS}}', str(total_learners))
            html_content = html_content.replace('{{TOTAL_GRADES}}', str(total_grades))
            html_content = html_content.replace('{{WEEK_COUNT}}', str(week_count))
            html_content = html_content.replace('{{GENERATED_DATE}}', datetime.now().strftime("%Y-%m-%d %H:%M"))
            
            # Handle logo path
            if self.logo_path.exists():
                logo_src = str(self.logo_path).replace('\\', '/')
                html_content = html_content.replace('logo_placeholder.png', logo_src)
            
            # Generate grade sections
            grade_sections = self._generate_grade_sections(grades_data, week_count)
            html_content = html_content.replace('{{GRADE_SECTIONS}}', grade_sections)
            
            # Generate output filename
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"school_list_{month_name}_{year}_{timestamp}.html"
                output_path = self.base_dir / 'logs' / output_filename
            
            # Ensure output directory exists
            output_path = Path(output_path)
            os.makedirs(output_path.parent, exist_ok=True)
            
            # Write the generated HTML
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logging.info(f"School list generated: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logging.error(f"Failed to generate school list: {e}")
            raise
    
    def _get_learners_by_grade(self, db_manager, include_inactive=False, grades=None) -> Dict[int, List[Dict]]:
        """
        Get all learners grouped by grade from the database.
        
        Args:
            db_manager: Database manager instance
            include_inactive: Whether to include inactive learners
            grades: Optional list of specific grades to include
            
        Returns:
            Dictionary mapping grade numbers to lists of learner dictionaries
        """
        try:
            # Build query
            if include_inactive:
                query = "SELECT grade, name, surname FROM Learners WHERE 1=1"
            else:
                query = "SELECT grade, name, surname FROM Learners WHERE is_active = 1"
            
            # Add grade filter if specified
            params = []
            if grades:
                placeholders = ','.join(['?' for _ in grades])
                query += f" AND grade IN ({placeholders})"
                params = [int(g) for g in grades]
            
            query += " ORDER BY grade, surname, name"
            
            learners_data = db_manager.execute_query(query, tuple(params) if params else None, fetchall=True)
            
            # Group by grade
            grades_dict = {}
            for row in learners_data:
                grade = int(row[0]) if row[0] else 0
                if grade not in grades_dict:
                    grades_dict[grade] = []
                grades_dict[grade].append({
                    'name': row[1] or '',
                    'surname': row[2] or ''
                })
            
            return grades_dict
            
        except Exception as e:
            logging.error(f"Failed to get learners by grade: {e}")
            raise
    
    def _generate_grade_sections(self, grades_data: Dict[int, List[Dict]], week_count: int) -> str:
        """
        Generate HTML sections for each grade.
        
        Args:
            grades_data: Dictionary mapping grades to learner lists
            week_count: Number of weeks in the month
            
        Returns:
            HTML string with all grade sections
        """
        sections = []
        is_alt = False
        
        for grade in sorted(grades_data.keys()):
            learners = grades_data[grade]
            alt_class = "grade-alt" if is_alt else ""
            
            # Generate week headers
            week_headers = ""
            for i in range(1, week_count + 1):
                week_headers += f'<th class="week-cell">Week {i}</th>'
            
            # Generate learner rows
            learner_rows = ""
            for learner in learners:
                name = learner.get('name', '')
                surname = learner.get('surname', '')
                full_name = f"{name} {surname}".strip()
                
                week_cells = ""
                for i in range(week_count):
                    week_cells += '<td class="week-cell"></td>'
                
                learner_rows += f"""
                <tr class="signature-row">
                    <td class="name-cell">{full_name}</td>
                    {week_cells}
                </tr>"""
            
            # Add empty rows to reach minimum of 5 rows per grade
            current_count = len(learners)
            while current_count < 5:
                week_cells = ""
                for i in range(week_count):
                    week_cells += '<td class="week-cell"></td>'
                
                learner_rows += f"""
                <tr class="signature-row">
                    <td class="name-cell"></td>
                    {week_cells}
                </tr>"""
                current_count += 1
            
            # Build grade section
            section = f"""
        <div class="grade-section {alt_class}">
            <div class="grade-header">
                <span>Grade {grade}</span>
                <span class="grade-count">{len(learners)} learners</span>
            </div>
            <table class="class-table">
                <thead>
                    <tr>
                        <th rowspan="2" class="name-cell">Name & Surname</th>
                        <th colspan="{week_count}" class="date-header">Signature</th>
                    </tr>
                    <tr>
                        {week_headers}
                    </tr>
                </thead>
                <tbody>
                    {learner_rows}
                </tbody>
            </table>
        </div>"""
            
            sections.append(section)
            is_alt = not is_alt
        
        return "\n".join(sections)


# Example usage function
def create_sample_class_list():
    """Create a sample class list for testing."""
    generator = ClassListGenerator()
    
    # Sample learner data
    sample_learners = [
        {'name': 'John', 'surname': 'Smith'},
        {'name': 'Jane', 'surname': 'Doe'},
        {'name': 'Mike', 'surname': 'Johnson'},
    ]
    
    output_path = generator.generate_class_list("1", sample_learners)
    logging.info(f"Sample class list created: {output_path}")
    return output_path

if __name__ == "__main__":
    create_sample_class_list()
