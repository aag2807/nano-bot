from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from typing import Optional, List
from app.database import get_db, create_tables
from app.api.middleware.auth import input_validator

# Try to import full agent, fallback to simple agent
try:
    from nano.agent import get_nano_agent
except ImportError:
    print("Full AI agent not available, using simple agent")
    from nano.simple_agent import get_simple_nano_agent as get_nano_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    customer_id: Optional[str] = None
    
    @validator('message')
    def validate_message(cls, v):
        is_valid, error_msg = input_validator.validate_customer_message(v)
        if not is_valid:
            raise ValueError(error_msg)
        return input_validator.sanitize_string(v, 2000)
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if v and not input_validator.validate_session_id(v):
            raise ValueError("Invalid session ID format")
        return v


class ChatResponse(BaseModel):
    response: str
    session_id: str
    requires_verification: Optional[bool] = None
    requires_security_question: Optional[bool] = None
    verified: Optional[bool] = None
    customer_id: Optional[str] = None
    escalation_id: Optional[str] = None
    tools_used: Optional[List[str]] = None
    error: Optional[bool] = None
    requires_new_session: Optional[bool] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Main chat endpoint for customer interactions with NANO.
    """
    try:
        # Ensure database tables exist
        create_tables()
        
        # Get NANO agent instance
        agent = get_nano_agent(db)
        
        # Create new session if none provided
        session_id = request.session_id
        if not session_id:
            session_id = agent.create_session(request.customer_id)
        
        # Process the message
        result = agent.process_message(
            session_id=session_id,
            message=request.message,
            customer_id=request.customer_id
        )
        
        return ChatResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )


class SessionRequest(BaseModel):
    customer_id: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    message: str


@router.post("/session", response_model=SessionResponse)
async def create_session_endpoint(
    request: SessionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new chat session.
    """
    try:
        agent = get_nano_agent(db)
        session_id = agent.create_session(request.customer_id)
        
        return SessionResponse(
            session_id=session_id,
            message="New session created successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session creation failed: {str(e)}"
        )


@router.delete("/session/{session_id}")
async def end_session_endpoint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    End a chat session.
    """
    try:
        # Update session status in database
        from app.database import Session as DBSession
        session = db.query(DBSession).filter(
            DBSession.session_id == session_id
        ).first()
        
        if session:
            session.status = "terminated"
            db.commit()
            
        return {"message": "Session ended successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session termination failed: {str(e)}"
        )


@router.get("/session/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get summary of a chat session.
    """
    try:
        agent = get_nano_agent(db)
        result = agent.support_tools.generate_summary(session_id, None, "chat")
        
        if result["success"]:
            return result["summary"]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summary generation failed: {str(e)}"
        )