#!/usr/bin/env python3
"""
Test script to demonstrate improved agent capabilities:
1. Better context awareness
2. Proactive tool usage
3. Entity extraction
4. Multi-intent detection
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, Customer, Transaction
from nano.simple_agent import SimpleNANOAgent
from datetime import datetime, timedelta
import random

def setup_test_database():
    """Create a test database with sample data."""
    engine = create_engine("sqlite:///test_nano.db", echo=False)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Clear existing data
    db.query(Customer).delete()
    db.query(Transaction).delete()
    
    # Create test customers
    customers = [
        Customer(
            customer_id="CUST001",
            full_name="John Smith",
            account_number="123456",
            email="john.smith@email.com",
            phone="555-0123",
            address="123 Main St, Anytown, USA",
            account_balance=5000.00,
            security_question="What is your mother's maiden name?",
            security_answer="Johnson"
        ),
        Customer(
            customer_id="CUST002",
            full_name="Jane Doe",
            account_number="789012",
            email="jane.doe@email.com",
            phone="555-0456",
            address="456 Oak Ave, Somewhere, USA",
            account_balance=10000.00,
            security_question="What was your first pet's name?",
            security_answer="Fluffy"
        )
    ]
    
    for customer in customers:
        db.add(customer)
    
    # Create test transactions for John Smith
    base_date = datetime.now()
    transactions = [
        Transaction(
            transaction_id=f"TXN00{i}",
            customer_id="CUST001",
            transaction_type="deposit" if i % 3 == 0 else "withdrawal",
            amount=random.uniform(50, 500),
            description=f"Transaction {i}",
            balance_after=5000.00 + random.uniform(-100, 100),
            created_at=base_date - timedelta(days=i)
        )
        for i in range(1, 11)
    ]
    
    for txn in transactions:
        db.add(txn)
    
    db.commit()
    db.close()
    
    return engine

def test_conversation_scenarios(engine):
    """Test various conversation scenarios."""
    Session = sessionmaker(bind=engine)
    
    print("=" * 60)
    print("TESTING IMPROVED NANO AGENT")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "Context-aware identity verification",
            "messages": [
                "Hi, I need to check my account balance",
                "My name is John Smith and my account number is 123456",
                "Johnson"  # Security answer
            ]
        },
        {
            "name": "Proactive information update",
            "messages": [
                "Hello",
                "John Smith 123456",
                "Johnson",
                "I need to update my email to john.new@email.com"
            ]
        },
        {
            "name": "Entity extraction with transaction history",
            "messages": [
                "Good morning",
                "I'm Jane Doe, account 789012",
                "Fluffy",
                "Show me my recent transactions and current balance"
            ]
        },
        {
            "name": "Multi-intent handling",
            "messages": [
                "Hi there",
                "John Smith, 123456",
                "Johnson",
                "What's my balance and can you update my phone to 555-9999?"
            ]
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'='*60}")
        
        # Create new session for each scenario
        db = Session()
        agent = SimpleNANOAgent(db)
        session_id = agent.create_session()
        
        for msg in scenario['messages']:
            print(f"\nCustomer: {msg}")
            response = agent.process_message(session_id, msg)
            print(f"NANO: {response['response']}")
            
            # Show tools used if any
            if response.get('tools_used'):
                print(f"   [Tools used: {', '.join(response['tools_used'])}]")
            
            # Show verification status
            if response.get('verified'):
                print(f"   [Customer verified]")
            if response.get('requires_verification'):
                print(f"   [Verification required]")
        
        db.close()
    
    print(f"\n{'='*60}")
    print("TEST COMPLETED")
    print(f"{'='*60}")

def main():
    """Main test function."""
    print("Setting up test database...")
    engine = setup_test_database()
    
    print("Running conversation scenarios...")
    test_conversation_scenarios(engine)
    
    print("\nKey improvements demonstrated:")
    print("1. Better context awareness - remembers conversation state")
    print("2. Proactive tool usage - automatically calls tools when entities detected")
    print("3. Entity extraction - extracts emails, phone numbers, account numbers")
    print("4. Multi-intent detection - handles multiple requests in one message")
    print("5. Confidence scoring - prioritizes intents based on keyword matches")

if __name__ == "__main__":
    main()