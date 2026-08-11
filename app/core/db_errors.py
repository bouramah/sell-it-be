from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fastapi import HTTPException


def commit_or_409(db: Session, message: str) -> None:
    """Commit the current transaction, turning a FK violation into a clean 409
    instead of letting an unhandled IntegrityError bubble up as a 500."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=message)
