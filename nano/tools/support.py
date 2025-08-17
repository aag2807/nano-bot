from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.database import AuditLog
from datetime import datetime
from app.config import settings


class GeneralSupportTools:
    def __init__(self, db: Session):
        self.db = db
        self.knowledge_base = self._load_banking_knowledge()

    def banking_knowledge_base(
        self, 
        session_id: str,
        customer_id: Optional[str],
        query: str
    ) -> Dict[str, any]:
        """
        Access banking procedures and general knowledge.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID (if available)
            query: Knowledge query
        
        Returns:
            Dict with relevant banking information
        """
        try:
            query_lower = query.lower()
            relevant_info = []
            
            # Search through knowledge base
            for category, info_dict in self.knowledge_base.items():
                for topic, details in info_dict.items():
                    # Simple keyword matching
                    if any(keyword in query_lower for keyword in topic.lower().split()):
                        relevant_info.append({
                            "category": category,
                            "topic": topic,
                            "information": details["info"],
                            "steps": details.get("steps", []),
                            "requirements": details.get("requirements", [])
                        })

            if not relevant_info:
                # Fallback for common banking terms
                if any(term in query_lower for term in ["balance", "account"]):
                    relevant_info.append({
                        "category": "account_services",
                        "topic": "Account Balance Inquiry",
                        "information": "I can help you check your account balance after verifying your identity.",
                        "steps": ["Provide full name and account number", "Answer security question", "View current balance"],
                        "requirements": ["Valid identification", "Security verification"]
                    })

            self._log_audit(session_id, customer_id, "banking_knowledge_base", 
                          f"Query: {query}, Results: {len(relevant_info)}", "success")

            return {
                "success": True,
                "query": query,
                "results": relevant_info,
                "total_results": len(relevant_info)
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "banking_knowledge_base", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Knowledge search failed: {str(e)}"
            }

    def escalate_to_human(
        self, 
        session_id: str,
        customer_id: Optional[str],
        reason: str,
        priority: str = "normal"
    ) -> Dict[str, any]:
        """
        Escalate customer to human representative.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID (if available)
            reason: Reason for escalation
            priority: Escalation priority (low, normal, high, urgent)
        
        Returns:
            Dict with escalation information
        """
        try:
            # Generate escalation ticket
            escalation_id = f"ESC-{datetime.utcnow().strftime('%Y%m%d')}-{session_id[-6:]}"
            
            escalation_info = {
                "escalation_id": escalation_id,
                "session_id": session_id,
                "customer_id": customer_id,
                "reason": reason,
                "priority": priority,
                "created_at": datetime.utcnow().isoformat(),
                "status": "pending"
            }

            # Determine next steps based on priority
            if priority == "urgent":
                wait_time = "immediate"
                contact_method = "Direct transfer to senior representative"
            elif priority == "high":
                wait_time = "5-10 minutes"
                contact_method = "Priority queue"
            else:
                wait_time = "15-20 minutes"
                contact_method = "Standard queue"

            self._log_audit(session_id, customer_id, "escalate_to_human", 
                          f"Escalation {escalation_id}: {reason} (Priority: {priority})", "success")

            return {
                "success": True,
                "escalation_id": escalation_id,
                "priority": priority,
                "estimated_wait_time": wait_time,
                "contact_method": contact_method,
                "message": f"I've created escalation ticket {escalation_id} to connect you with a human representative. Expected wait time: {wait_time}.",
                "next_steps": [
                    "Stay on the line for transfer",
                    "Reference escalation ID when speaking to representative",
                    "Provide any additional context about your inquiry"
                ]
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "escalate_to_human", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Escalation failed: {str(e)}"
            }

    def generate_summary(
        self, 
        session_id: str,
        customer_id: Optional[str],
        interaction_type: str = "general"
    ) -> Dict[str, any]:
        """
        Generate summary of customer interaction.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID (if available)
            interaction_type: Type of interaction
        
        Returns:
            Dict with interaction summary
        """
        try:
            # Get audit logs for this session
            logs = self.db.query(AuditLog).filter(
                AuditLog.session_id == session_id
            ).order_by(AuditLog.timestamp).all()

            if not logs:
                return {
                    "success": False,
                    "message": "No interaction data found for this session"
                }

            # Analyze the interaction
            actions_taken = []
            verification_status = "not_attempted"
            tools_used = set()
            
            for log in logs:
                actions_taken.append({
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": log.action,
                    "status": log.status,
                    "details": log.details
                })
                
                if log.action == "identity_verification":
                    verification_status = "completed" if log.status == "success" else "failed"
                
                tools_used.add(log.action)

            # Generate summary
            session_duration = (logs[-1].timestamp - logs[0].timestamp).total_seconds() / 60
            
            summary = {
                "session_id": session_id,
                "customer_id": customer_id,
                "start_time": logs[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": logs[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_minutes": round(session_duration, 2),
                "verification_status": verification_status,
                "tools_used": list(tools_used),
                "total_actions": len(actions_taken),
                "successful_actions": sum(1 for log in logs if log.status == "success"),
                "interaction_type": interaction_type,
                "actions_taken": actions_taken
            }

            self._log_audit(session_id, customer_id, "generate_summary", 
                          f"Generated summary for {len(actions_taken)} actions", "success")

            return {
                "success": True,
                "summary": summary
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "generate_summary", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Summary generation failed: {str(e)}"
            }

    def _load_banking_knowledge(self) -> Dict[str, Dict[str, Dict[str, any]]]:
        """Load banking knowledge base."""
        return {
            "account_services": {
                "Account Balance Inquiry": {
                    "info": "Check your current account balance and recent transactions.",
                    "steps": ["Verify identity", "Access account information", "Display balance"],
                    "requirements": ["Valid ID", "Security verification"]
                },
                "Account Statements": {
                    "info": "View and download monthly account statements.",
                    "steps": ["Log in to account", "Navigate to statements", "Select date range", "Download PDF"],
                    "requirements": ["Account access", "Identity verification"]
                },
                "Update Contact Information": {
                    "info": "Change your address, phone number, or email address.",
                    "steps": ["Verify identity", "Provide new information", "Confirm changes"],
                    "requirements": ["Identity verification", "Valid contact details"]
                }
            },
            "transactions": {
                "Transfer Funds": {
                    "info": "Transfer money between your accounts or to external accounts.",
                    "steps": ["Verify identity", "Select accounts", "Enter amount", "Confirm transfer"],
                    "requirements": ["Sufficient funds", "Valid recipient account"]
                },
                "Transaction History": {
                    "info": "View your recent transaction history and details.",
                    "steps": ["Access account", "Select date range", "View transactions"],
                    "requirements": ["Account access"]
                },
                "Stop Payment": {
                    "info": "Stop payment on a check or recurring transaction.",
                    "steps": ["Provide check/transaction details", "Pay stop payment fee", "Confirm request"],
                    "requirements": ["Valid reason", "Transaction details", "Fee payment"]
                }
            },
            "security": {
                "Password Reset": {
                    "info": "Reset your online banking password securely.",
                    "steps": ["Verify identity", "Set new password", "Confirm changes"],
                    "requirements": ["Identity verification", "Strong password"]
                },
                "Account Security": {
                    "info": "Information about keeping your account secure.",
                    "steps": ["Use strong passwords", "Monitor statements", "Report suspicious activity"],
                    "requirements": ["Regular monitoring", "Secure practices"]
                },
                "Fraud Reporting": {
                    "info": "Report suspected fraudulent activity on your account.",
                    "steps": ["Contact bank immediately", "Provide transaction details", "Complete fraud affidavit"],
                    "requirements": ["Immediate action", "Documentation"]
                }
            },
            "general": {
                "Branch Locations": {
                    "info": "Find Bank Of AI branches and ATM locations near you.",
                    "steps": ["Use branch locator", "Check hours", "Plan visit"],
                    "requirements": ["Location information"]
                },
                "Contact Information": {
                    "info": "Get contact information for different banking services.",
                    "steps": ["Select service type", "Choose contact method"],
                    "requirements": ["Service identification"]
                },
                "Banking Hours": {
                    "info": "Bank operating hours and holiday schedule.",
                    "steps": ["Check regular hours", "Verify holiday schedule"],
                    "requirements": ["None"]
                }
            }
        }

    def _log_audit(self, session_id: str, customer_id: Optional[str], 
                   action: str, details: str, status: str):
        """Log audit trail for support operations."""
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


def get_support_tools(db: Session) -> GeneralSupportTools:
    """Factory function to get general support tools."""
    return GeneralSupportTools(db)