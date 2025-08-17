from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.database import Customer, Session as DBSession, AuditLog, get_db
from datetime import datetime, timedelta
from passlib.context import CryptContext
import uuid
import logging

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


class IdentityVerificationTools:
    def __init__(self, db: Session):
        self.db = db

    def verify_customer_identity(
        self, 
        session_id: str,
        full_name: str, 
        account_number: str, 
        security_answer: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Verify customer identity using multiple factors.
        
        Args:
            session_id: Current session ID
            full_name: Customer's full name
            account_number: Customer's account number
            security_answer: Answer to security question (optional for first step)
        
        Returns:
            Dict with verification status and next steps
        """
        try:
            logger.info(f"verify_customer_identity called with session_id={session_id}, full_name={full_name}, account_number={account_number}, has_security_answer={security_answer is not None}")
            
            # Find customer by account number and name
            customer = self.db.query(Customer).filter(
                Customer.account_number == account_number,
                Customer.full_name.ilike(f"%{full_name}%")
            ).first()

            if not customer:
                self._log_audit(session_id, None, "identity_verification", 
                              f"Failed verification - customer not found", "failed")
                return {
                    "verified": False,
                    "message": "Customer information not found. Please check your details or visit a branch.",
                    "requires_security_question": False
                }

            # Check account status
            if customer.account_status != "active":
                self._log_audit(session_id, customer.customer_id, "identity_verification", 
                              f"Account status: {customer.account_status}", "failed")
                return {
                    "verified": False,
                    "message": "Account is not active. Please contact customer service.",
                    "requires_security_question": False
                }

            # Check login attempts
            if customer.login_attempts >= 3:
                self._log_audit(session_id, customer.customer_id, "identity_verification", 
                              "Too many failed attempts", "failed")
                return {
                    "verified": False,
                    "message": "Too many failed verification attempts. Please visit a branch.",
                    "requires_security_question": False
                }

            # If no security answer provided, ask for it
            if not security_answer:
                return {
                    "verified": False,
                    "message": f"Please answer your security question: {customer.security_question}",
                    "requires_security_question": True,
                    "customer_id": customer.customer_id
                }

            # Verify security answer
            if not self._verify_security_answer(customer.security_answer, security_answer):
                # Increment failed attempts
                customer.login_attempts += 1
                self.db.commit()
                
                self._log_audit(session_id, customer.customer_id, "identity_verification", 
                              "Incorrect security answer", "failed")
                return {
                    "verified": False,
                    "message": "Incorrect security answer. Please try again.",
                    "requires_security_question": True,
                    "remaining_attempts": 3 - customer.login_attempts
                }

            # Successful verification
            logger.info(f"Identity verification successful for customer_id={customer.customer_id}, account_number={account_number}")
            
            customer.login_attempts = 0
            customer.last_login = datetime.utcnow()
            customer.is_verified = True
            
            # Update session
            session = self.db.query(DBSession).filter(
                DBSession.session_id == session_id
            ).first()
            if session:
                session.customer_id = customer.customer_id
                session.is_verified = True
                session.last_activity = datetime.utcnow()
            
            self.db.commit()
            
            self._log_audit(session_id, customer.customer_id, "identity_verification", 
                          "Successful verification", "success")
            
            verification_result = {
                "verified": True,
                "message": f"Identity verified successfully. Welcome, {customer.full_name}!",
                "customer_id": customer.customer_id,
                "customer_name": customer.full_name
            }
            
            logger.info(f"Identity verification result: {verification_result}")
            return verification_result

        except Exception as e:
            self._log_audit(session_id, None, "identity_verification", 
                          f"Error: {str(e)}", "failed")
            return {
                "verified": False,
                "message": "Verification system temporarily unavailable. Please try again later.",
                "requires_security_question": False
            }

    def validate_security_question(self, customer_id: str, answer: str) -> Dict[str, any]:
        """
        Validate security question answer.
        
        Args:
            customer_id: Customer ID
            answer: Security question answer
        
        Returns:
            Dict with validation result
        """
        try:
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id
            ).first()

            if not customer:
                return {"valid": False, "message": "Customer not found"}

            is_valid = self._verify_security_answer(customer.security_answer, answer)
            
            return {
                "valid": is_valid,
                "message": "Security answer validated" if is_valid else "Incorrect answer"
            }

        except Exception as e:
            return {"valid": False, "message": f"Validation error: {str(e)}"}

    def check_account_status(self, customer_id: str) -> Dict[str, any]:
        """
        Check customer account status.
        
        Args:
            customer_id: Customer ID
        
        Returns:
            Dict with account status information
        """
        try:
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id
            ).first()

            if not customer:
                return {"status": "not_found", "message": "Customer account not found"}

            return {
                "status": customer.account_status,
                "customer_name": customer.full_name,
                "account_number": customer.account_number,
                "is_verified": customer.is_verified,
                "last_login": customer.last_login.isoformat() if customer.last_login else None
            }

        except Exception as e:
            return {"status": "error", "message": f"Status check error: {str(e)}"}

    def _verify_security_answer(self, stored_answer: str, provided_answer: str) -> bool:
        """Verify security answer (case-insensitive comparison)."""
        return stored_answer.lower().strip() == provided_answer.lower().strip()

    def _log_audit(self, session_id: str, customer_id: Optional[str], 
                   action: str, details: str, status: str):
        """Log audit trail for security events."""
        try:
            audit_log = AuditLog(
                session_id=session_id,
                customer_id=customer_id,
                action=action,
                details=details,
                status=status,
                timestamp=datetime.utcnow()
            )
            self.db.add(audit_log)
            self.db.commit()
        except Exception as e:
            print(f"Audit logging error: {e}")


def get_identity_tools(db: Session) -> IdentityVerificationTools:
    """Factory function to get identity verification tools."""
    return IdentityVerificationTools(db)