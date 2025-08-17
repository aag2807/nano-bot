import pytest
import asyncio
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, Customer, Session as DBSession
from nano.agent import NANOAgent


@pytest.fixture
def db_session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Add test customer
    customer = Customer(
        customer_id="test123",
        full_name="John Doe",
        account_number="1234567890",
        email="john@test.com",
        security_question="What is your pet's name?",
        security_answer="fluffy",
        account_balance=1000.00,
        account_status="active"
    )
    session.add(customer)
    session.commit()
    
    yield session
    session.close()


@pytest.fixture
def nano_agent(db_session):
    """Create NANO agent instance for testing."""
    with patch('nano.agent.AutoTokenizer'), patch('nano.agent.AutoModelForCausalLM'):
        agent = NANOAgent(db_session)
        return agent


def test_create_session(nano_agent):
    """Test session creation."""
    session_id = nano_agent.create_session()
    assert session_id is not None
    assert len(session_id) > 0
    assert session_id in nano_agent.active_sessions


def test_greeting_message(nano_agent):
    """Test greeting message processing."""
    session_id = nano_agent.create_session()
    response = nano_agent.process_message(session_id, "Hello")
    
    assert response["session_id"] == session_id
    assert "NANO" in response["response"]
    assert "Bank Of AI" in response["response"]


def test_identity_verification_request(nano_agent):
    """Test identity verification process."""
    session_id = nano_agent.create_session()
    response = nano_agent.process_message(session_id, "What's my balance?")
    
    assert response["requires_verification"] is True
    assert "verify your identity" in response["response"].lower()


def test_successful_identity_verification(nano_agent):
    """Test successful identity verification."""
    session_id = nano_agent.create_session()
    
    # First, request verification
    response1 = nano_agent.process_message(
        session_id, 
        "My name is John Doe and my account number is 1234567890"
    )
    
    assert response1.get("requires_security_question") is True
    
    # Answer security question
    response2 = nano_agent.process_message(session_id, "fluffy")
    
    assert response2.get("verified") is True
    assert "Welcome" in response2["response"]


def test_balance_inquiry_after_verification(nano_agent):
    """Test balance inquiry after successful verification."""
    session_id = nano_agent.create_session()
    
    # Complete verification process
    nano_agent.process_message(
        session_id, 
        "My name is John Doe and my account number is 1234567890"
    )
    nano_agent.process_message(session_id, "fluffy")
    
    # Now request balance
    response = nano_agent.process_message(session_id, "What's my balance?")
    
    assert "$1000.00" in response["response"]
    assert "query_account_balance" in response.get("tools_used", [])


def test_session_expiry(nano_agent):
    """Test session expiry handling."""
    session_id = nano_agent.create_session()
    
    # Mock expired session
    nano_agent.active_sessions[session_id]["created_at"] = \
        nano_agent.active_sessions[session_id]["created_at"].replace(year=2020)
    
    response = nano_agent.process_message(session_id, "Hello")
    
    assert response.get("requires_new_session") is True
    assert "timed out" in response["response"].lower()


def test_escalation_request(nano_agent):
    """Test human escalation."""
    session_id = nano_agent.create_session()
    response = nano_agent.process_message(session_id, "I need to speak to a human")
    
    assert "escalation_id" in response
    assert "ESC-" in response["escalation_id"]
    assert "escalate_to_human" in response.get("tools_used", [])


def test_general_support_query(nano_agent):
    """Test general banking support."""
    session_id = nano_agent.create_session()
    response = nano_agent.process_message(session_id, "How do I transfer money?")
    
    assert "banking_knowledge_base" in response.get("tools_used", [])
    assert len(response["response"]) > 0


def test_invalid_verification_attempts(nano_agent):
    """Test handling of invalid verification attempts."""
    session_id = nano_agent.create_session()
    
    # Try with invalid credentials
    response = nano_agent.process_message(
        session_id, 
        "My name is Invalid User and my account number is 9999999999"
    )
    
    assert response.get("verified") is False
    assert "not found" in response["response"].lower()


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(nano_agent):
    """Test cleanup of expired sessions."""
    # Create some sessions
    session1 = nano_agent.create_session()
    session2 = nano_agent.create_session()
    
    # Mock one as expired
    nano_agent.active_sessions[session1]["created_at"] = \
        nano_agent.active_sessions[session1]["created_at"].replace(year=2020)
    
    # Cleanup
    nano_agent.cleanup_expired_sessions()
    
    # Check that expired session was removed
    assert session1 not in nano_agent.active_sessions
    assert session2 in nano_agent.active_sessions