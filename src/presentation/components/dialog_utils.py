"""
Dialog Utilities Module

This module provides centralized utilities for common dialog operations
to eliminate code duplication across the application.
"""

from PySide6.QtWidgets import QMessageBox, QLabel, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt
from typing import Optional, Callable, Any, Dict, List
import sqlite3
import logging
from presentation.components.message_box import MessageBox
from presentation.components.confirmation_dialog import ConfirmationDialog
from presentation.components.success_dialog import SuccessDialog
from presentation.styles.colors import TEXT_COLOR


class DialogUtils:
    """Centralized utilities for dialog operations."""
    
    @staticmethod
    def show_message(parent, title: str, text: str, 
                    icon_type: QMessageBox.Icon = QMessageBox.Icon.Information):
        """
        Centralized method to show styled messages.
        
        Args:
            parent: Parent widget
            title: Message title
            text: Message content
            icon_type: Icon type for the message
        """
        MessageBox.show_styled_message(parent, title, text, icon_type)
    
    @staticmethod
    def show_error(parent, text: str, title: str = "Error"):
        """Show error message with Critical icon."""
        DialogUtils.show_message(parent, title, text, QMessageBox.Icon.Critical)
    
    @staticmethod
    def show_warning(parent, text: str, title: str = "Warning"):
        """Show warning message with Warning icon."""
        DialogUtils.show_message(parent, title, text, QMessageBox.Icon.Warning)
    
    @staticmethod
    def show_info(parent, text: str, title: str = "Information"):
        """Show information message with Information icon."""
        DialogUtils.show_message(parent, title, text, QMessageBox.Icon.Information)
    
    @staticmethod
    def show_success(parent, text: str):
        """Show success message using SuccessDialog."""
        return SuccessDialog.show_success(parent, text)
    
    @staticmethod
    def show_confirmation(parent, text: str, title: str = "Confirm", 
                         accept_text: str = "Yes", reject_text: str = "No") -> bool:
        """
        Show confirmation dialog and return True if accepted.
        
        Args:
            parent: Parent widget
            text: Confirmation message
            title: Dialog title
            accept_text: Accept button text
            reject_text: Reject button text
            
        Returns:
            bool: True if accepted, False if rejected
        """
        return ConfirmationDialog.show_dialog(
            parent=parent,
            title=title,
            message=text,
            accept_button_text=accept_text,
            reject_button_text=reject_text
        )
    
    @staticmethod
    def handle_database_error(parent, operation: str, error: Exception, 
                            show_details: bool = False):
        """
        Standardized database error handling.
        
        Args:
            parent: Parent widget
            operation: Description of the operation that failed
            error: The database error
            show_details: Whether to show detailed error message
        """
        error_message = f"Failed to {operation}."
        if show_details:
            error_message += f"\n\nDetails: {str(error)}"
        
        logging.error(f"Database error during {operation}: {error}")
        DialogUtils.show_error(parent, error_message, "Database Error")
    
    @staticmethod
    def safe_database_operation(parent, operation: Callable, 
                              operation_name: str, 
                              success_message: Optional[str] = None,
                              show_details_on_error: bool = False) -> bool:
        """
        Execute a database operation with standardized error handling.
        
        Args:
            parent: Parent widget
            operation: Function to execute
            operation_name: Description of the operation
            success_message: Message to show on success (optional)
            show_details_on_error: Whether to show error details
            
        Returns:
            bool: True if operation succeeded, False otherwise
        """
        try:
            result = operation()
            if success_message:
                DialogUtils.show_success(parent, success_message)
            return True
        except sqlite3.Error as e:
            DialogUtils.handle_database_error(
                parent, operation_name, e, show_details_on_error
            )
            return False
        except Exception as e:
            logging.error(f"Unexpected error during {operation_name}: {e}")
            DialogUtils.show_error(
                parent, 
                f"An unexpected error occurred while trying to {operation_name}.",
                "Unexpected Error"
            )
            return False


