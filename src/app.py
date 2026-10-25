"""
Slalom Capabilities Management System API

A FastAPI application that enables Slalom consultants to register their
capabilities and manage consulting expertise across the organization.
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import os
import secrets
from pathlib import Path
from datetime import UTC, datetime
from typing import Literal
from starlette.middleware.sessions import SessionMiddleware

try:
    from .auth import authenticate_user, get_current_user, require_csrf, require_practice_lead, require_user, user_has_capability_access, write_audit_event
except ImportError:
    from auth import authenticate_user, get_current_user, require_csrf, require_practice_lead, require_user, user_has_capability_access, write_audit_event

app = FastAPI(title="Slalom Capabilities Management API",
              description="API for managing consulting capabilities and consultant expertise")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32),
    session_cookie="slalom_session",
    max_age=8 * 60 * 60,
    same_site="strict",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=256)


class CapabilityRequirements(BaseModel):
    capacity: int | None = Field(default=None, ge=0, le=168)
    certifications: list[str] | None = None
    skill_levels: list[str] | None = None


class TrainingRequestBody(BaseModel):
    goal: str = Field(min_length=10, max_length=1000)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory capabilities database
capabilities = {
    "Cloud Architecture": {
        "description": "Design and implement scalable cloud solutions using AWS, Azure, and GCP",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["AWS Solutions Architect", "Azure Architect Expert"],
        "industry_verticals": ["Healthcare", "Financial Services", "Retail"],
        "capacity": 40,  # hours per week available across team
        "consultants": ["alice.smith@slalom.com", "bob.johnson@slalom.com"],
        "pending_consultants": []
    },
    "Data Analytics": {
        "description": "Advanced data analysis, visualization, and machine learning solutions",
        "practice_area": "Technology", 
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Tableau Desktop Specialist", "Power BI Expert", "Google Analytics"],
        "industry_verticals": ["Retail", "Healthcare", "Manufacturing"],
        "capacity": 35,
        "consultants": ["emma.davis@slalom.com", "sophia.wilson@slalom.com"],
        "pending_consultants": []
    },
    "DevOps Engineering": {
        "description": "CI/CD pipeline design, infrastructure automation, and containerization",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"], 
        "certifications": ["Docker Certified Associate", "Kubernetes Admin", "Jenkins Certified"],
        "industry_verticals": ["Technology", "Financial Services"],
        "capacity": 30,
        "consultants": ["john.brown@slalom.com", "olivia.taylor@slalom.com"],
        "pending_consultants": []
    },
    "Digital Strategy": {
        "description": "Digital transformation planning and strategic technology roadmaps",
        "practice_area": "Strategy",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Digital Transformation Certificate", "Agile Certified Practitioner"],
        "industry_verticals": ["Healthcare", "Financial Services", "Government"],
        "capacity": 25,
        "consultants": ["liam.anderson@slalom.com", "noah.martinez@slalom.com"],
        "pending_consultants": []
    },
    "Change Management": {
        "description": "Organizational change leadership and adoption strategies",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Prosci Certified", "Lean Six Sigma Black Belt"],
        "industry_verticals": ["Healthcare", "Manufacturing", "Government"],
        "capacity": 20,
        "consultants": ["ava.garcia@slalom.com", "mia.rodriguez@slalom.com"],
        "pending_consultants": []
    },
    "UX/UI Design": {
        "description": "User experience design and digital product innovation",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Adobe Certified Expert", "Google UX Design Certificate"],
        "industry_verticals": ["Retail", "Healthcare", "Technology"],
        "capacity": 30,
        "consultants": ["amelia.lee@slalom.com", "harper.white@slalom.com"],
        "pending_consultants": []
    },
    "Cybersecurity": {
        "description": "Information security strategy, risk assessment, and compliance",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["CISSP", "CISM", "CompTIA Security+"],
        "industry_verticals": ["Financial Services", "Healthcare", "Government"],
        "capacity": 25,
        "consultants": ["ella.clark@slalom.com", "scarlett.lewis@slalom.com"],
        "pending_consultants": []
    },
    "Business Intelligence": {
        "description": "Enterprise reporting, data warehousing, and business analytics",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Microsoft BI Certification", "Qlik Sense Certified"],
        "industry_verticals": ["Retail", "Manufacturing", "Financial Services"],
        "capacity": 35,
        "consultants": ["james.walker@slalom.com", "benjamin.hall@slalom.com"],
        "pending_consultants": []
    },
    "Agile Coaching": {
        "description": "Agile transformation and team coaching for scaled delivery",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Certified Scrum Master", "SAFe Agilist", "ICAgile Certified"],
        "industry_verticals": ["Technology", "Financial Services", "Healthcare"],
        "capacity": 20,
        "consultants": ["charlotte.young@slalom.com", "henry.king@slalom.com"],
        "pending_consultants": []
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/capabilities")
def get_capabilities(user: dict = Depends(require_user)):
    visible_capabilities = {}
    for name, details in capabilities.items():
        capability = dict(details)
        has_area_access = user_has_capability_access(user, details)
        capability["can_manage"] = user["role"] == "practice_lead" and has_area_access
        if user["role"] != "practice_lead":
            capability["pending_consultants"] = [
                email for email in details.get("pending_consultants", [])
                if email == user["email"]
            ]
            capability["training_requests"] = [
                item for item in details.get("training_requests", [])
                if item["email"] == user["email"]
            ]
        elif not has_area_access:
            capability["pending_consultants"] = []
            capability["training_requests"] = []
        visible_capabilities[name] = capability
    return visible_capabilities


@app.get("/reports/capabilities")
def get_capability_report(user: dict = Depends(require_practice_lead)):
    visible = {
        name: details for name, details in capabilities.items()
        if user_has_capability_access(user, details)
    }
    by_practice_area = {}
    for details in visible.values():
        area = details["practice_area"]
        summary = by_practice_area.setdefault(
            area,
            {
                "capabilities": 0,
                "registered_consultants": 0,
                "pending_requests": 0,
                "pending_training_requests": 0,
            },
        )
        summary["capabilities"] += 1
        summary["registered_consultants"] += len(details["consultants"])
        summary["pending_requests"] += len(details["pending_consultants"])
        summary["pending_training_requests"] += sum(
            item["status"] == "pending" for item in details.get("training_requests", [])
        )
    return {
        "capabilities": len(visible),
        "registered_consultants": sum(len(item["consultants"]) for item in visible.values()),
        "pending_requests": sum(len(item["pending_consultants"]) for item in visible.values()),
        "pending_training_requests": sum(
            sum(request["status"] == "pending" for request in item.get("training_requests", []))
            for item in visible.values()
        ),
        "by_practice_area": by_practice_area,
    }


@app.post("/auth/login")
def login(credentials: Credentials, request: Request):
    user = authenticate_user(credentials.email, credentials.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    request.session.clear()
    request.session["email"] = user["email"]
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    write_audit_event(user["email"], "login_succeeded")
    return {**user, "csrf_token": request.session["csrf_token"]}


@app.get("/auth/me")
def get_session_user(request: Request, user: dict = Depends(get_current_user)):
    csrf_token = request.session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {**user, "csrf_token": csrf_token}


@app.post("/auth/logout")
def logout(request: Request, user: dict = Depends(require_csrf)):
    write_audit_event(user["email"], "logout")
    request.session.clear()
    return {"message": "Logged out"}


@app.post("/capabilities/{capability_name}/register")
def register_for_capability(
    capability_name: str,
    email: str | None = None,
    user: dict = Depends(require_csrf),
):
    """Assign a consultant or submit a consultant's registration request."""
    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    if not user_has_capability_access(user, capability):
        raise HTTPException(status_code=403, detail="You cannot manage this practice area")

    if user["role"] == "consultant":
        if email and email.lower() != user["email"]:
            raise HTTPException(status_code=403, detail="Consultants can only register themselves")
        email = user["email"]
        if email in capability["consultants"]:
            raise HTTPException(status_code=400, detail="Consultant is already registered")
        if email in capability["pending_consultants"]:
            raise HTTPException(status_code=400, detail="Registration request is already pending")
        capability["pending_consultants"].append(email)
        write_audit_event(user["email"], "registration_requested", capability_name, email)
        return {"message": f"Registration request submitted for {capability_name}", "status": "pending"}

    if not email:
        raise HTTPException(status_code=422, detail="Practice leads must provide a consultant email")
    email = email.lower()

    # Validate consultant is not already registered
    if email in capability["consultants"]:
        raise HTTPException(
            status_code=400,
            detail="Consultant is already registered for this capability"
        )

    # Add consultant
    capability["consultants"].append(email)
    write_audit_event(user["email"], "registration_added", capability_name, email)
    return {"message": f"Registered {email} for {capability_name}"}


