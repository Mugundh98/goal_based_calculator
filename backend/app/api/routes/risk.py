from fastapi import APIRouter, HTTPException, status

from app.api.deps import Audit, CurrentUser, DbSession
from app.finance.risk_profile import QUESTIONNAIRE_VERSION, QUESTIONS, InvalidAnswersError
from app.schemas.risk import (
    AssessmentInput,
    AssessmentRead,
    OptionOut,
    QuestionnaireOut,
    QuestionOut,
)
from app.services.risk import (
    ProfileRequiredError,
    create_assessment,
    latest_assessment,
    list_assessments,
)

router = APIRouter(prefix="/risk", tags=["risk profile"])


@router.get("/questionnaire", response_model=QuestionnaireOut)
def questionnaire(_: CurrentUser) -> QuestionnaireOut:
    """The risk-tolerance questions and their options (without scores)."""
    return QuestionnaireOut(
        version=QUESTIONNAIRE_VERSION,
        questions=[
            QuestionOut(
                id=q.id,
                text=q.text,
                options=[OptionOut(id=o.id, text=o.text) for o in q.options],
            )
            for q in QUESTIONS
        ],
    )


@router.post("/assessments", response_model=AssessmentRead, status_code=status.HTTP_201_CREATED)
def submit_assessment(
    data: AssessmentInput, user: CurrentUser, db: DbSession, audit: Audit
) -> AssessmentRead:
    """Score the answers together with the financial profile and store the result."""
    try:
        assessment = create_assessment(db, user, data.answers)
    except ProfileRequiredError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Complete your financial profile first"
        ) from None
    except InvalidAnswersError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    audit(
        "risk.assess",
        user,
        entity_type="risk_assessment",
        entity_id=assessment.id,
        details={"category": assessment.category, "final_score": assessment.final_score},
    )
    return AssessmentRead.model_validate(assessment)


@router.get("/assessments", response_model=list[AssessmentRead])
def assessment_history(user: CurrentUser, db: DbSession) -> list[AssessmentRead]:
    """All of the user's assessments, newest first."""
    return [AssessmentRead.model_validate(a) for a in list_assessments(db, user)]


@router.get("/assessments/latest", response_model=AssessmentRead)
def latest(user: CurrentUser, db: DbSession) -> AssessmentRead:
    assessment = latest_assessment(db, user)
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No risk assessment yet")
    return AssessmentRead.model_validate(assessment)
