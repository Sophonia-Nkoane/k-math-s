"""
Base Dialog Component

This provides a base class for dialogs that includes common functionality
and standardized patterns to eliminate code duplication.
"""

from PySide6.QtWidgets import QMessageBox
from typing import Optional, Callable, Any, Dict, List
import sqlite3
import logging
from presentation.components.window_component import WindowComponent
from presentation.components.dialog_utils import DialogUtils, ValidationUtils, safe_db_operation
from utils.helpers import log_action


class BaseDialog(WindowComponent):
    """
    Base dialog class with common functionality.
    
    This class provides standardized methods for:
    - Message display (error, warning, info, success, confirmation)
    - Input validation
    - Database operations with error handling
    - User action logging
    """
    
    def __init__(self, parent=None, title: str = "Dialog", db_manager=None, 
                 current_user_id: Optional[int] = None):
        """
        Initialize base dialog.
        
        Args:
            parent: Parent widget
            title: Dialog window title
            db_manager: Database manager instance
            current_user_id: Current user ID for logging
        """
        super().__init__(parent, title=title)
        self.db_manager = db_manager
        self.current_user_id = current_user_id
        self._validation_errors = []
    
    # Message display methods using centralized utilities
    
    def show_error(self, message: str, title: str = "Error"):
        """Show error message."""
        DialogUtils.show_error(self, message, title)
    
    def show_warning(self, message: str, title: str = "Warning"):
        """Show warning message."""
        DialogUtils.show_warning(self, message, title)
    
    def show_info(self, message: str, title: str = "Information"):
        """Show information message."""
        DialogUtils.show_info(self, message, title)
    
    def show_success(self, message: str):
        """Show success message."""
        DialogUtils.show_success(self, message)
    
    def show_confirmation(self, message: str, title: str = "Confirm", 
                         accept_text: str = "Yes", reject_text: str = "No") -> bool:
        """Show confirmation dialog."""
        return DialogUtils.show_confirmation(
            self, message, title, accept_text, reject_text
        )
    
    def show_styled_message(self, title: str, text: str, 
                          icon_type: QMessageBox.Icon = QMessageBox.Icon.Information):
        """Show styled message (for backward compatibility)."""
        DialogUtils.show_message(self, title, text, icon_type)
    
    # Validation methods
    
    def validate_required(self, value: str, field_name: str) -> bool:
        """Validate required field."""
        return ValidationUtils.validate_required_field(self, value, field_name)
    
    def validate_numeric(self, value: str, field_name: str, 
                        min_value: Optional[float] = None,
                        max_value: Optional[float] = None) -> Optional[float]:
        """Validate numeric field."""
        return ValidationUtils.validate_numeric_field(
            self, value, field_name, min_value, max_value
        )
    
    def validate_email(self, email: str, field_name: str = "Email") -> bool:
        """Validate email field."""
        return ValidationUtils.validate_email(self, email, field_name)
    
    def validate_fields(self, validations: List[Dict[str, Any]]) -> bool:
        """Validate multiple fields using validation rules."""
        return ValidationUtils.validate_fields(self, validations)
    
    def add_validation_error(self, field_name: str, error_message: str):
        """Add validation error to the list."""
        self._validation_errors.append(f"{field_name}: {error_message}")
    
    def has_validation_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self._validation_errors) > 0
    
    def show_validation_errors(self):
        """Show all accumulated validation errors."""
        if self._validation_errors:
            error_text = "Please correct the following errors:\n\n" + \
                        "\n".join(f"• {error}" for error in self._validation_errors)
            self.show_error(error_text, "Validation Errors")
            self._validation_errors.clear()
    
    def clear_validation_errors(self):
        """Clear accumulated validation errors."""
        self._validation_errors.clear()
    
    # Database operation methods
    
    def safe_db_operation(self, operation: Callable, operation_name: str, 
                         success_message: Optional[str] = None,
                         show_details_on_error: bool = False) -> bool:
        """
        Execute database operation with error handling.
        
        Args:
            operation: Function to execute
            operation_name: Description of the operation
            success_message: Message to show on success
            show_details_on_error: Whether to show error details
            
        Returns:
            bool: True if successful, False otherwise
        """
        return DialogUtils.safe_database_operation(
            self, operation, operation_name, success_message, show_details_on_error
        )
    
    def handle_db_error(self, operation: str, error: Exception, 
                       show_details: bool = False):
        """Handle database errors with standardized messaging."""
        DialogUtils.handle_database_error(self, operation, error, show_details)
    
    # User action logging
    
    def log_action(self, action_type: str, object_id: Any, details: str = ""):
        """
        Log user action if current_user_id is set.
        
        Args:
            action_type: Type of action performed
            object_id: ID of the object affected
            details: Additional details about the action
        """
        if self.current_user_id and self.db_manager:
            try:
                log_action(
                    self.db_manager,
                    self.current_user_id,
                    action_type,
                    object_id,
                    details
                )
            except Exception as e:
                logging.warning(f"Failed to log action: {e}")
    
    # Common dialog patterns
    
    def confirm_action(self, action_description: str, 
                      details: str = "") -> bool:
        """
        Show confirmation dialog for an action.
        
        Args:
            action_description: Description of the action
            details: Additional details to show
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        message = f"Are you sure you want to {action_description}?"
        if details:
            message += f"\n\n{details}"
        
        return self.show_confirmation(message, "Confirm Action")
    
    def confirm_delete(self, item_description: str) -> bool:
        """
        Show confirmation dialog for deletion.
        
        Args:
            item_description: Description of item to delete
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        return self.show_confirmation(
            f"Are you sure you want to delete {item_description}?\n\n"
            "This action cannot be undone.",
            "Confirm Deletion",
            accept_text="Delete",
            reject_text="Cancel"
        )
    
    def save_with_confirmation(self, save_operation: Callable, 
                             item_description: str = "changes",
                             success_message: Optional[str] = None) -> bool:
        """
        Save with confirmation and error handling.
        
        Args:
            save_operation: Function that performs the save
            item_description: Description of what's being saved
            success_message: Custom success message
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self.confirm_action(f"save {item_description}"):
            return False
        
        default_success = success_message or f"Successfully saved {item_description}."
        
        return self.safe_db_operation(
            save_operation,
            f"save {item_description}",
            default_success
        )
    
    def delete_with_confirmation(self, delete_operation: Callable,
                               item_description: str,
                               success_message: Optional[str] = None) -> bool:
        """
        Delete with confirmation and error handling.
        
        Args:
            delete_operation: Function that performs the deletion
            item_description: Description of what's being deleted
            success_message: Custom success message
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self.confirm_delete(item_description):
            return False
        
        default_success = success_message or f"Successfully deleted {item_description}."
        
        return self.safe_db_operation(
            delete_operation,
            f"delete {item_description}",
            default_success
        )
    
    # Input field helpers
    
    def get_text_field_value(self, field, field_name: str, required: bool = True) -> Optional[str]:
        """
        Get and validate text field value.
        
        Args:
            field: The input field widget
            field_name: Name of the field for error messages
            required: Whether the field is required
            
        Returns:
            str: The field value if valid, None otherwise
        """
        value = field.text().strip() if hasattr(field, 'text') else str(field).strip()
        
        if required and not value:
            self.show_warning(f"{field_name} is required.", "Input Error")
            return None
        
        return value
    
    def get_numeric_field_value(self, field, field_name: str, 
                              min_value: Optional[float] = None,
                              max_value: Optional[float] = None) -> Optional[float]:
        """
        Get and validate numeric field value.
        
        Args:
            field: The input field widget
            field_name: Name of the field for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            
        Returns:
            float: The validated number, or None if invalid
        """
        if hasattr(field, 'text'):
            value_str = field.text().strip()
        elif hasattr(field, 'value'):
            value_str = str(field.value())
        else:
            value_str = str(field).strip()
        
        return self.validate_numeric(value_str, field_name, min_value, max_value)
    
    # Override methods for subclasses
    
    def validate_input(self) -> bool:
        """
        Override this method in subclasses to implement custom validation.
        
        Returns:
            bool: True if all input is valid, False otherwise
        """
        return True
    
    def clear_form(self):
        """Override this method to implement form clearing logic."""
        pass
    
    def load_data(self):
        """Override this method to implement data loading logic."""
        pass
    
    def save_data(self) -> bool:
        """
        Override this method to implement data saving logic.
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        return True
    
    def refresh_data(self):
        """Override this method to implement data refreshing logic."""
        pass