@app.delete("/capabilities/{capability_name}/unregister")
def unregister_from_capability(
    capability_name: str,
    email: str | None = None,
    user: dict = Depends(require_csrf),
):
    """Unregister a consultant from a capability"""
    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    if not user_has_capability_access(user, capability):
        raise HTTPException(status_code=403, detail="You cannot manage this practice area")

    if user["role"] == "consultant":
        if email and email.lower() != user["email"]:
            raise HTTPException(status_code=403, detail="Consultants can only remove their own registration")
        email = user["email"]
        if email in capability["pending_consultants"]:
            capability["pending_consultants"].remove(email)
            write_audit_event(user["email"], "registration_request_withdrawn", capability_name, email)
            return {"message": f"Registration request withdrawn for {capability_name}"}
        raise HTTPException(status_code=403, detail="Only practice leads can remove approved registrations")
    elif not email:
        raise HTTPException(status_code=422, detail="Practice leads must provide a consultant email")
    else:
        email = email.lower()

    # Validate consultant is registered
    if email not in capability["consultants"]:
        raise HTTPException(
            status_code=400,
            detail="Consultant is not registered for this capability"
        )

    # Remove consultant
    capability["consultants"].remove(email)
    write_audit_event(user["email"], "registration_removed", capability_name, email)
    return {"message": f"Unregistered {email} from {capability_name}"}


