from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import Customer, Transaction, AuditLog
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class DatabaseOperationTools:
    def __init__(self, db: Session):
        self.db = db

    def update_customer_record(
        self, 
        session_id: str,
        customer_id: str, 
        updates: Dict[str, any]
    ) -> Dict[str, any]:
        """
        Update customer information in the database.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            updates: Dictionary of fields to update
        
        Returns:
            Dict with update status
        """
        try:
            logger.info(f"update_customer_record called with session_id={session_id}, customer_id={customer_id}, updates={updates}")
            
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id
            ).first()

            if not customer:
                return {
                    "success": False,
                    "message": "Customer not found"
                }

            # Define updatable fields for security
            updatable_fields = [
                'email', 'phone', 'address'
            ]
            
            updated_fields = []
            for field, value in updates.items():
                if field in updatable_fields and hasattr(customer, field):
                    old_value = getattr(customer, field)
                    setattr(customer, field, value)
                    updated_fields.append(f"{field}: {old_value} -> {value}")

            if not updated_fields:
                return {
                    "success": False,
                    "message": "No valid fields to update"
                }

            customer.updated_at = datetime.utcnow()
            self.db.commit()

            self._log_audit(session_id, customer_id, "update_customer_record", 
                          f"Updated fields: {', '.join(updated_fields)}", "success")

            return {
                "success": True,
                "message": f"Customer record updated successfully",
                "updated_fields": list(updates.keys()),
                "customer_name": customer.full_name
            }

        except Exception as e:
            self.db.rollback()
            self._log_audit(session_id, customer_id, "update_customer_record", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Update failed: {str(e)}"
            }

    def query_account_balance(
        self, 
        session_id: str,
        customer_id: str
    ) -> Dict[str, any]:
        """
        Retrieve current account balance for customer.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
        
        Returns:
            Dict with balance information
        """
        try:
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id,
                Customer.account_status == "active"
            ).first()

            if not customer:
                return {
                    "success": False,
                    "message": "Customer account not found or inactive"
                }

            # Get the most recent transaction to verify balance
            last_transaction = self.db.query(Transaction).filter(
                Transaction.customer_id == customer_id
            ).order_by(desc(Transaction.created_at)).first()

            balance_verification = "verified"
            if last_transaction and last_transaction.balance_after != customer.account_balance:
                balance_verification = "needs_reconciliation"

            self._log_audit(session_id, customer_id, "query_account_balance", 
                          f"Balance queried: ${customer.account_balance:.2f}", "success")

            return {
                "success": True,
                "customer_name": customer.full_name,
                "account_number": customer.account_number,
                "current_balance": customer.account_balance,
                "balance_status": balance_verification,
                "last_updated": customer.updated_at.isoformat() if customer.updated_at else None
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "query_account_balance", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Balance query failed: {str(e)}"
            }

    def transaction_history(
        self, 
        session_id: str,
        customer_id: str, 
        limit: int = 10,
        days: int = 30
    ) -> Dict[str, any]:
        """
        Retrieve transaction history for customer.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            limit: Number of transactions to return
            days: Number of days to look back
        
        Returns:
            Dict with transaction history
        """
        try:
            # Calculate date range
            start_date = datetime.utcnow() - timedelta(days=days)
            
            transactions = self.db.query(Transaction).filter(
                Transaction.customer_id == customer_id,
                Transaction.created_at >= start_date
            ).order_by(desc(Transaction.created_at)).limit(limit).all()

            transaction_list = []
            for txn in transactions:
                transaction_list.append({
                    "transaction_id": txn.transaction_id,
                    "date": txn.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": txn.transaction_type,
                    "amount": txn.amount,
                    "description": txn.description,
                    "balance_after": txn.balance_after,
                    "status": txn.status
                })

            # Get summary statistics
            total_credits = sum(t.amount for t in transactions if t.transaction_type == "credit")
            total_debits = sum(t.amount for t in transactions if t.transaction_type == "debit")

            self._log_audit(session_id, customer_id, "transaction_history", 
                          f"Retrieved {len(transaction_list)} transactions for {days} days", "success")

            return {
                "success": True,
                "transactions": transaction_list,
                "summary": {
                    "total_transactions": len(transaction_list),
                    "total_credits": total_credits,
                    "total_debits": total_debits,
                    "net_change": total_credits - total_debits,
                    "date_range_days": days
                }
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "transaction_history", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Transaction history failed: {str(e)}"
            }

    def update_contact_info(
        self, 
        session_id: str,
        customer_id: str, 
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Update customer contact information.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            email: New email address
            phone: New phone number
            address: New address
        
        Returns:
            Dict with update status
        """
        try:
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id
            ).first()

            if not customer:
                return {
                    "success": False,
                    "message": "Customer not found"
                }

            updates = {}
            if email is not None:
                updates["email"] = email
            if phone is not None:
                updates["phone"] = phone
            if address is not None:
                updates["address"] = address

            if not updates:
                return {
                    "success": False,
                    "message": "No contact information provided to update"
                }

            # Use the general update method
            return self.update_customer_record(session_id, customer_id, updates)

        except Exception as e:
            self._log_audit(session_id, customer_id, "update_contact_info", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Contact update failed: {str(e)}"
            }

    def create_transaction(
        self, 
        session_id: str,
        customer_id: str,
        amount: float,
        transaction_type: str,
        description: str = ""
    ) -> Dict[str, any]:
        """
        Create a new transaction record.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            amount: Transaction amount
            transaction_type: "credit" or "debit"
            description: Transaction description
        
        Returns:
            Dict with transaction creation status
        """
        try:
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id,
                Customer.account_status == "active"
            ).first()

            if not customer:
                return {
                    "success": False,
                    "message": "Customer account not found or inactive"
                }

            # Calculate new balance
            if transaction_type == "credit":
                new_balance = customer.account_balance + amount
            elif transaction_type == "debit":
                new_balance = customer.account_balance - amount
                if new_balance < 0:
                    return {
                        "success": False,
                        "message": "Insufficient funds for this transaction"
                    }
            else:
                return {
                    "success": False,
                    "message": "Invalid transaction type. Must be 'credit' or 'debit'"
                }

            # Create transaction record
            transaction = Transaction(
                transaction_id=str(uuid.uuid4()),
                customer_id=customer_id,
                amount=amount,
                transaction_type=transaction_type,
                description=description,
                balance_after=new_balance,
                status="completed"
            )

            # Update customer balance
            customer.account_balance = new_balance
            customer.updated_at = datetime.utcnow()

            self.db.add(transaction)
            self.db.commit()

            self._log_audit(session_id, customer_id, "create_transaction", 
                          f"{transaction_type.title()} ${amount:.2f}: {description}", "success")

            return {
                "success": True,
                "message": "Transaction completed successfully",
                "transaction_id": transaction.transaction_id,
                "amount": amount,
                "type": transaction_type,
                "new_balance": new_balance,
                "description": description
            }

        except Exception as e:
            self.db.rollback()
            self._log_audit(session_id, customer_id, "create_transaction", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Transaction failed: {str(e)}"
            }

    def _log_audit(self, session_id: str, customer_id: str, 
                   action: str, details: str, status: str):
        """Log audit trail for database operations."""
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


def get_database_tools(db: Session) -> DatabaseOperationTools:
    """Factory function to get database operation tools."""
    return DatabaseOperationTools(db)