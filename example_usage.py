"""
Example usage of the NANO Banking AI API.
This script demonstrates how to interact with the API programmatically.
"""

import requests
import json
import time
from typing import Optional


class NANOAPIClient:
    """Client for interacting with NANO Banking AI API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id: Optional[str] = None
    
    def create_session(self) -> str:
        """Create a new chat session."""
        response = requests.post(f"{self.base_url}/api/v1/session", json={})
        if response.status_code == 200:
            self.session_id = response.json()["session_id"]
            print(f"✅ Created session: {self.session_id}")
            return self.session_id
        else:
            raise Exception(f"Failed to create session: {response.text}")
    
    def send_message(self, message: str) -> dict:
        """Send a message to NANO."""
        if not self.session_id:
            self.create_session()
        
        payload = {
            "message": message,
            "session_id": self.session_id
        }
        
        response = requests.post(f"{self.base_url}/api/v1/chat", json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to send message: {response.text}")
    
    def chat_conversation(self, messages: list):
        """Have a conversation with NANO."""
        print("🤖 Starting conversation with NANO...")
        print("=" * 50)
        
        for i, message in enumerate(messages):
            print(f"\n👤 User: {message}")
            
            try:
                response = self.send_message(message)
                print(f"🤖 NANO: {response['response']}")
                
                # Show additional info if available
                if response.get("requires_verification"):
                    print("ℹ️  Identity verification required")
                
                if response.get("requires_security_question"):
                    print("ℹ️  Security question required")
                
                if response.get("verified"):
                    print("✅ Identity verified successfully")
                
                if response.get("tools_used"):
                    print(f"🔧 Tools used: {', '.join(response['tools_used'])}")
                
                if response.get("escalation_id"):
                    print(f"📞 Escalation ID: {response['escalation_id']}")
                
                # Small delay between messages
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                break
    
    def get_health_status(self) -> dict:
        """Get API health status."""
        response = requests.get(f"{self.base_url}/api/v1/health")
        return response.json()
    
    def get_session_summary(self) -> dict:
        """Get summary of current session."""
        if not self.session_id:
            raise Exception("No active session")
        
        response = requests.get(f"{self.base_url}/api/v1/session/{self.session_id}/summary")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get summary: {response.text}")


def main():
    """Main demo function."""
    print("🏦 NANO Banking AI - Example Usage")
    print("=" * 40)
    
    # Initialize client
    client = NANOAPIClient()
    
    # Check API health
    try:
        health = client.get_health_status()
        print(f"API Status: {health['status']}")
        print(f"Service: {health['service']}")
    except Exception as e:
        print(f"❌ API not available: {e}")
        return
    
    # Example 1: Greeting and general inquiry
    print("\n📋 Example 1: Greeting and Balance Inquiry")
    conversation1 = [
        "Hello",
        "What's my account balance?",
        "My name is John Doe and my account number is 1234567890",
        "fluffy"  # Security answer
    ]
    client.chat_conversation(conversation1)
    
    # Example 2: Transaction history
    print("\n📋 Example 2: Transaction History")
    client2 = NANOAPIClient()
    conversation2 = [
        "I need to see my recent transactions",
        "John Doe, account 1234567890",
        "fluffy",
        "Show me the last 5 transactions"
    ]
    client2.chat_conversation(conversation2)
    
    # Example 3: Update contact information
    print("\n📋 Example 3: Update Contact Information")
    client3 = NANOAPIClient()
    conversation3 = [
        "I need to update my email address",
        "John Doe, account 1234567890", 
        "fluffy",
        "Please update my email to newemail@example.com"
    ]
    client3.chat_conversation(conversation3)
    
    # Example 4: General banking support
    print("\n📋 Example 4: General Banking Support")
    client4 = NANOAPIClient()
    conversation4 = [
        "How do I transfer money to another account?",
        "What are your banking hours?",
        "I need help with online banking"
    ]
    client4.chat_conversation(conversation4)
    
    # Example 5: Human escalation
    print("\n📋 Example 5: Human Escalation")
    client5 = NANOAPIClient()
    conversation5 = [
        "I have a complex issue and need to speak to a human representative",
    ]
    client5.chat_conversation(conversation5)
    
    # Get session summary
    try:
        print("\n📊 Session Summary:")
        summary = client.get_session_summary()
        print(f"Duration: {summary['duration_minutes']} minutes")
        print(f"Total actions: {summary['total_actions']}")
        print(f"Tools used: {', '.join(summary['tools_used'])}")
        print(f"Verification status: {summary['verification_status']}")
    except Exception as e:
        print(f"Could not get session summary: {e}")
    
    print("\n✅ Demo completed!")


def quick_test():
    """Quick test to verify API is working."""
    print("🧪 Quick API Test")
    
    client = NANOAPIClient()
    
    try:
        # Health check
        health = client.get_health_status()
        print(f"✅ Health check: {health['status']}")
        
        # Simple greeting
        response = client.send_message("Hello")
        print(f"✅ Chat response received: {len(response['response'])} characters")
        
        print("🎉 API is working correctly!")
        
    except Exception as e:
        print(f"❌ API test failed: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        quick_test()
    else:
        main()