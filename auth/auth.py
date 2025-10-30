from fastapi import Header, HTTPException
from config.config import AI_AGENT_KEY


def authenticate_request(x_ai_agent_key: str = Header(None)):
    """
    Authentication helper that validates the AI agent key.
    Logic intentionally identical to the previous implementation.
    """
    if not x_ai_agent_key:
        raise HTTPException(status_code=401, detail="Missing AI_AGENT_KEY in headers")

    if x_ai_agent_key != AI_AGENT_KEY:
        raise HTTPException(status_code=401, detail="Invalid AI_AGENT_KEY")

    return x_ai_agent_key


