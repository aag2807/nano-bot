# NANO Customer Service AI - Technical README

## Project Overview

NANO is a professional customer service AI assistant for Bank of AI, built using HuggingFaceTB/SmolLM2-1.7B-Instruct. The system provides secure banking assistance with integrated tool execution capabilities for identity verification, file management, database operations, and general customer support.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   LangChain     │    │   SmolLM2       │
│   Web Server    │◄──►│   Tool Chain    │◄──►│   1.7B Instruct │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       
         ▼                       ▼                       
┌─────────────────┐    ┌─────────────────┐              
│   Database      │    │   File System   │              
│   (PostgreSQL)  │    │   Management    │              
└─────────────────┘    └─────────────────┘              
```

## Tech Stack

- **AI Model**: HuggingFaceTB/SmolLM2-1.7B-Instruct
- **Framework**: LangChain for tool orchestration
- **API**: FastAPI for REST endpoints
- **Database**: PostgreSQL (recommended) or SQLite for development
- **File Storage**: Local filesystem with organized directory structure
- **Language**: Python 3.9+

## Core Components

### 1. AI Agent (NANO)
- **Model**: SmolLM2-1.7B-Instruct via HuggingFace Transformers
- **Role**: Customer service representative with banking domain knowledge
- **Security**: Identity verification enforcement before sensitive operations

### 2. Tool System
Four primary tool categories:

#### Identity Verification Tools
- `verify_customer_identity()`: Multi-factor authentication
- `validate_security_question()`: Security question verification
- `check_account_status()`: Account validity verification

#### File Management Tools
- `create_customer_folder()`: Organize customer documents
- `upload_document()`: Handle document uploads
- `retrieve_document()`: Secure document access
- `archive_document()`: Document lifecycle management

#### Database Operations Tools
- `update_customer_record()`: Modify customer information
- `query_account_balance()`: Retrieve account balances
- `transaction_history()`: Access transaction records
- `update_contact_info()`: Modify customer contact details

#### General Support Tools
- `banking_knowledge_base()`: Access banking procedures
- `escalate_to_human()`: Transfer to human representative
- `generate_summary()`: Create interaction summaries

### 3. Security Layer
- Identity verification middleware
- Request logging and audit trails
- Rate limiting and abuse prevention
- Encrypted data handling

## Installation & Setup

### Prerequisites
```bash
python >= 3.9
pip >= 21.0
```

### Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd nano-customer-service-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Required Dependencies
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
langchain==0.0.350
langchain-huggingface==0.0.3
transformers==4.36.0
torch>=2.0.0
psycopg2-binary==2.9.9  # For PostgreSQL
sqlalchemy==2.0.23
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

### Database Setup

#### Option 1: PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib  # Ubuntu
brew install postgresql  # macOS

# Create database
sudo -u postgres createdb nano_banking_db

# Set environment variables
export DATABASE_URL="postgresql://username:password@localhost/nano_banking_db"
```

#### Option 2: SQLite (Development)
```python
# In config.py
DATABASE_URL = "sqlite:///./nano_banking.db"
```

### Configuration
Create `.env` file:
```env
# Database
DATABASE_URL=postgresql://username:password@localhost/nano_banking_db

# HuggingFace
HF_MODEL_NAME=HuggingFaceTB/SmolLM2-1.7B-Instruct
HF_TOKEN=your_huggingface_token  # Optional for public models

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Storage
CUSTOMER_FILES_PATH=./customer_files
MAX_FILE_SIZE_MB=10

# API Settings
HOST=0.0.0.0
PORT=8000
DEBUG=False
```

## Project Structure

```
nano-customer-service-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py              # Configuration settings
│   ├── database.py            # Database connection and models
│   └── api/
│       ├── __init__.py
│       ├── endpoints/
│       │   ├── chat.py        # Chat endpoint
│       │   └── health.py      # Health check
│       └── middleware/
│           ├── auth.py        # Authentication middleware
│           └── logging.py     # Request logging
├── nano/
│   ├── __init__.py
│   ├── agent.py              # Main NANO agent class
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── identity.py       # Identity verification tools
│   │   ├── files.py          # File management tools
│   │   ├── database.py       # Database operation tools
│   │   └── support.py        # General support tools
│   ├── prompts/
│   │   ├── system_prompt.py  # NANO system prompt
│   │   └── tool_prompts.py   # Tool-specific prompts
│   └── utils/
│       ├── security.py       # Security utilities
│       └── validation.py     # Input validation
├── database/
│   ├── migrations/           # Database migration files
│   └── schemas/              # Database schemas
├── customer_files/           # Customer document storage
├── tests/
│   ├── test_agent.py
│   ├── test_tools.py
│   └── test_api.py
├── requirements.txt
├── .env.example
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Chat Endpoint
```http
POST /api/v1/chat
Content-Type: application/json

{
  "message": "What's my account balance?",
  "session_id": "unique-session-id",
  "customer_id": "optional-customer-id"
}
```

### Health Check
```http
GET /api/v1/health
```

## Usage Examples

### Starting the Server
```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Sample Conversation Flow
```python
# Customer initiates chat
POST /api/v1/chat
{
  "message": "Hi, I need to check my account balance",
  "session_id": "session_123"
}

# NANO responds with identity verification request
{
  "response": "Hello! I'm NANO, your Bank of AI assistant. I'd be happy to help with your account balance. First, I need to verify your identity. Please provide your full name and account number.",
  "requires_verification": true,
  "session_id": "session_123"
}

# Customer provides verification info
POST /api/v1/chat
{
  "message": "My name is John Doe and my account number is 123456789",
  "session_id": "session_123"
}

# NANO verifies and provides balance
{
  "response": "Thank you, Mr. Doe. I've verified your identity. Your current account balance is $2,547.83. Is there anything else I can help you with today?",
  "tools_used": ["verify_customer_identity", "query_account_balance"],
  "session_id": "session_123"
}
```

## Security Features

1. **Identity Verification**: Multi-step verification process
2. **Session Management**: Secure session handling
3. **Audit Logging**: Complete interaction logging
4. **Data Encryption**: Sensitive data encryption at rest
5. **Rate Limiting**: API rate limiting protection
6. **Input Validation**: Comprehensive input sanitization

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=nano --cov-report=html

# Run specific test categories
pytest tests/test_tools.py -v
```

## Deployment

### Docker Deployment
```bash
# Build container
docker build -t nano-ai .

# Run with docker-compose
docker-compose up -d
```

### Environment Variables for Production
- Set `DEBUG=False`
- Use secure `SECRET_KEY`
- Configure production database
- Set up proper logging
- Enable HTTPS/SSL

## Performance Considerations

- **Model Loading**: SmolLM2-1.7B loads quickly but consider caching
- **Database Connections**: Use connection pooling
- **File Storage**: Consider cloud storage for production
- **Caching**: Implement Redis for session caching
- **Scaling**: Use load balancer for multiple instances

## Monitoring and Logging

- Request/response logging
- Tool usage analytics
- Error tracking and alerting
- Performance metrics
- Security audit trails

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure security compliance
5. Submit pull request

## License

[Your License Here]

---

**Note**: This is a banking AI system handling sensitive financial data. Ensure compliance with relevant financial regulations (PCI DSS, GDPR, etc.) before production deployment.
