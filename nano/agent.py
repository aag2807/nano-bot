import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import logging

logger = logging.getLogger(__name__)

from app.database import Session as DBSession, get_db, AuditLog, Conversation
from nano.prompts.system_prompt import NANO_SYSTEM_PROMPT
from nano.tools.identity import get_identity_tools
from nano.tools.files import get_file_tools
from nano.tools.database import get_database_tools
from nano.tools.support import get_support_tools
from nano.tools.ocr import get_ocr_tools
from app.config import settings


class NANOAgent:
    def __init__(self, db: Session):
        self.db = db
        self.model_name = settings.hf_model_name
        self.tokenizer = None
        self.model = None
        self._load_model()
        
        # Initialize tools
        self.identity_tools = get_identity_tools(db)
        self.file_tools = get_file_tools(db)
        self.database_tools = get_database_tools(db)
        self.support_tools = get_support_tools(db)
        self.ocr_tools = get_ocr_tools(db)
        
        # Session management
        self.active_sessions = {}

    def _load_model(self):
        """Load the HuggingFace model and tokenizer."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )
            print(f"Loaded model: {self.model_name}")
        except Exception as e:
            print(f"Error loading model: {e}")
            # Fallback to basic text generation
            self.model = None
            self.tokenizer = None

    def create_session(self, customer_id: Optional[str] = None) -> str:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        
        # Create session in database
        session = DBSession(
            session_id=session_id,
            customer_id=customer_id,
            status="active"
        )
        self.db.add(session)
        self.db.commit()
        
        # Track in memory
        self.active_sessions[session_id] = {
            "created_at": datetime.utcnow(),
            "customer_id": customer_id,
            "is_verified": False
        }
        
        self._log_audit(session_id, customer_id, "create_session", "New session created", "success")
        return session_id

    def process_message(self, session_id: str, message: str, customer_id: Optional[str] = None) -> Dict[str, any]:
        """
        Process incoming customer message and generate appropriate response.
        
        Args:
            session_id: Session identifier
            message: Customer message
            customer_id: Customer ID if provided
        
        Returns:
            Dict with agent response and metadata
        """
        try:
            # Validate session
            if session_id not in self.active_sessions:
                # Try to restore from database
                db_session = self.db.query(DBSession).filter(
                    DBSession.session_id == session_id,
                    DBSession.status == "active"
                ).first()
                
                if not db_session:
                    return {
                        "response": "I'm sorry, your session has expired. Please start a new conversation.",
                        "session_id": session_id,
                        "requires_new_session": True
                    }
                
                self.active_sessions[session_id] = {
                    "created_at": db_session.created_at,
                    "customer_id": db_session.customer_id,
                    "is_verified": db_session.is_verified
                }

            session = self.active_sessions[session_id]
            
            # Check session timeout
            if self._is_session_expired(session_id):
                return {
                    "response": "Your session has timed out for security reasons. Please start a new conversation.",
                    "session_id": session_id,
                    "requires_new_session": True
                }

            # Update session activity
            self._update_session_activity(session_id)
            
            # Save user message to database
            self._save_conversation_message(
                session_id=session_id,
                role="user", 
                message=message,
                customer_id=session.get("customer_id")
            )

            # Get conversation history for context
            conversation_history = self._get_conversation_history(session_id)
            session["conversation_history"] = conversation_history
            
            # Analyze message and determine intent with entities
            intent_analysis = self._analyze_intent(message)
            intent = intent_analysis["primary_intent"]
            entities = intent_analysis.get("entities", {})
            
            # Log intent analysis for debugging
            logger.info(f"Intent analysis: {intent_analysis}")
            
            # Generate response based on intent, entities, and verification status
            response = self._generate_response(session_id, message, intent, session, entities, intent_analysis)
            
            # Save assistant response to database
            import json
            metadata = {
                "intent": intent,
                "tools_used": response.get("tools_used", []),
                "requires_verification": response.get("requires_verification", False),
                "verified": response.get("verified", False)
            }
            self._save_conversation_message(
                session_id=session_id,
                role="assistant",
                message=response["response"],
                customer_id=session.get("customer_id"),
                extra_data=json.dumps(metadata)
            )
            
            self._log_audit(session_id, session.get("customer_id"), "process_message", 
                          f"Intent: {intent}, Response length: {len(response['response'])}", "success")
            
            return response

        except Exception as e:
            self._log_audit(session_id, customer_id, "process_message", 
                          f"Error: {str(e)}", "failed")
            return {
                "response": "I apologize, but I'm experiencing technical difficulties. Please try again or contact customer service.",
                "session_id": session_id,
                "error": True
            }

    def _analyze_intent(self, message: str) -> Dict[str, any]:
        """Analyze customer message to determine intent and extract entities."""
        message_lower = message.lower()
        
        # Enhanced intent detection with confidence scores and entity extraction
        intents = []
        entities = {}
        
        # Identity verification patterns with context awareness
        identity_keywords = ["verify", "identity", "login", "authenticate", "who am i", "my name"]
        identity_score = sum(1 for kw in identity_keywords if kw in message_lower)
        if identity_score > 0:
            intents.append(("identity_verification", identity_score * 0.3))
            
        # Check for name and account patterns
        import re
        account_pattern = r'\b\d{6,}\b'
        account_matches = re.findall(account_pattern, message)
        if account_matches:
            entities['account_number'] = account_matches[0]
            intents.append(("identity_verification", 0.5))
            
        # Balance inquiry patterns with variations
        balance_keywords = ["balance", "how much", "account total", "money", "funds", "available", "checking", "savings"]
        balance_score = sum(1 for kw in balance_keywords if kw in message_lower)
        if balance_score > 0:
            intents.append(("balance_inquiry", balance_score * 0.4))
        
        # Transaction history patterns
        transaction_keywords = ["history", "transactions", "recent", "statements", "spent", "charges", "deposits", "withdrawals", "activity"]
        transaction_score = sum(1 for kw in transaction_keywords if kw in message_lower)
        if transaction_score > 0:
            intents.append(("transaction_history", transaction_score * 0.35))
        
        # Update information patterns with entity extraction
        update_keywords = ["update", "change", "modify", "new", "correct"]
        contact_keywords = ["address", "phone", "email", "number", "contact"]
        update_score = sum(1 for kw in update_keywords if kw in message_lower)
        contact_score = sum(1 for kw in contact_keywords if kw in message_lower)
        if update_score > 0 or contact_score > 0:
            intents.append(("update_information", (update_score + contact_score) * 0.3))
            
            # Extract what needs updating
            if "email" in message_lower:
                entities['update_field'] = 'email'
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                email_matches = re.findall(email_pattern, message)
                if email_matches:
                    entities['new_email'] = email_matches[0]
            if "phone" in message_lower or "number" in message_lower:
                entities['update_field'] = 'phone'
                phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
                phone_matches = re.findall(phone_pattern, message)
                if phone_matches:
                    entities['new_phone'] = phone_matches[0]
            if "address" in message_lower:
                entities['update_field'] = 'address'
        
        # File/document patterns with OCR capability
        file_keywords = ["upload", "document", "file", "statement", "download", "pdf", "attachment", "scan", "image", "photo"]
        ocr_keywords = ["read", "extract", "text", "ocr", "analyze", "check", "receipt"]
        file_score = sum(1 for kw in file_keywords if kw in message_lower)
        ocr_score = sum(1 for kw in ocr_keywords if kw in message_lower)
        
        if file_score > 0 or ocr_score > 0:
            if ocr_score > 0:
                intents.append(("document_ocr", (file_score + ocr_score) * 0.4))
            else:
                intents.append(("file_management", file_score * 0.35))
        
        # Help/support patterns - lower priority
        help_keywords = ["help", "how", "what", "explain", "support", "assist", "can you"]
        help_score = sum(1 for kw in help_keywords if kw in message_lower)
        if help_score > 0:
            intents.append(("general_support", help_score * 0.2))
        
        # Escalation patterns - high priority
        escalation_keywords = ["human", "representative", "manager", "escalate", "complain", "supervisor", "agent", "person", "speak to"]
        escalation_score = sum(1 for kw in escalation_keywords if kw in message_lower)
        if escalation_score > 0:
            intents.append(("escalation", escalation_score * 0.5))
        
        # Greeting patterns
        greeting_keywords = ["hello", "hi", "good morning", "good afternoon", "good evening", "hey", "greetings"]
        if any(kw in message_lower for kw in greeting_keywords) and len(message_lower.split()) < 10:
            intents.append(("greeting", 0.8))
        
        # Sort intents by confidence score
        intents.sort(key=lambda x: x[1], reverse=True)
        
        # Return the highest confidence intent or general_inquiry
        primary_intent = intents[0][0] if intents else "general_inquiry"
        confidence = intents[0][1] if intents else 0.1
        
        return {
            "primary_intent": primary_intent,
            "confidence": confidence,
            "all_intents": intents,
            "entities": entities
        }

    def _generate_response(self, session_id: str, message: str, intent: str, session: Dict, entities: Dict = None, intent_analysis: Dict = None) -> Dict[str, any]:
        """Generate appropriate response based on intent, entities, and context."""
        
        is_verified = session.get("is_verified", False)
        customer_id = session.get("customer_id")
        tools_used = []
        entities = entities or {}
        intent_analysis = intent_analysis or {}
        
        # Check conversation context for follow-up questions
        conversation_history = session.get("conversation_history", [])
        if conversation_history:
            last_message = conversation_history[-1] if conversation_history else None
            if last_message and last_message.get("role") == "assistant":
                # Check if we're waiting for specific information
                if "provide your full name and account number" in last_message.get("message", ""):
                    # Override intent to identity verification if we're waiting for credentials
                    if entities.get("account_number") or "name" in message.lower():
                        intent = "identity_verification"
                        logger.info(f"Context override: Detected identity verification attempt")
        
        # Handle greeting
        if intent == "greeting":
            return {
                "response": f"Hello! I'm NANO, your {settings.bank_name} customer service assistant. How can I help you today?",
                "session_id": session_id,
                "requires_verification": False
            }
        
        # Handle escalation request
        if intent == "escalation":
            result = self.support_tools.escalate_to_human(
                session_id, customer_id, "Customer requested human representative", "normal"
            )
            tools_used.append("escalate_to_human")
            
            if result["success"]:
                return {
                    "response": result["message"],
                    "session_id": session_id,
                    "escalation_id": result["escalation_id"],
                    "tools_used": tools_used
                }
            else:
                return {
                    "response": "I'm having trouble connecting you to a representative right now. Please try calling our customer service line directly.",
                    "session_id": session_id,
                    "tools_used": tools_used
                }
        
        # Check if verification is required for sensitive operations
        sensitive_intents = ["balance_inquiry", "transaction_history", "update_information", "file_management", "document_ocr"]
        
        if intent in sensitive_intents and not is_verified:
            return {
                "response": "I'd be happy to help with that! First, I need to verify your identity for security purposes. Please provide your full name and account number.",
                "session_id": session_id,
                "requires_verification": True,
                "next_intent": intent
            }
        
        # Handle identity verification with extracted entities
        if intent == "identity_verification" or (not is_verified and entities.get("account_number")):
            # Use extracted entities for verification
            return self._handle_identity_verification(session_id, message, session, entities)
        
        # Handle verified requests with entities
        if is_verified and customer_id:
            return self._handle_verified_request(session_id, message, intent, customer_id, session, entities)
        
        # Handle general support
        if intent == "general_support":
            result = self.support_tools.banking_knowledge_base(session_id, customer_id, message)
            tools_used.append("banking_knowledge_base")
            
            if result["success"] and result["results"]:
                info = result["results"][0]
                response = f"Here's information about {info['topic']}:\n\n{info['information']}"
                if info.get("steps"):
                    response += f"\n\nSteps:\n" + "\n".join(f"• {step}" for step in info["steps"])
            else:
                response = "I'd be happy to help! Could you please provide more details about what you're looking for?"
            
            return {
                "response": response,
                "session_id": session_id,
                "tools_used": tools_used
            }
        
        # Default response
        return {
            "response": "I understand you need assistance. Could you please provide more specific information about how I can help you today?",
            "session_id": session_id
        }

    def _handle_identity_verification(self, session_id: str, message: str, session: Dict, entities: Dict = None) -> Dict[str, any]:
        """Handle identity verification process with entity extraction."""
        logger.info(f"_handle_identity_verification called for session {session_id}, awaiting_security_answer={session.get('awaiting_security_answer', False)}, entities={entities}")
        entities = entities or {}
        
        # Use entities if available, otherwise extract
        account_number = entities.get('account_number')
        if not account_number:
            # Fallback to simple extraction
            words = message.split()
            for word in words:
                if word.isdigit() and len(word) >= 6:
                    account_number = word
                    break
        
        # Extract name (assume first few words before account number or common patterns)
        full_name = None
        if "name is" in message.lower():
            name_start = message.lower().find("name is") + 7
            name_part = message[name_start:].split()[:3]  # Take up to 3 words
            # Remove common words that might be included
            clean_words = [word for word in name_part if word.lower() not in ['and', 'my', 'account', 'number']]
            full_name = " ".join(clean_words).strip('.,!?')
        elif account_number:
            # Take words before account number as potential name
            name_words = []
            for word in words:
                if word == account_number:
                    break
                clean_word = word.replace(',', '').replace('.', '')
                if clean_word.isalpha() and clean_word.lower() not in ['my', 'name', 'is', 'and', 'account', 'number']:
                    name_words.append(clean_word)
            if len(name_words) >= 2:
                full_name = " ".join(name_words[-2:])  # Take last 2 words as first, last name
        
        if full_name and account_number:
            result = self.identity_tools.verify_customer_identity(
                session_id, full_name, account_number
            )
            
            if result["verified"]:
                session["is_verified"] = True
                session["customer_id"] = result["customer_id"]
                return {
                    "response": result["message"] + " What can I help you with today?",
                    "session_id": session_id,
                    "verified": True,
                    "customer_id": result["customer_id"],
                    "tools_used": ["verify_customer_identity"]
                }
            elif result.get("requires_security_question"):
                # Store temporary verification data in session
                session["awaiting_security_answer"] = True
                session["temp_customer_id"] = result.get("customer_id")
                session["temp_name"] = full_name
                session["temp_account"] = account_number
                
                return {
                    "response": result["message"],
                    "session_id": session_id,
                    "requires_security_question": True,
                    "customer_id": result.get("customer_id"),
                    "tools_used": ["verify_customer_identity"]
                }
            else:
                return {
                    "response": result["message"],
                    "session_id": session_id,
                    "verification_failed": True,
                    "tools_used": ["verify_customer_identity"]
                }
        
        # Check if this might be a security answer
        if session.get("awaiting_security_answer"):
            customer_id = session.get("temp_customer_id")
            if customer_id:
                logger.info(f"Processing security answer for customer_id={customer_id}")
                result = self.identity_tools.verify_customer_identity(
                    session_id, session.get("temp_name", ""), 
                    session.get("temp_account", ""), message
                )
                
                if result["verified"]:
                    # Clear temporary verification data
                    session["awaiting_security_answer"] = False
                    session.pop("temp_customer_id", None)
                    session.pop("temp_name", None)
                    session.pop("temp_account", None)
                    
                    session["is_verified"] = True
                    session["customer_id"] = result["customer_id"]
                    return {
                        "response": result["message"] + " What can I help you with today?",
                        "session_id": session_id,
                        "verified": True,
                        "customer_id": result["customer_id"],
                        "tools_used": ["verify_customer_identity"]
                    }
                else:
                    # Keep the session state for retry unless max attempts reached
                    if "too many" in result.get("message", "").lower():
                        # Clear session data on max attempts
                        session["awaiting_security_answer"] = False
                        session.pop("temp_customer_id", None)
                        session.pop("temp_name", None)
                        session.pop("temp_account", None)
                    
                    return {
                        "response": result["message"],
                        "session_id": session_id,
                        "verification_failed": True,
                        "tools_used": ["verify_customer_identity"]
                    }
        
        return {
            "response": "To verify your identity, I need your full name and account number. Please provide both in your message.",
            "session_id": session_id,
            "requires_verification": True
        }

    def _handle_verified_request(self, session_id: str, message: str, intent: str, customer_id: str, session: Dict, entities: Dict = None) -> Dict[str, any]:
        """Handle requests from verified customers with entity awareness."""
        tools_used = []
        entities = entities or {}
        
        # Proactively use tools based on intent and entities
        logger.info(f"Handling verified request: intent={intent}, entities={entities}")
        
        if intent == "balance_inquiry":
            result = self.database_tools.query_account_balance(session_id, customer_id)
            tools_used.append("query_account_balance")
            
            if result["success"]:
                response = f"Your current account balance is ${result['current_balance']:.2f}. Is there anything else I can help you with?"
            else:
                response = f"I'm sorry, I couldn't retrieve your balance at this time. {result['message']}"
        
        elif intent == "transaction_history":
            result = self.database_tools.transaction_history(session_id, customer_id, limit=5)
            tools_used.append("transaction_history")
            
            if result["success"] and result["summary"]["total_transactions"] > 0:
                response = f"Here are your recent transactions:\n\n"
                for txn in result["transactions"][:3]:  # Show last 3
                    response += f"• {txn['date']}: {txn['type'].title()} ${txn['amount']:.2f} - {txn['description']}\n"
                response += f"\nTotal transactions in last 30 days: {result['summary']['total_transactions']}"
            else:
                response = "I don't see any recent transactions on your account."
        
        elif intent == "update_information":
            # Check if we have the necessary entities to perform the update
            if entities.get('update_field') and (entities.get('new_email') or entities.get('new_phone')):
                # Proactively update the information
                update_field = entities['update_field']
                updates = {}
                
                if update_field == 'email' and entities.get('new_email'):
                    updates['email'] = entities['new_email']
                elif update_field == 'phone' and entities.get('new_phone'):
                    updates['phone'] = entities['new_phone']
                
                if updates:
                    result = self.database_tools.update_customer_record(session_id, customer_id, updates)
                    tools_used.append("update_customer_record")
                    
                    if result["success"]:
                        response = f"I've successfully updated your {update_field} to {list(updates.values())[0]}. Is there anything else I can help you with?"
                    else:
                        response = f"I encountered an issue updating your {update_field}. {result['message']}"
                else:
                    response = "I can help update your contact information. What would you like to change - your email, phone number, or address? Please provide the new information."
            else:
                response = "I can help update your contact information. What would you like to change - your email, phone number, or address? Please provide the new information."
        
        elif intent == "file_management":
            response = "I can help with document management. Would you like to upload a document, view your existing documents, or organize your files?"
        
        elif intent == "document_ocr":
            response = "I can help you process documents using OCR technology to extract text and banking information. Please upload your document (PDF, image, or scan) and I'll analyze it for you. What type of document would you like me to process?"
        
        else:
            # General inquiry for verified user
            result = self.support_tools.banking_knowledge_base(session_id, customer_id, message)
            tools_used.append("banking_knowledge_base")
            
            if result["success"] and result["results"]:
                info = result["results"][0]
                response = f"Here's information about {info['topic']}:\n\n{info['information']}"
            else:
                response = "I'm here to help with your banking needs. You can ask about your balance, transaction history, update your information, or get general banking assistance."
        
        return {
            "response": response,
            "session_id": session_id,
            "customer_id": customer_id,
            "tools_used": tools_used
        }

    def _is_session_expired(self, session_id: str) -> bool:
        """Check if session has expired."""
        if session_id not in self.active_sessions:
            return True
        
        session = self.active_sessions[session_id]
        session_age = datetime.utcnow() - session["created_at"]
        return session_age > timedelta(minutes=settings.session_timeout_minutes)

    def _update_session_activity(self, session_id: str):
        """Update session last activity time."""
        if session_id in self.active_sessions:
            # Update in-memory session
            self.active_sessions[session_id]["last_activity"] = datetime.utcnow()
            
            # Update database session
            db_session = self.db.query(DBSession).filter(
                DBSession.session_id == session_id
            ).first()
            if db_session:
                db_session.last_activity = datetime.utcnow()
                self.db.commit()

    def _log_audit(self, session_id: str, customer_id: Optional[str], 
                   action: str, details: str, status: str):
        """Log audit trail for agent operations."""
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

    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=settings.session_timeout_minutes)
        
        # Clean up in-memory sessions
        expired_sessions = [
            sid for sid, session in self.active_sessions.items()
            if session["created_at"] < cutoff_time
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        # Update database sessions
        self.db.query(DBSession).filter(
            DBSession.last_activity < cutoff_time,
            DBSession.status == "active"
        ).update({"status": "expired"})
        self.db.commit()

    def _save_conversation_message(self, session_id: str, role: str, message: str, customer_id: Optional[str] = None, extra_data: Optional[str] = None):
        """Save a conversation message to the database."""
        try:
            conversation = Conversation(
                session_id=session_id,
                customer_id=customer_id,
                role=role,
                message=message,
                extra_data=extra_data
            )
            self.db.add(conversation)
            self.db.commit()
            logger.info(f"Saved conversation message: session={session_id}, role={role}, message_length={len(message)}")
        except Exception as e:
            logger.error(f"Failed to save conversation message: {e}")
            self.db.rollback()

    def _get_conversation_history(self, session_id: str, hours: int = 8) -> List[Dict[str, any]]:
        """Get conversation history for the last N hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            conversations = self.db.query(Conversation).filter(
                Conversation.session_id == session_id,
                Conversation.created_at >= cutoff_time
            ).order_by(Conversation.created_at.asc()).all()
            
            history = []
            for conv in conversations:
                history.append({
                    "role": conv.role,
                    "message": conv.message,
                    "timestamp": conv.created_at.isoformat(),
                    "metadata": conv.extra_data
                })
            
            logger.info(f"Retrieved {len(history)} conversation messages for session {session_id}")
            return history
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []


def get_nano_agent(db: Session) -> NANOAgent:
    """Factory function to get NANO agent."""
    return NANOAgent(db)