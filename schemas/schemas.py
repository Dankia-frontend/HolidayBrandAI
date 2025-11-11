from pydantic import BaseModel, Field
from fastapi import FastAPI, Query, Body, HTTPException
from typing import Any, Optional

class AvailabilityRequest(BaseModel):
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


# ==================== Park Configuration Schemas ====================

class ParkConfigurationCreate(BaseModel):
    """Schema for creating a new park configuration"""
    location_id: str = Field(..., description="GHL location ID")
    park_name: str = Field(..., description="Human-readable park name")
    newbook_api_token: str = Field(..., description="Newbook API token for this park")
    newbook_api_key: str = Field(..., description="Newbook API key for this park")
    newbook_region: str = Field(..., description="Newbook region code")
    ghl_pipeline_id: str = Field(..., description="GHL pipeline ID for this park")
    
    # Optional stage IDs
    stage_arriving_soon: Optional[str] = Field(None, description="Stage ID for 'arriving soon' bookings")
    stage_arriving_today: Optional[str] = Field(None, description="Stage ID for 'arriving today' bookings")
    stage_arrived: Optional[str] = Field(None, description="Stage ID for 'arrived' bookings")
    stage_departing_today: Optional[str] = Field(None, description="Stage ID for 'departing today' bookings")
    stage_departed: Optional[str] = Field(None, description="Stage ID for 'departed' bookings")


class ParkConfigurationUpdate(BaseModel):
    """Schema for updating an existing park configuration"""
    park_name: Optional[str] = Field(None, description="Human-readable park name")
    newbook_api_token: Optional[str] = Field(None, description="Newbook API token for this park")
    newbook_api_key: Optional[str] = Field(None, description="Newbook API key for this park")
    newbook_region: Optional[str] = Field(None, description="Newbook region code")
    ghl_pipeline_id: Optional[str] = Field(None, description="GHL pipeline ID for this park")
    
    # Optional stage IDs
    stage_arriving_soon: Optional[str] = Field(None, description="Stage ID for 'arriving soon' bookings")
    stage_arriving_today: Optional[str] = Field(None, description="Stage ID for 'arriving today' bookings")
    stage_arrived: Optional[str] = Field(None, description="Stage ID for 'arrived' bookings")
    stage_departing_today: Optional[str] = Field(None, description="Stage ID for 'departing today' bookings")
    stage_departed: Optional[str] = Field(None, description="Stage ID for 'departed' bookings")
    is_active: Optional[bool] = Field(None, description="Whether the configuration is active")


class ParkConfigurationResponse(BaseModel):
    """Schema for park configuration responses"""
    id: int
    location_id: str
    park_name: str
    newbook_api_token: str
    newbook_api_key: str
    newbook_region: str
    ghl_pipeline_id: str
    
    stage_arriving_soon: Optional[str]
    stage_arriving_today: Optional[str]
    stage_arrived: Optional[str]
    stage_departing_today: Optional[str]
    stage_departed: Optional[str]
    
    is_active: bool
    created_at: Any
    updated_at: Any


# ==================== Voice AI Configuration Schemas ====================

class VoiceAICloneRequest(BaseModel):
    """Schema for cloning Voice AI configuration from one location to another"""
    source_location_id: str = Field(..., description="Source GHL location ID to copy from")
    target_location_id: str = Field(..., description="Target GHL location ID to copy to")
    clone_assistants: bool = Field(True, description="Clone AI assistants")
    clone_workflows: bool = Field(True, description="Clone workflows associated with Voice AI")
    clone_phone_numbers: bool = Field(False, description="Clone phone number configurations (if applicable)")


class VoiceAIConfigResponse(BaseModel):
    """Schema for Voice AI configuration response"""
    location_id: str
    config_data: dict = Field(..., description="Voice AI configuration data")
    success: bool
    message: Optional[str] = None


# ==================== Voice AI Agents Schemas ====================

class VoiceAIAgentsCloneRequest(BaseModel):
    """Schema for cloning Voice AI Agents from one location to another"""
    source_location_id: str = Field(..., description="Source GHL location ID to copy from")
    target_location_id: str = Field(..., description="Target GHL location ID to copy to")
    clone_all: bool = Field(True, description="Clone all agents (if False, specify agent IDs)")
    specific_agent_ids: Optional[list[str]] = Field(None, description="Specific agent IDs to clone (used when clone_all is False)")


class VoiceAIAgentCreateRequest(BaseModel):
    """Schema for creating a Voice AI Agent"""
    location_id: str = Field(..., description="GHL location ID where the agent will be created")
    name: str = Field(..., description="Agent name")
    prompt: Optional[str] = Field(None, description="Agent prompt/instructions")
    systemPrompt: Optional[str] = Field(None, description="System prompt")
    firstMessage: Optional[str] = Field(None, description="First message the agent says")
    voiceId: Optional[str] = Field(None, description="Voice ID to use")
    provider: Optional[str] = Field(None, description="Voice provider (e.g., 'elevenlabs', 'azure')")
    language: Optional[str] = Field("en-US", description="Language code")
    model: Optional[str] = Field("gpt-4", description="AI model to use")
    temperature: Optional[float] = Field(0.7, description="Model temperature (0-1)")


class VoiceAIAgentUpdateRequest(BaseModel):
    """Schema for updating a Voice AI Agent"""
    name: Optional[str] = Field(None, description="Agent name")
    prompt: Optional[str] = Field(None, description="Agent prompt/instructions")
    systemPrompt: Optional[str] = Field(None, description="System prompt")
    firstMessage: Optional[str] = Field(None, description="First message")
    voiceId: Optional[str] = Field(None, description="Voice ID")
    provider: Optional[str] = Field(None, description="Voice provider")
    language: Optional[str] = Field(None, description="Language code")
    model: Optional[str] = Field(None, description="AI model")
    temperature: Optional[float] = Field(None, description="Model temperature")
    enabled: Optional[bool] = Field(None, description="Whether agent is enabled")
    