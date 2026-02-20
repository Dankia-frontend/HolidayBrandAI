from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from utils.issues_db import create_issue, get_issue, get_all_issues

router = APIRouter(prefix="/api", tags=["Issues"])


class IssueResponse(BaseModel):
    id: int
    issue_title: str
    issue_description: str
    location_id: str
    park_name: str
    date: str


@router.post("/issues", response_model=IssueResponse)
def create_issue_endpoint(
    issue_title: str = Query(..., description="Issue title"),
    issue_description: str = Query(..., description="Issue description"),
    location_id: str = Query(..., description="Location ID"),
    park_name: str = Query(..., description="Park name"),
    date: str = Query(..., description="Date"),
):
    """
    Create a new issue. Saves issue title, description, location_id, park_name, and date to the DB.
    Returns the created issue with its assigned id.
    Query params are URL-decoded so values from GHL/voice AI are stored correctly.
    """
    result = create_issue(
        issue_title=unquote(issue_title),
        issue_description=unquote(issue_description),
        location_id=unquote(location_id),
        park_name=unquote(park_name),
        date=unquote(date),
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to create issue")
    return result


@router.get("/issues", response_model=list[IssueResponse])
def get_all_issues_endpoint():
    """
    Get all issues.
    """
    return get_all_issues()


@router.get("/issues/{issue_id}", response_model=IssueResponse)
def get_issue_endpoint(issue_id: int):
    """
    Get an issue by id.
    """
    result = get_issue(issue_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return result
