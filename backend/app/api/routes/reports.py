from datetime import date

from fastapi import APIRouter, Response

from app.api.deps import Audit, CurrentUser, DbSession
from app.services.reports import plan_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/plan",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The plan as a PDF"}},
)
def download_plan(user: CurrentUser, db: DbSession, audit: Audit) -> Response:
    """The user's whole plan (profile, goals, recommendations, retirement, investments) as a PDF."""
    pdf = plan_pdf(db, user)
    audit("report.download", user, details={"bytes": len(pdf)})
    filename = f"goalwise-plan-{date.today().isoformat()}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",  # personal financial data: never cache
        },
    )
