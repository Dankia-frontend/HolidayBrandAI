from fastapi import HTTPException, Security, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify API token from Authorization header using HTTPBearer"""
    expected_token = os.getenv("AI_AGENT_KEY")
    
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    
    return credentials.credentials


def authenticate_request(x_ai_agent_key: str = Header(None)):
    """
    Authentication helper that validates the AI agent key from header.
    Used by Newbook and RMS for simple header-based authentication.
    """
    expected_token = os.getenv("AI_AGENT_KEY")
    
    if not x_ai_agent_key:
        raise HTTPException(status_code=401, detail="Missing AI_AGENT_KEY in headers")

    if x_ai_agent_key != expected_token:
        raise HTTPException(status_code=401, detail="Invalid AI_AGENT_KEY")

    return x_ai_agent_key