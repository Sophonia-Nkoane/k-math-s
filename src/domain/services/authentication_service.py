import sqlite3
import bcrypt
import logging
from datetime import datetime


logger = logging.getLogger(__name__)

class AuthenticationService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Authentication service initialized")
        
    def validate_login(self, username, password):
        """Validates user login with detailed logging"""
        start_time = datetime.now()
        try:
            self.logger.info(f"Login attempt for user: {username}")
            
            # Query for user
            query = "SELECT user_id, username, password, role FROM Users WHERE username = ?"
            self.logger.debug(f"Executing query: {query} with username: {username}")
            user = self.db_manager.execute_query(query, (username,), fetchone=True)
            self.logger.debug(f"Query result: {user}")
            
            if not user:
                self.logger.warning(f"Login failed - User not found: {username}")
                return None, "Invalid username or password"
                
            try:
                stored_password = user[2]  # password hash from database
                self.logger.debug("Checking password")
                if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                    self.logger.info(f"Login successful for user: {username}")
                    result = {
                        'user_id': user[0],
                        'username': user[1],
                        'role': user[3]
                    }
                    self.logger.debug(f"Returning result: {result}")
                    return result, None
                else:
                    self.logger.warning(f"Login failed - Invalid password for user: {username}")
                    return None, "Invalid username or password"
                    
            except ValueError as e:
                self.logger.error(f"Password validation error for user {username}: {e}")
                return None, "Invalid password format"
                
        except Exception as e:
            self.logger.error(f"Login validation error: {e}", exc_info=True)
            return None, f"Authentication error: {str(e)}"
        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"Login validation time: {execution_time:.3f} seconds")
    
    def change_password(self, user_id, current_password, new_password):
        """Changes user password with logging"""
        try:
            self.logger.info(f"Password change attempt for user_id: {user_id}")
            
            # Verify current password first
            query = "SELECT password FROM Users WHERE user_id = ?"
            result = self.db_manager.execute_query(query, (user_id,), fetchone=True)
            
            if not result:
                self.logger.error(f"Password change failed - User not found: {user_id}")
                return False, "User not found"
                
            current_hash = result[0]
            if not bcrypt.checkpw(current_password.encode('utf-8'), current_hash.encode('utf-8')):
                self.logger.warning(f"Password change failed - Invalid current password for user_id: {user_id}")
                return False, "Current password is incorrect"
            
            # Hash and store new password
            new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            update_query = "UPDATE Users SET password = ? WHERE user_id = ?"
            self.db_manager.execute_query(update_query, (new_hash.decode('utf-8'), user_id), commit=True)
            
            self.logger.info(f"Password successfully changed for user_id: {user_id}")
            return True, "Password changed successfully"
            
        except Exception as e:
            self.logger.error(f"Password change error for user_id {user_id}: {e}", exc_info=True)
            return False, f"Error changing password: {str(e)}"
    
    def create_user(self, username, password, role='user'):
        """Creates a new user with logging"""
        try:
            self.logger.info(f"Creating new user: {username} with role: {role}")
            
            # Check if username already exists
            check_query = "SELECT COUNT(*) FROM Users WHERE username = ?"
            count = self.db_manager.execute_query(check_query, (username,), fetchone=True)[0]
            
            if count > 0:
                self.logger.warning(f"User creation failed - Username already exists: {username}")
                return False, "Username already exists"
            
            # Hash password and create user
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            insert_query = """
                INSERT INTO Users (username, password, role)
                VALUES (?, ?, ?)
            """
            self.db_manager.execute_query(
                insert_query,
                (username, password_hash.decode('utf-8'), role),
                commit=True
            )
            
            self.logger.info(f"User created successfully: {username}")
            return True, "User created successfully"
            
        except Exception as e:
            self.logger.error(f"User creation error for {username}: {e}", exc_info=True)
            return False, f"Error creating user: {str(e)}"

    def verify_admin(self, user_id):
        """Verifies if a user has admin privileges"""
        try:
            query = "SELECT role FROM Users WHERE user_id = ?"
            result = self.db_manager.execute_query(query, (user_id,), fetchone=True)
            
            is_admin = result and result[0] == 'admin'
            self.logger.info(f"Admin verification for user_id {user_id}: {is_admin}")
            return is_admin
            
        except Exception as e:
            self.logger.error(f"Admin verification error for user_id {user_id}: {e}")
            return False

    @staticmethod
    def verify_user_password(db_manager, user_id, password):
        """Static method to verify password that can be used by instance or directly"""
        try:
            query = "SELECT password FROM Users WHERE user_id = ?"
            result = db_manager.execute_query(query, (user_id,), fetchone=True)
            if not result:
                logger.warning(f"No user found with ID {user_id}")
                return False

            stored_value = result[0]
            password_bytes = password.encode('utf-8')

            try:
                stored_hash_bytes = stored_value.encode('utf-8')
                is_valid = bcrypt.checkpw(password_bytes, stored_hash_bytes)
                if is_valid:
                    logger.info(f"Password verification successful for user {user_id}")
                    return True
                else:
                    logger.warning(f"Password verification failed for user {user_id}")
                    return False
            except ValueError:
                # Handle legacy plain text passwords
                if stored_value == password:
                    # Upgrade to hash
                    new_hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
                    update_query = "UPDATE Users SET password = ? WHERE user_id = ?"
                    db_manager.execute_query(update_query, (new_hashed_password, user_id), commit=True)
                    logger.info(f"Password hash upgraded for user {user_id}")
                    return True
                return False

        except sqlite3.Error as e:
            logger.error(f"Database error during password verification: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during password verification: {e}")
            return False
