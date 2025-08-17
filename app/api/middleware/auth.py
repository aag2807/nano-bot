from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
import time
from collections import defaultdict

from app.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token handler
security = HTTPBearer(auto_error=False)

# Rate limiting storage (in production, use Redis)
rate_limit_storage = defaultdict(list)


class AuthMiddleware:
    """Authentication and security middleware."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.token_expire_minutes = settings.access_token_expire_minutes

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)


class RateLimiter:
    """Rate limiting middleware to prevent abuse."""
    
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window

    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is within rate limits."""
        now = time.time()
        client_requests = rate_limit_storage[client_ip]
        
        # Remove old requests outside the time window
        rate_limit_storage[client_ip] = [
            req_time for req_time in client_requests 
            if now - req_time < self.time_window
        ]
        
        # Check if under limit
        if len(rate_limit_storage[client_ip]) < self.max_requests:
            rate_limit_storage[client_ip].append(now)
            return True
        
        return False


class SecurityHeaders:
    """Add security headers to responses."""
    
    @staticmethod
    def add_security_headers():
        """Return security headers dictionary."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    # Check for forwarded headers (common in production with load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to requests."""
    # Skip rate limiting for health checks
    if request.url.path.startswith("/health") or request.url.path.startswith("/api/v1/health"):
        return await call_next(request)
    
    client_ip = get_client_ip(request)
    rate_limiter = RateLimiter(max_requests=100, time_window=60)  # 100 requests per minute
    
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": 60
            }
        )
    
    response = await call_next(request)
    return response


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Add security headers
    security_headers = SecurityHeaders.add_security_headers()
    for header, value in security_headers.items():
        response.headers[header] = value
    
    return response


def validate_session_token(credentials: HTTPAuthorizationCredentials = None) -> Optional[dict]:
    """
    Validate session token (optional for most endpoints).
    This is mainly for admin or special endpoints.
    """
    if not credentials:
        return None
    
    auth_middleware = AuthMiddleware()
    payload = auth_middleware.verify_token(credentials.credentials)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return payload


class InputValidator:
    """Input validation and sanitization."""
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        if not isinstance(input_str, str):
            return ""
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\r']
        sanitized = input_str
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Limit length
        return sanitized[:max_length].strip()
    
    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """Validate session ID format."""
        if not session_id or not isinstance(session_id, str):
            return False
        
        # Session IDs should be UUIDs
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(session_id))
    
    @staticmethod
    def validate_customer_message(message: str) -> tuple[bool, str]:
        """Validate customer message input."""
        if not message or not isinstance(message, str):
            return False, "Message cannot be empty"
        
        if len(message) > 2000:
            return False, "Message too long (maximum 2000 characters)"
        
        if len(message.strip()) < 1:
            return False, "Message cannot be empty"
        
        return True, "Valid"


# Instance of authentication middleware
auth_middleware = AuthMiddleware()
input_validator = InputValidator()