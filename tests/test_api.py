import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, Customer, Transaction, Session, Document, AuditLog, Conversation, get_db


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            # Add test customer
            customer = Customer(
                customer_id="test123",
                full_name="John Doe", 
                account_number="1234567890",
                email="john@test.com",
                security_question="What is your pet's name?",
                security_answer="fluffy",
                account_balance=1500.00,
                account_status="active"
            )
            db.add(customer)
            db.commit()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """Create test client."""
    with patch('nano.agent.AutoTokenizer'), patch('nano.agent.AutoModelForCausalLM'):
        return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "NANO Banking AI"
    assert "endpoints" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "NANO Banking AI"


def test_detailed_health_check(client):
    """Test detailed health check."""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data
    assert data["checks"]["database"]["status"] == "healthy"


def test_api_info(client):
    """Test API information endpoint."""
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert "capabilities" in data
    assert "Identity Verification" in data["capabilities"]


def test_create_session(client):
    """Test session creation endpoint."""
    response = client.post("/api/v1/session", json={})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["message"] == "New session created successfully"


def test_chat_greeting(client):
    """Test chat endpoint with greeting."""
    response = client.post("/api/v1/chat", json={
        "message": "Hello"
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "NANO" in data["response"]
    assert "Bank Of AI" in data["response"]


def test_chat_balance_request_without_verification(client):
    """Test balance request without verification."""
    response = client.post("/api/v1/chat", json={
        "message": "What's my balance?"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["requires_verification"] is True
    assert "verify your identity" in data["response"].lower()


def test_chat_with_session_id(client):
    """Test chat with existing session ID."""
    # First create a session
    session_response = client.post("/api/v1/session", json={})
    session_id = session_response.json()["session_id"]
    
    # Use the session ID in chat
    response = client.post("/api/v1/chat", json={
        "message": "Hello",
        "session_id": session_id
    })
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id


def test_chat_verification_process(client):
    """Test complete verification process."""
    # Start with identity verification
    response1 = client.post("/api/v1/chat", json={
        "message": "My name is John Doe and my account number is 1234567890"
    })
    assert response1.status_code == 200
    data1 = response1.json()
    session_id = data1["session_id"]
    
    # Should ask for security question
    assert data1.get("requires_security_question") is True
    
    # Answer security question
    response2 = client.post("/api/v1/chat", json={
        "message": "fluffy",
        "session_id": session_id
    })
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2.get("verified") is True


def test_chat_input_validation(client):
    """Test input validation."""
    # Test empty message
    response = client.post("/api/v1/chat", json={
        "message": ""
    })
    assert response.status_code == 422  # Validation error
    
    # Test very long message
    long_message = "A" * 3000
    response = client.post("/api/v1/chat", json={
        "message": long_message
    })
    assert response.status_code == 422  # Validation error


def test_chat_invalid_session_id(client):
    """Test invalid session ID format."""
    response = client.post("/api/v1/chat", json={
        "message": "Hello",
        "session_id": "invalid-session-id"
    })
    assert response.status_code == 422  # Validation error


def test_escalation_request(client):
    """Test human escalation request."""
    response = client.post("/api/v1/chat", json={
        "message": "I want to speak to a human representative"
    })
    assert response.status_code == 200
    data = response.json()
    assert "escalation_id" in data
    assert "ESC-" in data["escalation_id"]


def test_end_session(client):
    """Test ending a session."""
    # Create session first
    session_response = client.post("/api/v1/session", json={})
    session_id = session_response.json()["session_id"]
    
    # End the session
    response = client.delete(f"/api/v1/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Session ended successfully"


def test_session_summary(client):
    """Test getting session summary."""
    # Create session and have some interaction
    session_response = client.post("/api/v1/session", json={})
    session_id = session_response.json()["session_id"]
    
    # Have some chat interactions
    client.post("/api/v1/chat", json={
        "message": "Hello",
        "session_id": session_id
    })
    
    # Get summary
    response = client.get(f"/api/v1/session/{session_id}/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "duration_minutes" in data


def test_rate_limiting(client):
    """Test rate limiting middleware."""
    # This would need to be adjusted based on rate limit settings
    # For now, just test that multiple requests don't immediately fail
    for i in range(5):
        response = client.get("/api/v1/health")
        assert response.status_code == 200


def test_security_headers(client):
    """Test security headers are present."""
    response = client.get("/api/v1/health")
    
    # Check for security headers
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "X-XSS-Protection" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_cors_headers(client):
    """Test CORS headers."""
    response = client.options("/api/v1/health", headers={
        "Access-Control-Request-Method": "GET",
        "Origin": "http://localhost:3000"
    })
    # CORS headers should be present for OPTIONS requests
    assert "Access-Control-Allow-Origin" in response.headers


@pytest.mark.asyncio
async def test_concurrent_requests(client):
    """Test handling concurrent requests."""
    import asyncio
    from httpx import AsyncClient
    
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Send multiple concurrent requests
        tasks = []
        for i in range(10):
            task = ac.post("/api/v1/chat", json={"message": f"Hello {i}"})
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data
            assert "NANO" in data["response"]