@app.post("/capabilities/{capability_name}/approve")
def approve_consultant(
    capability_name: str,
    email: str,
    user: dict = Depends(require_practice_lead),
    csrf_user: dict = Depends(require_csrf),
):
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")
    capability = capabilities[capability_name]
    if not user_has_capability_access(user, capability):
        raise HTTPException(status_code=403, detail="You cannot manage this practice area")
    email = email.lower()
    if email not in capability["pending_consultants"]:
        raise HTTPException(status_code=404, detail="No pending request for this consultant")
    capability["pending_consultants"].remove(email)
    if email not in capability["consultants"]:
        capability["consultants"].append(email)
    write_audit_event(user["email"], "registration_approved", capability_name, email)
    return {"message": f"Approved {email} for {capability_name}"}


@app.post("/capabilities/{capability_name}/training-requests", status_code=201)
def request_training(
    capability_name: str,
    request_body: TrainingRequestBody,
    user: dict = Depends(require_csrf),
):
    if user["role"] != "consultant":
        raise HTTPException(status_code=403, detail="Only consultants can request training")
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")
    requests = capabilities[capability_name].setdefault("training_requests", [])
    if any(
        item["email"] == user["email"] and item["status"] == "pending"
        for item in requests
    ):
        raise HTTPException(status_code=400, detail="A training request is already pending")
    goal = request_body.goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="Training goal cannot be empty")
    request = {
        "email": user["email"],
        "goal": goal,
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
    }
    requests.append(request)
    write_audit_event(user["email"], "training_requested", capability_name)
    return {"message": f"Training request submitted for {capability_name}", "status": "pending"}


@app.post("/capabilities/{capability_name}/training-requests/review")
def review_training_request(
    capability_name: str,
    email: str,
    decision: Literal["approved", "declined"],
    user: dict = Depends(require_practice_lead),
    csrf_user: dict = Depends(require_csrf),
):
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")
    capability = capabilities[capability_name]
    if not user_has_capability_access(user, capability):
        raise HTTPException(status_code=403, detail="You cannot manage this practice area")
    training_request = next(
        (
            item for item in capability.get("training_requests", [])
            if item["email"] == email.lower() and item["status"] == "pending"
        ),
        None,
    )
    if training_request is None:
        raise HTTPException(status_code=404, detail="No pending training request for this consultant")
    training_request["status"] = decision
    training_request["reviewed_by"] = user["email"]
    training_request["reviewed_at"] = datetime.now(UTC).isoformat()
    write_audit_event(user["email"], f"training_{decision}", capability_name, email.lower())
    return {"message": f"Training request {decision} for {capability_name}"}


@app.patch("/capabilities/{capability_name}/requirements")
def update_capability_requirements(
    capability_name: str,
    updates: CapabilityRequirements,
    user: dict = Depends(require_practice_lead),
    csrf_user: dict = Depends(require_csrf),
):
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")
    capability = capabilities[capability_name]
    if not user_has_capability_access(user, capability):
        raise HTTPException(status_code=403, detail="You cannot manage this practice area")
    changes = updates.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="At least one requirement must be provided")
    if "capacity" in changes and changes["capacity"] is None:
        raise HTTPException(status_code=422, detail="Capacity cannot be null")
    if "skill_levels" in changes and (
        not changes["skill_levels"]
        or any(not level.strip() for level in changes["skill_levels"])
    ):
        raise HTTPException(status_code=422, detail="At least one non-empty skill level is required")
    if "certifications" in changes and (
        changes["certifications"] is None
        or any(not certification.strip() for certification in changes["certifications"])
    ):
        raise HTTPException(status_code=422, detail="Certifications must be non-empty strings")
    capability.update(changes)
    write_audit_event(user["email"], "capability_requirements_updated", capability_name)
    return capability