class ValidationUtils:
    """Centralized validation utilities for dialog inputs."""
    
    @staticmethod
    def validate_required_field(parent, field_value: str, field_name: str) -> bool:
        """
        Validate that a required field is not empty.
        
        Args:
            parent: Parent widget for error messages
            field_value: The field value to validate
            field_name: Name of the field for error messages
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not field_value or not field_value.strip():
            DialogUtils.show_warning(
                parent, 
                f"{field_name} is required.", 
                "Input Error"
            )
            return False
        return True
    
    @staticmethod
    def validate_numeric_field(parent, field_value: str, field_name: str, 
                             min_value: Optional[float] = None,
                             max_value: Optional[float] = None) -> Optional[float]:
        """
        Validate that a field contains a valid number.
        
        Args:
            parent: Parent widget for error messages
            field_value: The field value to validate
            field_name: Name of the field for error messages
            min_value: Minimum allowed value (optional)
            max_value: Maximum allowed value (optional)
            
        Returns:
            float: The validated number, or None if invalid
        """
        try:
            value = float(field_value)
            
            if min_value is not None and value < min_value:
                DialogUtils.show_warning(
                    parent,
                    f"{field_name} must be at least {min_value}.",
                    "Input Error"
                )
                return None
                
            if max_value is not None and value > max_value:
                DialogUtils.show_warning(
                    parent,
                    f"{field_name} must be no more than {max_value}.",
                    "Input Error"
                )
                return None
                
            return value
        except ValueError:
            DialogUtils.show_warning(
                parent,
                f"{field_name} must be a valid number.",
                "Input Error"
            )
            return None
    
    @staticmethod
    def validate_fields(parent, validations: List[Dict[str, Any]]) -> bool:
        """
        Validate multiple fields using a list of validation rules.
        
        Args:
            parent: Parent widget for error messages
            validations: List of validation dictionaries containing:
                - 'value': Field value to validate
                - 'name': Field name for error messages
                - 'required': Whether field is required (default: True)
                - 'type': Field type ('text', 'numeric', 'email', etc.)
                - 'min': Minimum value for numeric fields
                - 'max': Maximum value for numeric fields
                
        Returns:
            bool: True if all validations pass, False otherwise
        """
        for validation in validations:
            value = validation.get('value', '')
            name = validation.get('name', 'Field')
            required = validation.get('required', True)
            field_type = validation.get('type', 'text')
            
            # Check if field is required
            if required and not ValidationUtils.validate_required_field(parent, value, name):
                return False
            
            # Skip further validation if field is empty and not required
            if not value and not required:
                continue
            
            # Type-specific validation
            if field_type == 'numeric':
                min_val = validation.get('min')
                max_val = validation.get('max')
                if ValidationUtils.validate_numeric_field(
                    parent, value, name, min_val, max_val
                ) is None:
                    return False
            
            elif field_type == 'email':
                if not ValidationUtils.validate_email(parent, value, name):
                    return False
        
        return True
    
    @staticmethod
    def validate_email(parent, email: str, field_name: str = "Email") -> bool:
        """
        Validate email format.
        
        Args:
            parent: Parent widget for error messages
            email: Email address to validate
            field_name: Name of the field for error messages
            
        Returns:
            bool: True if valid email format, False otherwise
        """
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            DialogUtils.show_warning(
                parent,
                f"{field_name} must be a valid email address.",
                "Input Error"
            )
            return False
        return True


class DialogSetupUtils:
    """Utilities for common dialog setup patterns."""
    
    @staticmethod
    def create_label(text: str, style_color: bool = True) -> QLabel:
        """
        Create a styled label.
        
        Args:
            text: Label text
            style_color: Whether to apply TEXT_COLOR styling
            
        Returns:
            QLabel: Configured label widget
        """
        label = QLabel(text)
        if style_color:
            label.setStyleSheet(f"color: {TEXT_COLOR()};")
        return label
    
    @staticmethod
    def create_centered_button_layout(buttons: List) -> QHBoxLayout:
        """
        Create a centered button layout.
        
        Args:
            buttons: List of button widgets
            
        Returns:
            QHBoxLayout: Configured button layout
        """
        layout = QHBoxLayout()
        layout.addStretch()
        
        for button in buttons:
            layout.addWidget(button)
        
        layout.addStretch()
        return layout
    
    @staticmethod
    def create_message_layout(message: str, center: bool = True) -> QVBoxLayout:
        """
        Create a message layout with styled label.
        
        Args:
            message: Message text
            center: Whether to center the message
            
        Returns:
            QVBoxLayout: Configured message layout
        """
        layout = QVBoxLayout()
        label = DialogSetupUtils.create_label(message)
        
        if center:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
        label.setWordWrap(True)
        layout.addWidget(label)
        return layout


# Convenience functions for backward compatibility and ease of use
def show_error(parent, message: str, title: str = "Error"):
    """Convenience function to show error message."""
    return DialogUtils.show_error(parent, message, title)

def show_warning(parent, message: str, title: str = "Warning"):
    """Convenience function to show warning message."""
    return DialogUtils.show_warning(parent, message, title)

def show_info(parent, message: str, title: str = "Information"):
    """Convenience function to show info message."""
    return DialogUtils.show_info(parent, message, title)

def show_success(parent, message: str):
    """Convenience function to show success message."""
    return DialogUtils.show_success(parent, message)

def show_confirmation(parent, message: str, title: str = "Confirm") -> bool:
    """Convenience function to show confirmation dialog."""
    return DialogUtils.show_confirmation(parent, message, title)

def validate_required(parent, value: str, name: str) -> bool:
    """Convenience function for required field validation."""
    return ValidationUtils.validate_required_field(parent, value, name)

def safe_db_operation(parent, operation: Callable, operation_name: str, 
                     success_message: Optional[str] = None) -> bool:
    """Convenience function for safe database operations."""
    return DialogUtils.safe_database_operation(
        parent, operation, operation_name, success_message
    )
