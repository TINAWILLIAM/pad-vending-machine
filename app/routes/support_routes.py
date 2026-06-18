"""
support_routes.py – APIs for Support Tickets (User Submission & Admin Management)
"""
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.database import get_collection
from app.admin.dependencies import require_admin_token
from app.utils.logger import logger

router = APIRouter(prefix="/support", tags=["Support Tickets"])


# ── Request / Response Schemas ───────────────────────────────────────────────

class TicketCreateRequest(BaseModel):
    user_id: str
    email: EmailStr
    issue_type: str
    description: str
    machine_id: Optional[str] = None
    machine_name: Optional[str] = None


class TicketStatusUpdateRequest(BaseModel):
    status: str


def _to_response(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/create-ticket", status_code=status.HTTP_201_CREATED, summary="Create a new support ticket")
async def create_ticket(request: TicketCreateRequest):
    """
    Submit a support ticket complaint. Anyone can do this.
    """
    col = get_collection("issue_reports")
    now = datetime.utcnow()
    
    ticket_doc = {
        "user_id": request.user_id,
        "email": request.email,
        "issue_type": request.issue_type,
        "description": request.description,
        "machine_id": request.machine_id,
        "machine_name": request.machine_name,
        "status": "OPEN",
        "created_at": now,
        "updated_at": now,
    }
    
    try:
        result = await col.insert_one(ticket_doc)
        ticket_id = str(result.inserted_id)
        logger.info(f"Support ticket created: {ticket_id} for user {request.email}")
        return {
            "ticket_id": ticket_id,
            "message": "Support ticket created successfully."
        }
    except Exception as exc:
        logger.error(f"Failed to create support ticket: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit support ticket. Please try again."
        )


@router.get("/tickets", summary="List all support tickets (newest first)")
async def get_tickets(_: dict = Depends(require_admin_token)):
    """
    Admin only: Get all tickets, sorted newest first.
    """
    col = get_collection("issue_reports")
    try:
        cursor = col.find({}).sort("created_at", -1)
        tickets = []
        async for doc in cursor:
            tickets.append(_to_response(doc))
        return tickets
    except Exception as exc:
        logger.error(f"Failed to fetch support tickets: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve support tickets."
        )


@router.patch("/ticket/{ticket_id}", summary="Update a ticket's status")
async def update_ticket_status(ticket_id: str, request: TicketStatusUpdateRequest, _: dict = Depends(require_admin_token)):
    """
    Admin only: Update a ticket's status (OPEN, IN_PROGRESS, or RESOLVED).
    """
    if request.status not in ["OPEN", "IN_PROGRESS", "RESOLVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be one of: OPEN, IN_PROGRESS, RESOLVED"
        )
        
    try:
        oid = ObjectId(ticket_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticket ID format."
        )

    col = get_collection("issue_reports")
    now = datetime.utcnow()
    
    try:
        result = await col.find_one_and_update(
            {"_id": oid},
            {"$set": {"status": request.status, "updated_at": now}},
            return_document=True
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found."
            )
        logger.info(f"Support ticket {ticket_id} status updated to {request.status}")
        return _to_response(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update support ticket {ticket_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ticket status."
        )
