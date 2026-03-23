import os
import sys
import logging
from PySide6.QtGui import QActionGroup

# Handle imports differently if running as script vs module
if __name__ == '__main__':
    # Add project root to Python path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, project_root)
    from presentation.components.buttons import ButtonFactory
else:
    from ..components.buttons import ButtonFactory

class MenuBar:
    def __init__(self, parent):
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Initializing menu bar")
        self.menu_bar = parent.menuBar()
        self.menu_bar.clear()
        self.setup_menus()
        self.logger.debug("Menu bar initialization complete")

    def setup_menus(self):
        self.logger.debug("Setting up menus")
        # Learner Payments Menu
        learner_payment_menu = self.menu_bar.addMenu("Learner Payments")
        learner_payment_menu.addAction(
            ButtonFactory.create_menu_action("Record Learner Payment", 
                self.parent, self.parent.open_record_payment_dialog)
        )
        learner_payment_menu.addSeparator()
        learner_payment_menu.addAction(
            ButtonFactory.create_menu_action("Pause Learner Billing",
                self.parent, self.parent.pause_selected_learner_billing)
        )
        learner_payment_menu.addAction(
            ButtonFactory.create_menu_action("Resume Learner Billing",
                self.parent, self.parent.resume_selected_learner_billing)
        )

        # Management Menu
        management_menu = self.menu_bar.addMenu("Management")
        management_menu.addAction(
            ButtonFactory.create_menu_action("Manage Payment Options",
                self.parent, self.parent.open_payment_options_dialog)
        )
        management_menu.addAction(
            ButtonFactory.create_menu_action("Manage Payment Terms",
                self.parent, self.parent.open_payment_terms_dialog)
        )
        management_menu.addAction(
            ButtonFactory.create_menu_action("Manage Families",
                self.parent, self.parent.open_families_dialog)
        )
        
        # Admin Menu (if user is admin)
        if self.parent.current_user_role == 'admin':
            admin_menu = self.menu_bar.addMenu("Admin")
            admin_menu.addAction(
                ButtonFactory.create_menu_action("Add User",
                    self.parent, self.parent.open_add_user_dialog)
            )
            admin_menu.addAction(
                ButtonFactory.create_menu_action("Users",
                    self.parent, self.parent.open_delete_user_dialog)
            )
            admin_menu.addAction(
                ButtonFactory.create_menu_action("View Audit Log",
                    self.parent, self.parent.open_audit_log_dialog)
            )

        # Control Menu
        control_menu = self.menu_bar.addMenu("Control")
        control_menu.addAction(
            ButtonFactory.create_menu_action("Reload Learners",
                self.parent, self.parent.load_learners)
        )
        control_menu.addAction(
            ButtonFactory.create_menu_action("Settings",
                self.parent, self.parent.open_system_settings_dialog)
        )
        control_menu.addSeparator()
        control_menu.addAction(
            ButtonFactory.create_menu_action("Statement Settings",
                self.parent, self.parent.open_statement_settings_dialog)
        )
        control_menu.addAction(
            ButtonFactory.create_menu_action("Email Settings",
                self.parent, self.parent.open_email_settings_dialog)
        )

        # Reports Menu
        reports_menu = self.menu_bar.addMenu("Reports")
        reports_menu.addAction(
            ButtonFactory.create_menu_action("Payment Statistics",
                self.parent, self.parent.show_payment_statistics)
        )
        reports_menu.addAction(
            ButtonFactory.create_menu_action("Learner Class List",
                self.parent, self.parent.open_learner_class_list_dialog)
        )
        reports_menu.addAction(
            ButtonFactory.create_menu_action("Learner Attendance",
                self.parent, self.parent.open_learner_attendance_dialog)
        )

        # View Menu (rightmost)
        view_menu = self.menu_bar.addMenu("View")
        theme_menu = view_menu.addMenu("Theme")
        
        # Theme actions
        self.light_action = ButtonFactory.create_menu_action(
            "Light", self.parent, lambda: self.change_theme(False))
        self.dark_action = ButtonFactory.create_menu_action(
            "Dark", self.parent, lambda: self.change_theme(True))
        self.system_action = ButtonFactory.create_menu_action(
            "System", self.parent, self.toggle_system_theme)
            
        # Make actions checkable and exclusive
        theme_group = QActionGroup(self.menu_bar)
        for action in [self.light_action, self.dark_action, self.system_action]:
            action.setCheckable(True)
            theme_group.addAction(action)
            theme_menu.addAction(action)
        
        # Set initial state
        self.update_theme_menu_state()
    
    def update_theme_menu_state(self):
        """Updates the checked state of the theme menu actions based on the current theme settings."""
        if hasattr(self.parent, 'theme_manager') and self.parent.theme_manager:
            theme_manager = self.parent.theme_manager
            
            if theme_manager.is_following_system():
                self.system_action.setChecked(True)
            elif theme_manager.is_dark_mode():
                self.dark_action.setChecked(True)
            else:
                self.light_action.setChecked(True)
        else:
            self.logger.warning("Theme manager not available to update theme menu state")
    
    def change_theme(self, is_dark):
        if hasattr(self.parent, 'theme_manager') and self.parent.theme_manager:
            self.parent.theme_manager.set_follow_system(False)
            self.parent.theme_manager.set_theme(is_dark)
            self.update_theme_menu_state()
        else:
            self.logger.error("theme_manager not found on parent object")
    
    def toggle_system_theme(self):
        if hasattr(self.parent, 'theme_manager') and self.parent.theme_manager:
            self.parent.theme_manager.set_follow_system(True)
            self.update_theme_menu_state()
        else:
            self.logger.error("theme_manager not found on parent object")
