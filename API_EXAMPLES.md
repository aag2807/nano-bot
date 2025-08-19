# NANO Banking AI - API Examples

Quick reference for testing the NANO Banking AI API endpoints.

## Base URL
```
http://localhost:8000
```

## Authentication
No authentication required for this proof of concept.

---

## Health Check Endpoints

### Basic Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "service": "NANO Banking AI",
  "version": "1.0.0"
}
```

### Detailed Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health/detailed"
```

---

## Chat Endpoints

### 1. Start a New Conversation
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, I need help with my account"
  }'
```

**Response:**
```json
{
  "response": "Hello! I'm NANO, your Bank of AI customer service assistant. How can I help you today?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "requires_verification": false
}
```

### 2. Check Account Balance (Requires Verification)
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is my account balance?",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response:**
```json
{
  "response": "I'd be happy to help with that! First, I need to verify your identity for security purposes. Please provide your full name and account number.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "requires_verification": true,
  "next_intent": "balance_inquiry"
}
```

### 3. Provide Identity Verification
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "My name is John Doe and my account number is 123456789",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response (Successful Verification):**
```json
{
  "response": "Thank you, Mr. Doe. I've verified your identity. Your current account balance is $2,547.83. What can I help you with today?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "verified": true,
  "customer_id": "cust_123456789",
  "tools_used": ["verify_customer_identity", "query_account_balance"]
}
```

### 4. Get Transaction History
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me my recent transactions",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response:**
```json
{
  "response": "Here are your recent transactions:\n\n• 2024-01-14: Deposit $1,200.00 - Salary Direct Deposit\n• 2024-01-13: Withdrawal $45.50 - ATM Withdrawal\n• 2024-01-12: Purchase $23.99 - Online Purchase\n\nTotal transactions in last 30 days: 15",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "cust_123456789",
  "tools_used": ["transaction_history"]
}
```

### 5. Update Contact Information
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to update my email to john.doe@newemail.com",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response:**
```json
{
  "response": "I've successfully updated your email to john.doe@newemail.com. Is there anything else I can help you with?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "cust_123456789",
  "tools_used": ["update_customer_record"]
}
```

### 6. Request Human Agent
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to speak with a human representative",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Response:**
```json
{
  "response": "I'm connecting you with a human representative. Your escalation ID is ESC-789123. A representative will be with you shortly.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "escalation_id": "ESC-789123",
  "tools_used": ["escalate_to_human"]
}
```

---

## Session Management

### Create New Session
```bash
curl -X POST "http://localhost:8000/api/v1/session" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust_123456789"
  }'
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "New session created successfully"
}
```

### End Session
```bash
curl -X DELETE "http://localhost:8000/api/v1/session/550e8400-e29b-41d4-a716-446655440000"
```

**Response:**
```json
{
  "message": "Session ended successfully"
}
```

### Get Session Summary
```bash
curl -X GET "http://localhost:8000/api/v1/session/550e8400-e29b-41d4-a716-446655440000/summary"
```

---

## Error Responses

### Invalid Session
```json
{
  "response": "I'm sorry, your session has expired. Please start a new conversation.",
  "session_id": "invalid-session-id",
  "requires_new_session": true
}
```

### Verification Failed
```json
{
  "response": "I'm sorry, but I couldn't verify your identity with the information provided. Please check your name and account number and try again.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "verification_failed": true,
  "tools_used": ["verify_customer_identity"]
}
```

### Server Error
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred. Please try again later.",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

---

## Testing Flow

1. **Start with health check** to ensure service is running
2. **Begin conversation** with a greeting
3. **Request sensitive information** (triggers verification)
4. **Provide credentials** to verify identity
5. **Use banking features** (balance, transactions, updates)
6. **Test escalation** if needed

## Sample Test Customers

For testing purposes, these mock customers are available:

- **Name:** John Doe, **Account:** 123456789
- **Name:** Jane Smith, **Account:** 987654321
- **Name:** Bob Johnson, **Account:** 555666777

---

## Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.