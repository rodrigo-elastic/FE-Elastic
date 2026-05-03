"""
filename: schemas.py
description: Pydantic models that mirror the JSON shapes Claude is forced to emit.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import List, Optional

from pydantic import BaseModel, Field


class BriefSectionOut(BaseModel):
    heading: str
    bullets: List[str]


class PreMeetingBriefOut(BaseModel):
    headline: str
    sections: List[BriefSectionOut]


class ActionItemOut(BaseModel):
    title: str
    owner_name: str
    owner_email: Optional[str] = None
    due_date: Optional[str] = None
    impact: Optional[str] = Field(default="med", description="low | med | high")
    description: str
    source_quote: str


class MEDDPICCSignalOut(BaseModel):
    category: str = Field(description="One of: Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion, Competition")
    quote: str
    note: Optional[str] = None


class CompetitorMentionOut(BaseModel):
    competitor: str
    context: str


class FollowUpEmailOut(BaseModel):
    subject: str
    body_markdown: str


class PostMeetingResultOut(BaseModel):
    summary: str
    action_items: List[ActionItemOut]
    meddpicc_signals: List[MEDDPICCSignalOut]
    competitor_mentions: List[CompetitorMentionOut]
    follow_up_email: FollowUpEmailOut


class LiveAlertOut(BaseModel):
    type: str = Field(description="competitor | meddpicc | question | risk")
    severity: str = Field(description="low | med | high")
    message: str
    suggested_response: str


class LiveAlertsOut(BaseModel):
    alerts: List[LiveAlertOut]


# ============================================================ TOOLS ===================


class POCPlanCriterion(BaseModel):
    metric: str
    target: str
    source_quote: str


class POCPlanPhase(BaseModel):
    name: str
    weeks: str
    activities: List[str]
    deliverables: List[str]
    technical_owners: dict  # keys: elastic, customer


class POCPlanResources(BaseModel):
    fe_hours: str
    customer_hours: str
    infrastructure: str


class POCPlanRisk(BaseModel):
    description: str
    mitigation: str


class POCPlanOut(BaseModel):
    executive_summary: str
    success_criteria: List[POCPlanCriterion]
    phases: List[POCPlanPhase]
    resource_requests: POCPlanResources
    risks: List[POCPlanRisk]


class SPLToESQLOut(BaseModel):
    esql: str
    explanation: str
    caveats: List[str]


class ComplianceRequirement(BaseModel):
    requirement: str
    elastic_control: str
    native: bool


class ComplianceMapping(BaseModel):
    regulation: str
    industry_note: str
    requirements: List[ComplianceRequirement]


class ComplianceMappingsOut(BaseModel):
    mappings: List[ComplianceMapping]


class StackItem(BaseModel):
    name: str
    evidence: str


class StackExtractOut(BaseModel):
    observability: List[StackItem]
    search: List[StackItem]
    cloud: List[StackItem]
    data: List[StackItem]
    languages: List[StackItem]
    frameworks: List[StackItem]


class CodeSampleOut(BaseModel):
    title: str
    code: str
    explanation: str
    prerequisites: List[str]
