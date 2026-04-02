"""
Exams (clinic encounters)
=========================
RBAC
----
  Create / update / delete: admin, clinic_staff
  Read: all authenticated (end_user sees own exams only)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.database import get_db
from app.models.exam import Exam, ExamStatus, Package
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_role
from app.core.encryption import encryptor
from app.schemas.exam import ExamCreate, ExamUpdate, ExamResponse

router = APIRouter(prefix="/exams", tags=["exams"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(exam: Exam) -> ExamResponse:
    findings = None
    if exam.findings_encrypted:
        try:
            findings = encryptor.decrypt(exam.findings_encrypted)
        except Exception:
            findings = "[decryption error]"
    return ExamResponse(
        id=exam.id,
        patient_id=exam.patient_id,
        staff_id=exam.staff_id,
        package_id=exam.package_id,
        exam_type=exam.exam_type,
        findings=findings,
        status=exam.status,
        notes=exam.notes,
        scheduled_at=exam.scheduled_at,
        completed_at=exam.completed_at,
        created_at=exam.created_at,
    )


def _get_or_404(db: Session, exam_id: int) -> Exam:
    exam = db.execute(select(Exam).where(Exam.id == exam_id)).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


def _validate_package(db: Session, package_id: int) -> Package:
    """Ensure the package exists and is the currently active (confirmed) edition."""
    pkg = db.execute(select(Package).where(Package.id == package_id)).scalar_one_or_none()
    if not pkg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Package {package_id} not found",
        )
    if not pkg.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Package '{pkg.name}' version {pkg.version} is not active. "
                "Only the confirmed active edition can be scheduled for exams. "
                "Activate the correct version first via PATCH /packages/{id}/activate."
            ),
        )
    return pkg


def _validate_patient(db: Session, patient_id: int) -> User:
    from app.models.user import UserRole
    patient = db.execute(select(User).where(User.id == patient_id)).scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Patient (user id={patient_id}) not found",
        )
    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Patient account is inactive",
        )
    return patient


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "clinic_staff")),
):
    """
    Schedule an exam for a patient.

    If package_id is provided it must be the currently active (confirmed)
    edition of that package.  Using an inactive version is rejected so that
    staff always schedule against the correct edition.
    """
    _validate_patient(db, payload.patient_id)

    if payload.package_id is not None:
        _validate_package(db, payload.package_id)

    exam = Exam(
        patient_id=payload.patient_id,
        staff_id=current_user.id,
        package_id=payload.package_id,
        exam_type=payload.exam_type.strip(),
        scheduled_at=payload.scheduled_at,
        notes=payload.notes,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _to_response(exam)


@router.get("", response_model=list[ExamResponse])
def list_exams(
    patient_id: int | None = Query(default=None, description="Filter by patient (admin/staff only)"),
    exam_status: ExamStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Exam)

    if current_user.role == UserRole.end_user:
        # End-users can only see their own exams
        q = q.where(Exam.patient_id == current_user.id)
    elif patient_id is not None:
        q = q.where(Exam.patient_id == patient_id)

    if exam_status is not None:
        q = q.where(Exam.status == exam_status)

    exams = db.execute(q.order_by(Exam.scheduled_at.desc()).offset(skip).limit(limit)).scalars().all()
    return [_to_response(e) for e in exams]


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam = _get_or_404(db, exam_id)
    if current_user.role == UserRole.end_user and exam.patient_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _to_response(exam)


@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "clinic_staff")),
):
    """
    Update exam findings, status, or notes.
    Findings are encrypted at rest before storage.
    """
    exam = _get_or_404(db, exam_id)

    if exam.status == ExamStatus.completed and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed exams can only be modified by an administrator",
        )
    if exam.status == ExamStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancelled exams cannot be updated",
        )

    if payload.findings is not None:
        exam.findings_encrypted = encryptor.encrypt(payload.findings)
    if payload.status is not None:
        exam.status = payload.status
    if payload.notes is not None:
        exam.notes = payload.notes
    if payload.completed_at is not None:
        exam.completed_at = payload.completed_at

    # Auto-set completed_at if transitioning to completed
    if payload.status == ExamStatus.completed and exam.completed_at is None:
        from datetime import datetime, timezone
        exam.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(exam)
    return _to_response(exam)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Hard-delete an exam record (admin only).
    Completed exams cannot be deleted to preserve audit history.
    """
    exam = _get_or_404(db, exam_id)
    if exam.status == ExamStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed exams cannot be deleted (audit trail)",
        )
    db.delete(exam)
    db.commit()
