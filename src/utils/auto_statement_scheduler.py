import threading
import time
import logging
from datetime import datetime, timedelta
from PySide6.QtCore import QTimer, QObject, Signal
from utils.settings_manager import SettingsManager
from data.database_manager import DatabaseManager
from business.services.statement_service import StatementService
from business.services.email_service import EmailService

class AutoStatementScheduler(QObject):
    """Background scheduler for automatic statement generation and email delivery."""
    
    generation_complete = Signal(str)  # Signal for UI updates
    generation_started = Signal(str)   # Signal when generation starts
    
    def __init__(self, main_window, db_manager):
        super().__init__()
        self.main_window = main_window
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings_manager = SettingsManager()
        
        # Initialize services
        from data.repositories.learner_repository import LearnerRepository
        from data.repositories.family_repository import FamilyRepository
        from data.repositories.payment_repository import PaymentRepository
        
        learner_repository = LearnerRepository(db_manager)
        family_repository = FamilyRepository(db_manager)
        payment_repository = PaymentRepository(db_manager)
        
        self.statement_service = StatementService(
            main_window, learner_repository, family_repository, 
            payment_repository, main_window.logo_path, db_manager
        )
        self.email_service = EmailService(db_manager)
        
        # Background thread for scheduling
        self.scheduler_thread = None
        self.running = False
        self.last_generation_date = None
        
        # Timer for UI updates and periodic checks
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.check_schedule)
        self.ui_timer.start(60000)  # Check every minute
        
        # Status tracking
        self.is_generating = False
        self.next_generation_time = None
        
    def start(self):
        """Start the automatic statement generation scheduler."""
        if self.settings_manager.get_system_setting("auto_generate_enabled", False):
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._background_worker)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            self._calculate_next_generation_time()
            
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
            
    def _background_worker(self):
        """Background thread that monitors for statement generation time."""
        while self.running:
            try:
                if self._should_generate_statements():
                    self._generate_and_send_statements()
                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                self.logger.exception(f"Scheduler error: {e}")
                time.sleep(60)  # Wait before retrying
                
    def _should_generate_statements(self) -> bool:
        """Check if it's time to generate statements."""
        if not self.running or self.is_generating:
            return False
            
        now = datetime.now()
        
        # Get configuration
        target_day = self.settings_manager.get_system_setting("auto_generate_day", 25)
        target_hour = self.settings_manager.get_system_setting("auto_generate_hour", 9)
        target_minute = self.settings_manager.get_system_setting("auto_generate_minute", 0)
        
        # Check if current time matches target time
        time_matches = (now.day == target_day and 
                       now.hour == target_hour and 
                       now.minute == target_minute)
        
        # Check if we haven't generated today already
        date_matches = (self.last_generation_date is None or 
                       self.last_generation_date.date() != now.date())
        
        return time_matches and date_matches
                
    def _generate_and_send_statements(self):
        """Generate statements for all active learners and send via email."""
        if self.is_generating:
            return
            
        self.is_generating = True
        generation_start_time = datetime.now()
        
        try:
            self.generation_started.emit("Starting automatic statement generation...")
            
            # Get all active learners and families
            active_learners = self._get_active_learners()
            active_families = self._get_active_families()
            
            total_generated = 0
            total_sent = 0
            errors = []
            
            # Generate and send learner statements
            for learner in active_learners:
                try:
                    # Generate statement HTML
                    statement_html = self.statement_service.generate_learner_statement_html(
                        learner.acc_no, self.main_window.current_username
                    )
                    
                    # Send email
                    if learner.email:
                        success = self.email_service.send_statement_email(
                            learner.email, 
                            f"Statement for {learner.name} {learner.surname}",
                            statement_html,
                            learner.acc_no
                        )
                        if success:
                            total_sent += 1
                        else:
                            errors.append(f"Failed to send to {learner.email}")
                    
                    total_generated += 1
                    
                except Exception as e:
                    errors.append(f"Error with learner {learner.acc_no}: {str(e)}")
            
            # Generate and send family statements
            for family in active_families:
                try:
                    # Generate family statement HTML
                    statement_html = self.statement_service.generate_family_statement_html(
                        family.id, self.main_window.current_username
                    )
                    
                    # Send to primary parent email
                    if family.p1_email:
                        success = self.email_service.send_statement_email(
                            family.p1_email,
                            f"Family Statement for {family.account_no}",
                            statement_html,
                            family.account_no
                        )
                        if success:
                            total_sent += 1
                        else:
                            errors.append(f"Failed to send to family {family.account_no}")
                    
                    total_generated += 1
                    
                except Exception as e:
                    errors.append(f"Error with family {family.account_no}: {str(e)}")
            
            # Log generation results
            self._log_generation_results(
                total_generated, total_sent, len(errors), 
                generation_start_time, errors
            )
            
            # Update status
            self.last_generation_date = datetime.now()
            self._calculate_next_generation_time()
            
            message = f"Generated {total_generated} statements, sent {total_sent} emails"
            if errors:
                message += f" (with {len(errors)} errors)"
            
            self.generation_complete.emit(message)
            
        except Exception as e:
            error_msg = f"Statement generation failed: {str(e)}"
            self.logger.error(error_msg)
            self.generation_complete.emit(error_msg)
            
        finally:
            self.is_generating = False
            
    def _get_active_learners(self):
        """Get all active learners from database."""
        try:
            query = """
                SELECT s.acc_no, s.name, s.surname, s.email, s.family_id
                FROM Learners s
                WHERE s.is_active = 1
            """
            results = self.db_manager.execute_query(query, fetchall=True)
            
            learners = []
            for row in results:
                learner = type('Learner', (), {
                    'acc_no': row[0],
                    'name': row[1], 
                    'surname': row[2],
                    'email': row[3],
                    'family_id': row[4]
                })()
                learners.append(learner)
            
            return learners
        except Exception as e:
            self.logger.error(f"Error fetching active learners: {e}")
            return []
            
    def _get_active_families(self):
        """Get all active families from database."""
        try:
            query = """
                SELECT f.family_id, f.family_account_no, f.p1_email
                FROM Families f
                WHERE f.is_active = 1
            """
            results = self.db_manager.execute_query(query, fetchall=True)
            
            families = []
            for row in results:
                family = type('Family', (), {
                    'id': row[0],
                    'account_no': row[1],
                    'p1_email': row[2]
                })()
                families.append(family)
            
            return families
        except Exception as e:
            self.logger.error(f"Error fetching active families: {e}")
            return []
            
    def _log_generation_results(self, generated, sent, errors, start_time, error_details):
        """Log statement generation results to database."""
        try:
            duration = datetime.now() - start_time
            status = "SUCCESS" if errors == 0 else "PARTIAL_SUCCESS" if sent > 0 else "FAILED"
            
            query = """
                INSERT INTO statement_generation_log 
                (generation_date, statements_generated, emails_sent, errors_count, duration_seconds, status, error_details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            error_details_str = "; ".join(error_details) if error_details else None
            
            self.db_manager.execute_query(query, (
                start_time.strftime("%Y-%m-%d %H:%M:%S"),
                generated,
                sent,
                errors,
                int(duration.total_seconds()),
                status,
                error_details_str
            ), commit=True)
            
        except Exception as e:
            self.logger.error(f"Error logging generation results: {e}")
            
    def _calculate_next_generation_time(self):
        """Calculate the next statement generation time."""
        try:
            target_day = self.settings_manager.get_system_setting("auto_generate_day", 25)
            target_hour = self.settings_manager.get_system_setting("auto_generate_hour", 9)
            target_minute = self.settings_manager.get_system_setting("auto_generate_minute", 0)
            
            now = datetime.now()
            
            # Create next month's target date
            if now.day >= target_day:
                # Move to next month
                if now.month == 12:
                    next_month = 1
                    next_year = now.year + 1
                else:
                    next_month = now.month + 1
                    next_year = now.year
            else:
                # Same month
                next_month = now.month
                next_year = now.year
                
            # Handle month-end edge cases (e.g., Feb 30th)
            try:
                self.next_generation_time = datetime(
                    next_year, next_month, target_day, target_hour, target_minute
                )
            except ValueError:
                # If target day doesn't exist in the month, use last day of month
                if next_month == 2:
                    target_day = 28  # Handle February
                elif next_month in [4, 6, 9, 11]:
                    target_day = 30  # 30-day months
                else:
                    target_day = 31  # 31-day months
                    
                self.next_generation_time = datetime(
                    next_year, next_month, target_day, target_hour, target_minute
                )
                
        except Exception as e:
            self.logger.error(f"Error calculating next generation time: {e}")
            self.next_generation_time = None
            
    def check_schedule(self):
        """Check if we should generate statements and update UI status."""
        if not self.running:
            return
            
        try:
            now = datetime.now()
            
            # Check if it's time to generate
            if (self.next_generation_time and 
                now >= self.next_generation_time and 
                not self.is_generating):
                
                # Trigger generation
                if self._should_generate_statements():
                    # Start generation in background
                    generation_thread = threading.Thread(target=self._generate_and_send_statements)
                    generation_thread.daemon = True
                    generation_thread.start()
                    
                    # Recalculate next generation time
                    self._calculate_next_generation_time()
            
            # Update UI status if needed
            if hasattr(self.main_window, 'update_auto_generation_status'):
                self.main_window.update_auto_generation_status(
                    self.running, self.is_generating, self.next_generation_time
                )
                
        except Exception as e:
            self.logger.error(f"Error in schedule check: {e}")
            
    def manual_generate_statements(self):
        """Manually trigger statement generation (for UI button)."""
        if self.is_generating:
            return "Already generating statements"
            
        try:
            self.generation_started.emit("Manual statement generation started...")
            
            # Run generation in background thread
            generation_thread = threading.Thread(target=self._generate_and_send_statements)
            generation_thread.daemon = True
            generation_thread.start()
            
            return "Manual generation started"
            
        except Exception as e:
            return f"Manual generation failed: {str(e)}"
            
    def get_status_info(self) -> dict:
        """Get current scheduler status for UI display."""
        return {
            'enabled': self.running,
            'is_generating': self.is_generating,
            'next_generation_time': self.next_generation_time,
            'last_generation_date': self.last_generation_date
        }
