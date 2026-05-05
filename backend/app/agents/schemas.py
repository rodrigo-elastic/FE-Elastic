"""
filename: schemas.py
description: Pydantic models that mirror the JSON shapes Claude is forced to emit.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, List, Literal, Optional

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


class TroubleshootCause(BaseModel):
    cause: str
    confidence: str = Field(description="high | medium | low")
    evidence_in_input: str


class TroubleshootDiagnosticQuery(BaseModel):
    title: str
    esql: str
    expected_signal: str


class TroubleshootRemediation(BaseModel):
    step: str
    risk_level: str = Field(description="low | medium | high")
    reversible: bool


class TroubleshootOut(BaseModel):
    likely_causes: List[TroubleshootCause]
    diagnostic_queries: List[TroubleshootDiagnosticQuery]
    quick_remediations: List[TroubleshootRemediation]
    escalation_path: str
    caveats: List[str]


# ============================================================ DEPLOY VALIDATOR (Astrid) ===


class DeployFinding(BaseModel):
    """One antipattern Astrid spotted in a pasted cluster summary."""
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    antipattern: str
    remediation_steps: List[str]
    doc_url: str


class DeployValidatorOut(BaseModel):
    """Full validation report from the deploy validator tool."""
    findings: List[DeployFinding]
    summary: str
    cluster_health_score: int = Field(ge=0, le=100)


# ============================================================ COMPARE (Sloane) ========


class CompareTechnicalDimension(BaseModel):
    axis: str
    elastic: str
    competitor: str
    winner: str = Field(description="elastic | competitor | tie")
    reasoning: str


class CompareTechnical(BaseModel):
    summary: str
    dimensions: List[CompareTechnicalDimension]
    elastic_advantages: List[str]
    competitor_advantages: List[str]
    honest_gaps: List[str]


class CompareScenario(BaseModel):
    ingest_gb_day: float
    retention_months: int


class CompareCost(BaseModel):
    summary: str
    scenario: CompareScenario
    elastic_annual_usd: Optional[float] = None
    competitor_annual_usd: Optional[float] = None
    savings_vs_competitor_pct: Optional[float] = None
    pricing_model_notes: List[str]
    hidden_costs: List[str]


class CompareOut(BaseModel):
    competitor: str
    battlecard_used: bool
    technical: CompareTechnical
    cost: CompareCost
    discovery_questions: List[str]
    follow_ups: List[str]
    sources: List[str]


# ============================================================ ORCHESTRATOR ============


class OrchestratorPick(BaseModel):
    """One tool selection emitted by Auro at planning time."""
    tool: str
    rationale: str
    input_json: str  # JSON-encoded input arguments. Parsed server-side before execution.


class OrchestratorPlanOut(BaseModel):
    """Step-1 planning output: which tools to call and with what inputs."""
    plan: str
    picks: List[OrchestratorPick]


class OrchestratorSynthesisOut(BaseModel):
    """Step-3 synthesis output: unified narrative + suggested follow-ups."""
    synthesis: str
    follow_ups: List[str]


class OrchestratorInvocation(BaseModel):
    """One executed tool slot in the orchestrator response."""
    tool: str
    rationale: str
    input: Dict[str, Any]
    output_summary: str
    ok: bool
    error: Optional[str] = None


class OrchestratorOut(BaseModel):
    """Final response shape for POST /tools/orchestrator."""
    plan: str
    tools_invoked: List[OrchestratorInvocation]
    synthesis: str
    follow_ups: List[str]


# ============================================================ PROPOSAL (Carmen) ========


class ProposalValuePillar(BaseModel):
    name: str
    headline: str
    metrics: List[str]


class ProposalScope(BaseModel):
    in_scope: List[str]
    out_of_scope: List[str]


class ProposalTimelinePhase(BaseModel):
    phase: str
    weeks: str
    deliverables: List[str]


class ProposalInvestment(BaseModel):
    elastic_cloud_annual_usd: Optional[float] = None
    professional_services_hours: Optional[int] = None
    free_pov_hours: int = 60
    notes: List[str] = Field(default_factory=list)


class ProposalRisk(BaseModel):
    risk: str
    mitigation: str


class ProposalOut(BaseModel):
    """Carmen's one-page proposal output. The pdf_path is filled in server-side after rendering."""
    meeting_id: str
    title: str
    executive_summary: str
    value_pillars: List[ProposalValuePillar]
    scope: ProposalScope
    timeline: List[ProposalTimelinePhase]
    investment: ProposalInvestment
    risks: List[ProposalRisk]
    next_steps: List[str]
    pdf_path: str = ""


# ============================================================ COST CALC (Lyra) =========


# Data-quality literal: every numeric line carries one of these so the FE,
# the JSON consumer, and the demo judges can all separate hard list pricing
# from a demo-grade approximation in one glance.
DataQuality = Literal["verified_list_price", "demo_estimate"]


class CostLineItem(BaseModel):
    """One labeled numeric output of the cost calculator with a quality tag."""
    label: str
    amount_usd: Optional[float] = None
    unit_price_usd: Optional[float] = None
    data_quality: DataQuality = "demo_estimate"
    note: Optional[str] = None


class ElasticCost(BaseModel):
    """Elastic Cloud annual TCO breakdown."""
    hot_gb: float = 0.0
    warm_gb: float = 0.0
    frozen_gb: float = 0.0
    hot_cost: float = 0.0
    warm_cost: float = 0.0
    frozen_cost: float = 0.0
    total_annual_usd: float = 0.0
    line_items: List[CostLineItem] = Field(default_factory=list)


class CompetitorCost(BaseModel):
    """Named competitor (Splunk or Datadog) annual TCO breakdown."""
    name: str
    total_annual_usd: float = 0.0
    line_items: List[CostLineItem] = Field(default_factory=list)


class SavingsBreakdown(BaseModel):
    """Savings of Elastic vs the user's current spend, with per-line tags."""
    vs_current_usd: Optional[float] = None
    vs_current_pct: Optional[float] = None
    line_items: List[CostLineItem] = Field(default_factory=list)


class CostInputs(BaseModel):
    """Echo of the user-supplied calculator inputs (for audit and replay)."""
    ingest_gb_day: float
    retention_months: int
    hot_pct: float = 30.0
    warm_pct: float = 30.0
    frozen_pct: float = 40.0
    current_spend_annual_usd: Optional[float] = None
    competitor: str = "splunk"


class CostOut(BaseModel):
    """Full cost-calc response. Every numeric line carries a data_quality tag."""
    inputs: CostInputs
    elastic: ElasticCost
    splunk: CompetitorCost
    datadog: CompetitorCost
    competitor: CompetitorCost
    savings: SavingsBreakdown
    savings_vs_current: Optional[float] = None
    savings_pct_vs_current: Optional[float] = None
    notes: List[str] = Field(default_factory=list)
