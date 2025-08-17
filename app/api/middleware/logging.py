import logging
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import Request, Response
from sqlalchemy.orm import Session
from app.database import AuditLog, get_db

# Configure logger
logger = logging.getLogger("nano.requests")


class RequestLoggingMiddleware:
    """Middleware for comprehensive request/response logging."""
    
    def __init__(self):
        self.sensitive_fields = {
            'password', 'token', 'secret', 'key', 'authorization',
            'account_number', 'ssn', 'security_answer'
        }
    
    async def log_request_response(self, request: Request, call_next, db: Session):
        """Log request and response details."""
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        
        # Log request
        request_data = await self._prepare_request_log(request, client_ip)
        logger.info(f"Request: {json.dumps(request_data)}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        response_data = self._prepare_response_log(response, process_time)
        logger.info(f"Response: {json.dumps(response_data)}")
        
        # Store in audit log if this is a sensitive operation
        if self._is_sensitive_endpoint(request.url.path):
            await self._store_audit_log(request_data, response_data, db)
        
        # Add custom headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_data["request_id"]
        
        return response
    
    async def _prepare_request_log(self, request: Request, client_ip: str) -> Dict[str, Any]:
        """Prepare request data for logging."""
        # Generate unique request ID
        request_id = f"req_{int(time.time() * 1000)}_{id(request) % 10000}"
        
        # Basic request info
        request_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", ""),
            "content_type": request.headers.get("Content-Type", ""),
            "content_length": request.headers.get("Content-Length", "0")
        }
        
        # Add query parameters (sanitized)
        if request.query_params:
            request_data["query_params"] = dict(request.query_params)
        
        # Add request body for POST/PUT (sanitized)
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await self._get_request_body(request)
                if body:
                    request_data["body"] = self._sanitize_sensitive_data(body)
            except Exception as e:
                request_data["body_error"] = str(e)
        
        # Add session info if available
        session_id = self._extract_session_id(request)
        if session_id:
            request_data["session_id"] = session_id
        
        return request_data
    
    def _prepare_response_log(self, response: Response, process_time: float) -> Dict[str, Any]:
        """Prepare response data for logging."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": response.status_code,
            "process_time_seconds": round(process_time, 4),
            "content_type": response.headers.get("Content-Type", ""),
            "content_length": response.headers.get("Content-Length", "0")
        }
    
    async def _get_request_body(self, request: Request) -> Optional[Dict[str, Any]]:
        """Extract request body as JSON."""
        try:
            # Check if body has already been read
            if hasattr(request, '_cached_body'):
                body_bytes = request._cached_body
            else:
                body_bytes = await request.body()
                request._cached_body = body_bytes
            
            if body_bytes:
                body_str = body_bytes.decode('utf-8')
                return json.loads(body_str)
            return None
        except Exception:
            return None
    
    def _sanitize_sensitive_data(self, data: Any) -> Any:
        """Remove or mask sensitive data from logs."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in self.sensitive_fields:
                    sanitized[key] = "*" * len(str(value)) if value else None
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_sensitive_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_sensitive_data(item) for item in data]
        else:
            return data
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _extract_session_id(self, request: Request) -> Optional[str]:
        """Extract session ID from request."""
        # Check query parameters
        session_id = request.query_params.get("session_id")
        if session_id:
            return session_id
        
        # Check headers
        session_id = request.headers.get("X-Session-ID")
        if session_id:
            return session_id
        
        # For POST requests, might be in body (would need to parse)
        return None
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint handles sensitive operations."""
        sensitive_paths = [
            "/api/v1/chat",
            "/api/v1/session",
            "/verify",
            "/balance",
            "/transaction"
        ]
        return any(sensitive_path in path for sensitive_path in sensitive_paths)
    
    async def _store_audit_log(self, request_data: Dict, response_data: Dict, db: Session):
        """Store sensitive operations in audit log."""
        try:
            audit_entry = AuditLog(
                session_id=request_data.get("session_id", "unknown"),
                customer_id=None,  # Would be populated by the actual handler
                action="api_request",
                details=json.dumps({
                    "method": request_data["method"],
                    "path": request_data["path"],
                    "status_code": response_data["status_code"],
                    "process_time": response_data["process_time_seconds"],
                    "client_ip": request_data["client_ip"]
                }),
                ip_address=request_data["client_ip"],
                user_agent=request_data.get("user_agent"),
                status="success" if response_data["status_code"] < 400 else "failed"
            )
            
            db.add(audit_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to store audit log: {e}")


class SecurityEventLogger:
    """Logger for security events."""
    
    @staticmethod
    def log_security_event(event_type: str, details: Dict[str, Any], severity: str = "INFO"):
        """Log security-related events."""
        security_logger = logging.getLogger("nano.security")
        
        log_entry = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "details": details
        }
        
        if severity == "CRITICAL":
            security_logger.critical(json.dumps(log_entry))
        elif severity == "ERROR":
            security_logger.error(json.dumps(log_entry))
        elif severity == "WARNING":
            security_logger.warning(json.dumps(log_entry))
        else:
            security_logger.info(json.dumps(log_entry))
    
    @staticmethod
    def log_failed_verification(session_id: str, client_ip: str, reason: str):
        """Log failed identity verification attempts."""
        SecurityEventLogger.log_security_event(
            "failed_verification",
            {
                "session_id": session_id,
                "client_ip": client_ip,
                "reason": reason
            },
            "WARNING"
        )
    
    @staticmethod
    def log_rate_limit_exceeded(client_ip: str, endpoint: str):
        """Log rate limit violations."""
        SecurityEventLogger.log_security_event(
            "rate_limit_exceeded",
            {
                "client_ip": client_ip,
                "endpoint": endpoint
            },
            "WARNING"
        )
    
    @staticmethod
    def log_suspicious_activity(session_id: str, client_ip: str, activity: str):
        """Log potentially suspicious activities."""
        SecurityEventLogger.log_security_event(
            "suspicious_activity",
            {
                "session_id": session_id,
                "client_ip": client_ip,
                "activity": activity
            },
            "ERROR"
        )


# Middleware instance
request_logger = RequestLoggingMiddleware()
security_logger = SecurityEventLogger()