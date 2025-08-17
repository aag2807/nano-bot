import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, Customer, Transaction, Document
from nano.tools.identity import get_identity_tools
from nano.tools.database import get_database_tools
from nano.tools.files import get_file_tools
from nano.tools.support import get_support_tools
import tempfile
import os


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
        account_balance=2000.00,
        account_status="active"
    )
    session.add(customer)
    session.commit()
    
    yield session
    session.close()


class TestIdentityVerificationTools:
    """Test identity verification tools."""
    
    def test_successful_verification(self, db_session):
        """Test successful identity verification."""
        tools = get_identity_tools(db_session)
        
        # First step - provide name and account
        result = tools.verify_customer_identity(
            session_id="test-session",
            full_name="John Doe",
            account_number="1234567890"
        )
        
        assert result["requires_security_question"] is True
        assert "pet's name" in result["message"]
        
        # Second step - answer security question
        result2 = tools.verify_customer_identity(
            session_id="test-session",
            full_name="John Doe", 
            account_number="1234567890",
            security_answer="fluffy"
        )
        
        assert result2["verified"] is True
        assert result2["customer_id"] == "test123"
    
    def test_invalid_customer(self, db_session):
        """Test verification with invalid customer."""
        tools = get_identity_tools(db_session)
        
        result = tools.verify_customer_identity(
            session_id="test-session",
            full_name="Invalid User",
            account_number="9999999999"
        )
        
        assert result["verified"] is False
        assert "not found" in result["message"]
    
    def test_incorrect_security_answer(self, db_session):
        """Test incorrect security answer."""
        tools = get_identity_tools(db_session)
        
        result = tools.verify_customer_identity(
            session_id="test-session",
            full_name="John Doe",
            account_number="1234567890",
            security_answer="wrong answer"
        )
        
        assert result["verified"] is False
        assert "Incorrect" in result["message"]
    
    def test_account_status_check(self, db_session):
        """Test account status check."""
        tools = get_identity_tools(db_session)
        
        result = tools.check_account_status("test123")
        
        assert result["status"] == "active"
        assert result["customer_name"] == "John Doe"
        assert result["account_number"] == "1234567890"


class TestDatabaseOperationTools:
    """Test database operation tools."""
    
    def test_query_account_balance(self, db_session):
        """Test account balance query."""
        tools = get_database_tools(db_session)
        
        result = tools.query_account_balance("test-session", "test123")
        
        assert result["success"] is True
        assert result["current_balance"] == 2000.00
        assert result["customer_name"] == "John Doe"
    
    def test_update_contact_info(self, db_session):
        """Test updating contact information."""
        tools = get_database_tools(db_session)
        
        result = tools.update_contact_info(
            session_id="test-session",
            customer_id="test123",
            email="newemail@test.com",
            phone="555-0123"
        )
        
        assert result["success"] is True
        assert "email" in result["updated_fields"]
        assert "phone" in result["updated_fields"]
        
        # Verify the update
        customer = db_session.query(Customer).filter(
            Customer.customer_id == "test123"
        ).first()
        assert customer.email == "newemail@test.com"
        assert customer.phone == "555-0123"
    
    def test_create_transaction(self, db_session):
        """Test transaction creation."""
        tools = get_database_tools(db_session)
        
        result = tools.create_transaction(
            session_id="test-session",
            customer_id="test123",
            amount=100.00,
            transaction_type="credit",
            description="Test deposit"
        )
        
        assert result["success"] is True
        assert result["amount"] == 100.00
        assert result["new_balance"] == 2100.00
        
        # Verify transaction was created
        transaction = db_session.query(Transaction).filter(
            Transaction.customer_id == "test123"
        ).first()
        assert transaction is not None
        assert transaction.amount == 100.00
        assert transaction.transaction_type == "credit"
    
    def test_insufficient_funds_transaction(self, db_session):
        """Test transaction with insufficient funds."""
        tools = get_database_tools(db_session)
        
        result = tools.create_transaction(
            session_id="test-session",
            customer_id="test123",
            amount=3000.00,  # More than balance
            transaction_type="debit",
            description="Large withdrawal"
        )
        
        assert result["success"] is False
        assert "Insufficient funds" in result["message"]
    
    def test_transaction_history(self, db_session):
        """Test transaction history retrieval."""
        tools = get_database_tools(db_session)
        
        # Create some test transactions first
        tools.create_transaction("test-session", "test123", 50.0, "credit", "Test 1")
        tools.create_transaction("test-session", "test123", 25.0, "debit", "Test 2")
        
        result = tools.transaction_history("test-session", "test123")
        
        assert result["success"] is True
        assert len(result["transactions"]) == 2
        assert result["summary"]["total_transactions"] == 2


