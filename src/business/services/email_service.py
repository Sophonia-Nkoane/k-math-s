import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import logging
from utils.settings_manager import SettingsManager

class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self):
        self.settings_manager = SettingsManager()
        self.logger = logging.getLogger(__name__)

    def send_payment_thank_you_email(self, parent_email: str, learner_name: str, amount: float, payment_date: str) -> bool:
        """
        Send a thank you email to parent for payment.

        Args:
            parent_email: Parent's email address
            learner_name: Learner name
            amount: Payment amount
            payment_date: Payment date

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get email settings
            smtp_server = self.settings_manager.get_email_setting("smtp_host", "smtp.gmail.com")
            smtp_port = int(self.settings_manager.get_email_setting("smtp_port", "587"))
            username = self.settings_manager.get_email_setting("smtp_user", "")
            password = self.settings_manager.get_email_setting("smtp_password", "")
            use_tls = self.settings_manager.get_email_setting("smtp_tls", "true").lower() == "true"

            if not all([smtp_server, smtp_port, username, password, parent_email]):
                self.logger.error("Missing email configuration or parent email")
                return False

            # Get email templates
            subject_template = self.settings_manager.get_email_setting("payment_subject", "Payment Received - Thank You for {learner_name}'s Payment")
            body_template = self.settings_manager.get_email_setting("payment_body", "Dear Parent/Guardian,\n\nWe are pleased to confirm that we have received your payment for {learner_name}.\n\nPayment Details:\nLearner: {learner_name}\nAmount: R{amount:.2f}\nDate: {payment_date}\n\nThank you for your continued support.\n\nBest regards,\nPro K-Maths Administration")

            # Format templates with actual values
            subject = subject_template.format(learner_name=learner_name)
            body = self._format_email_body(body_template, {
                'learner_name': learner_name,
                'amount': amount,
                'payment_date': payment_date
            })

            # Create message
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = parent_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()

            server.login(username, password)
            text = msg.as_string()
            server.sendmail(username, parent_email, text)
            server.quit()

            self.logger.info(f"Thank you email sent to {parent_email} for {learner_name}'s payment of R{amount:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send thank you email to {parent_email}: {str(e)}")
            return False

    def _create_thank_you_email_body(self, learner_name: str, amount: float, payment_date: str) -> str:
        """Create HTML email body for thank you message."""
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2c3e50; text-align: center;">Payment Received Successfully</h2>

                <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <p>Dear Parent/Guardian,</p>

                    <p>We are pleased to confirm that we have received your payment for <strong>{learner_name}</strong>.</p>

                    <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #27ae60;">Payment Details:</h3>
                        <p><strong>Learner:</strong> {learner_name}</p>
                        <p><strong>Amount:</strong> R{amount:.2f}</p>
                        <p><strong>Date:</strong> {payment_date}</p>
                    </div>

                    <p>Your payment has been processed and recorded in our system. Thank you for your continued support of your child's education.</p>

                    <p>If you have any questions or need to discuss your account, please don't hesitate to contact us.</p>

                    <p>Best regards,<br>
                    <strong>Pro K-Maths Administration</strong></p>
                </div>

                <div style="text-align: center; color: #7f8c8d; font-size: 12px; margin-top: 20px;">
                    <p>This is an automated message. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def send_ocr_failure_notification(self, admin_email: str, document_type: str, file_path: str) -> bool:
        """
        Send notification when OCR fails to process a document.

        Args:
            admin_email: Admin email address to notify
            document_type: Type of document (payment slip, attendance sheet, etc.)
            file_path: Path to the failed document

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get email settings
            smtp_server = self.settings_manager.get_email_setting("smtp_host", "smtp.gmail.com")
            smtp_port = int(self.settings_manager.get_email_setting("smtp_port", "587"))
            username = self.settings_manager.get_email_setting("smtp_user", "")
            password = self.settings_manager.get_email_setting("smtp_password", "")
            use_tls = self.settings_manager.get_email_setting("smtp_tls", "true").lower() == "true"

            if not all([smtp_server, smtp_port, username, password, admin_email]):
                self.logger.error("Missing email configuration or admin email")
                return False

            # Get email templates
            subject_template = self.settings_manager.get_email_setting("ocr_subject", "OCR Processing Failed - {document_type} Document")
            body_template = self.settings_manager.get_email_setting("ocr_body", "Dear Administrator,\n\nThe system was unable to automatically process a {document_type} document using OCR.\n\nDocument Details:\nDocument Type: {document_type}\nFile Name: {filename}\n\nPlease review and enter the information manually.\n\nBest regards,\nPro K-Maths System")

            # Format templates with actual values
            import os
            filename = os.path.basename(file_path)
            subject = subject_template.format(document_type=document_type.title())
            body = self._format_email_body(body_template, {
                'document_type': document_type,
                'filename': filename,
                'filepath': file_path
            })

            # Create message
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = admin_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()

            server.login(username, password)
            text = msg.as_string()
            server.sendmail(username, admin_email, text)
            server.quit()

            self.logger.info(f"OCR failure notification sent to {admin_email} for {document_type} document: {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send OCR failure notification to {admin_email}: {str(e)}")
            return False

    def _create_ocr_failure_email_body(self, document_type: str, file_path: str) -> str:
        """Create HTML email body for OCR failure notification."""
        import os
        filename = os.path.basename(file_path)

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #fff3cd; padding: 20px; border-radius: 10px; border-left: 5px solid #ffc107;">
                <h2 style="color: #856404; text-align: center;">OCR Processing Failed</h2>

                <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <p>Dear Administrator,</p>

                    <p>The system was unable to automatically process a {document_type} document using OCR.</p>

                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #495057;">Document Details:</h3>
                        <p><strong>Document Type:</strong> {document_type.title()}</p>
                        <p><strong>File Name:</strong> {filename}</p>
                        <p><strong>Full Path:</strong> {file_path}</p>
                    </div>

                    <p><strong>Possible reasons for failure:</strong></p>
                    <ul>
                        <li>Poor document quality or image resolution</li>
                        <li>Unsupported document format or layout</li>
                        <li>Learner information not found in database</li>
                        <li>OCR model initialization issues</li>
                    </ul>

                    <p>The document has been uploaded but requires manual processing. Please review and enter the information manually.</p>

                    <p>Best regards,<br>
                    <strong>Pro K-Maths System</strong></p>
                </div>

                <div style="text-align: center; color: #6c757d; font-size: 12px; margin-top: 20px;">
                    <p>This is an automated system notification.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _format_email_body(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Format email body template with provided variables.

        Args:
            template: Email body template string
            variables: Dictionary of variables to substitute

        Returns:
            str: Formatted email body
        """
        try:
            # Handle special formatting for amount
            if 'amount' in variables:
                variables['amount'] = f"{variables['amount']:.2f}"

            # Format the template
            formatted_body = template.format(**variables)

            # Convert newlines to HTML breaks for plain text templates
            if not formatted_body.strip().startswith('<'):
                formatted_body = formatted_body.replace('\n', '<br>')

            return formatted_body

        except KeyError as e:
            self.logger.error(f"Missing variable in email template: {e}")
            return template
        except Exception as e:
            self.logger.error(f"Error formatting email body: {str(e)}")
            return template

    def send_statement_email(self, recipient_email: str, subject: str, statement_html: str, reference_id: str) -> bool:
        """
        Send a statement email to a recipient.

        Args:
            recipient_email: Recipient's email address
            subject: Email subject
            statement_html: HTML content of the statement
            reference_id: Learner or family reference ID

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get email settings
            smtp_server = self.settings_manager.get_email_setting("smtp_host", "smtp.gmail.com")
            smtp_port = int(self.settings_manager.get_email_setting("smtp_port", "587"))
            username = self.settings_manager.get_email_setting("smtp_user", "")
            password = self.settings_manager.get_email_setting("smtp_password", "")
            use_tls = self.settings_manager.get_email_setting("smtp_tls", "true").lower() == "true"

            if not all([smtp_server, smtp_port, username, password, recipient_email]):
                self.logger.error("Missing email configuration or recipient email")
                return False

            # Create message with statement HTML
            msg = MIMEMultipart('alternative')
            msg['From'] = username
            msg['To'] = recipient_email
            msg['Subject'] = subject

            # Add HTML content
            html_part = MIMEText(statement_html, 'html')
            msg.attach(html_part)

            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()

            server.login(username, password)
            text = msg.as_string()
            server.sendmail(username, recipient_email, text)
            server.quit()

            self.logger.info(f"Statement email sent to {recipient_email} for {reference_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send statement email to {recipient_email}: {str(e)}")
            return False

    def _create_statement_email_body(self, statement_html: str, recipient_name: str, reference_id: str) -> str:
        """Create HTML email body for statement with proper styling."""
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; background-color: #f8f9fa; }}
                .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ border-bottom: 2px solid #007bff; padding-bottom: 20px; margin-bottom: 30px; }}
                .greeting {{ font-size: 16px; margin-bottom: 20px; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 14px; }}
                .contact-info {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="color: #007bff; margin: 0;">Account Statement</h2>
                    <p style="margin: 10px 0 0 0; color: #6c757d;">Reference: {reference_id}</p>
                </div>

                <div class="greeting">
                    <p>Dear {recipient_name},</p>
                    <p>Please find your account statement below. This statement includes all charges and payments for the current billing period.</p>
                </div>

                <div class="statement-content">
                    {statement_html}
                </div>

                <div class="contact-info">
                    <h4 style="margin-top: 0;">Payment Information</h4>
                    <p><strong>Due Date:</strong> As indicated on your statement</p>
                    <p><strong>Payment Methods:</strong> EFT, Cash, or as specified in your payment terms</p>
                    <p><strong>Questions?</strong> Contact us at the details below</p>
                </div>

                <div class="footer">
                    <p><strong>Thank you for choosing Pro K-Maths!</strong></p>
                    <p>If you have any questions about this statement, please contact our administration office.</p>
                    <p style="font-size: 12px; color: #adb5bd;">This is an automated statement. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def test_email_connection(self) -> bool:
        """
        Test email connection and authentication.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            smtp_server = self.settings_manager.get_email_setting("smtp_host", "smtp.gmail.com")
            smtp_port = int(self.settings_manager.get_email_setting("smtp_port", "587"))
            username = self.settings_manager.get_email_setting("smtp_user", "")
            password = self.settings_manager.get_email_setting("smtp_password", "")
            use_tls = self.settings_manager.get_email_setting("smtp_tls", "true").lower() == "true"

            if not all([smtp_server, smtp_port, username, password]):
                return False

            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()

            server.login(username, password)
            server.quit()

            return True

        except Exception as e:
            self.logger.error(f"Email connection test failed: {str(e)}")
            return False
