from pydantic import BaseModel
from fastapi import FastAPI, Query, Body, HTTPException
from typing import Any

class AvailabilityRequest(BaseModel):
    username: str
    password: str
    period_from: str
    period_to: str
    adults: int
    children:int
    daily_mode: str
    
class BookingRequest(BaseModel):
    period_from: str
    period_to: str
    guest_firstname: str
    guest_lastname: str
    guest_email:str
    guest_phone: str
    adults:int
    children:str
    category_id: int
    daily_mode:str
    amount:int
    
class CheckBooking(BaseModel):
    name:str
    email:Any
    booking_date:str
    