class TestFileManagementTools:
    """Test file management tools."""
    
    def test_create_customer_folder(self, db_session):
        """Test customer folder creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock settings for file path
            import app.config
            original_path = app.config.settings.customer_files_path
            app.config.settings.customer_files_path = temp_dir
            
            try:
                tools = get_file_tools(db_session)
                result = tools.create_customer_folder("test-session", "test123")
                
                assert result["success"] is True
                assert os.path.exists(os.path.join(temp_dir, "test123"))
                assert os.path.exists(os.path.join(temp_dir, "test123", "statements"))
                
            finally:
                app.config.settings.customer_files_path = original_path
    
    def test_upload_document(self, db_session):
        """Test document upload."""
        with tempfile.TemporaryDirectory() as temp_dir:
            import app.config
            original_path = app.config.settings.customer_files_path
            app.config.settings.customer_files_path = temp_dir
            
            try:
                tools = get_file_tools(db_session)
                
                # Test file content
                test_content = b"This is a test PDF content"
                
                result = tools.upload_document(
                    session_id="test-session",
                    customer_id="test123",
                    file_content=test_content,
                    filename="test_document.pdf",
                    document_type="statements"
                )
                
                assert result["success"] is True
                assert "document_id" in result
                assert result["file_size"] == len(test_content)
                
                # Verify document record in database
                document = db_session.query(Document).filter(
                    Document.customer_id == "test123"
                ).first()
                assert document is not None
                assert document.filename == "test_document.pdf"
                
            finally:
                app.config.settings.customer_files_path = original_path
    
    def test_upload_oversized_file(self, db_session):
        """Test upload of oversized file."""
        tools = get_file_tools(db_session)
        
        # Create content larger than max size (10MB default)
        large_content = b"A" * (11 * 1024 * 1024)  # 11MB
        
        result = tools.upload_document(
            session_id="test-session",
            customer_id="test123",
            file_content=large_content,
            filename="large_file.pdf"
        )
        
        assert result["success"] is False
        assert "too large" in result["message"]
    
    def test_list_customer_documents(self, db_session):
        """Test listing customer documents."""
        # First add a document to the database
        document = Document(
            document_id="doc123",
            customer_id="test123",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="active"
        )
        db_session.add(document)
        db_session.commit()
        
        tools = get_file_tools(db_session)
        result = tools.list_customer_documents("test-session", "test123")
        
        assert result["success"] is True
        assert result["total_count"] == 1
        assert result["documents"][0]["filename"] == "test.pdf"


class TestGeneralSupportTools:
    """Test general support tools."""
    
    def test_banking_knowledge_base(self, db_session):
        """Test banking knowledge base search."""
        tools = get_support_tools(db_session)
        
        result = tools.banking_knowledge_base(
            session_id="test-session",
            customer_id="test123",
            query="account balance"
        )
        
        assert result["success"] is True
        assert len(result["results"]) > 0
        # Should find balance-related information
        assert any("balance" in r["topic"].lower() for r in result["results"])
    
    def test_escalate_to_human(self, db_session):
        """Test human escalation."""
        tools = get_support_tools(db_session)
        
        result = tools.escalate_to_human(
            session_id="test-session",
            customer_id="test123",
            reason="Complex account issue",
            priority="high"
        )
        
        assert result["success"] is True
        assert "escalation_id" in result
        assert result["priority"] == "high"
        assert "ESC-" in result["escalation_id"]
    
    def test_generate_summary(self, db_session):
        """Test interaction summary generation."""
        # First create some audit logs
        from app.database import AuditLog
        from datetime import datetime
        
        log1 = AuditLog(
            session_id="test-session",
            customer_id="test123",
            action="identity_verification",
            details="Successful verification",
            status="success",
            timestamp=datetime.utcnow()
        )
        log2 = AuditLog(
            session_id="test-session", 
            customer_id="test123",
            action="query_account_balance",
            details="Balance inquiry",
            status="success",
            timestamp=datetime.utcnow()
        )
        
        db_session.add(log1)
        db_session.add(log2)
        db_session.commit()
        
        tools = get_support_tools(db_session)
        result = tools.generate_summary("test-session", "test123")
        
        assert result["success"] is True
        assert result["summary"]["session_id"] == "test-session"
        assert result["summary"]["total_actions"] == 2
        assert result["summary"]["successful_actions"] == 2
        assert "identity_verification" in result["summary"]["tools_used"]
        assert "query_account_balance" in result["summary"]["tools_used"]