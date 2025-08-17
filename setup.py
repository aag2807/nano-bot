"""
Setup script for NANO Banking AI.
Run this script to initialize the database and create sample data.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
import uuid

from app.config import settings
from app.database import Base, Customer, Transaction, create_tables
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_sample_customers():
    """Create sample customers for testing."""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Sample customers
        customers = [
            {
                "customer_id": str(uuid.uuid4()),
                "full_name": "John Doe",
                "account_number": "1234567890",
                "email": "john.doe@email.com",
                "phone": "555-0123",
                "address": "123 Main St, City, State 12345",
                "security_question": "What is your pet's name?",
                "security_answer": "fluffy",
                "account_balance": 2500.00,
                "account_status": "active"
            },
            {
                "customer_id": str(uuid.uuid4()),
                "full_name": "Jane Smith",
                "account_number": "2345678901", 
                "email": "jane.smith@email.com",
                "phone": "555-0124",
                "address": "456 Oak Ave, City, State 12345",
                "security_question": "What city were you born in?",
                "security_answer": "chicago",
                "account_balance": 1750.50,
                "account_status": "active"
            },
            {
                "customer_id": str(uuid.uuid4()),
                "full_name": "Bob Johnson",
                "account_number": "3456789012",
                "email": "bob.johnson@email.com", 
                "phone": "555-0125",
                "address": "789 Pine St, City, State 12345",
                "security_question": "What is your mother's maiden name?",
                "security_answer": "williams",
                "account_balance": 3200.75,
                "account_status": "active"
            }
        ]
        
        for customer_data in customers:
            # Check if customer already exists
            existing = db.query(Customer).filter(
                Customer.account_number == customer_data["account_number"]
            ).first()
            
            if not existing:
                customer = Customer(**customer_data)
                db.add(customer)
                print(f"Created customer: {customer_data['full_name']} ({customer_data['account_number']})")
                
                # Add some sample transactions
                transactions = [
                    {
                        "transaction_id": str(uuid.uuid4()),
                        "customer_id": customer_data["customer_id"],
                        "amount": 100.00,
                        "transaction_type": "credit",
                        "description": "Direct Deposit",
                        "balance_after": customer_data["account_balance"] - 50.00,
                        "status": "completed"
                    },
                    {
                        "transaction_id": str(uuid.uuid4()),
                        "customer_id": customer_data["customer_id"],
                        "amount": 50.00,
                        "transaction_type": "debit",
                        "description": "ATM Withdrawal",
                        "balance_after": customer_data["account_balance"],
                        "status": "completed"
                    }
                ]
                
                for txn_data in transactions:
                    transaction = Transaction(**txn_data)
                    db.add(transaction)
        
        db.commit()
        print("Sample data created successfully!")
        
    except Exception as e:
        print(f"Error creating sample data: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Main setup function."""
    print("Setting up NANO Banking AI...")
    
    # Create database tables
    print("Creating database tables...")
    create_tables()
    print("Database tables created")
    
    # Create sample customers
    print("Creating sample customers...")
    create_sample_customers()
    print("Sample customers created")
    
    print("\nSetup complete!")
    print("\nSample customers for testing:")
    print("1. John Doe - Account: 1234567890 - Security Answer: fluffy")
    print("2. Jane Smith - Account: 2345678901 - Security Answer: chicago")
    print("3. Bob Johnson - Account: 3456789012 - Security Answer: williams")
    
    print(f"\nTo start the server:")
    print(f"uvicorn app.main:app --reload --host {settings.host} --port {settings.port}")
    
    print(f"\nAPI will be available at:")
    print(f"http://{settings.host}:{settings.port}/api/v1/chat")
    print(f"http://{settings.host}:{settings.port}/docs (API documentation)")


if __name__ == "__main__":
    main()