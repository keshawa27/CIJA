"""Notifications. Rows are written inside the caller's transaction; email is sent
afterwards by `deliver_pending`, so a failed send never rolls back the work itself."""

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import db as database
from .config import settings
from .models import Intake, Notification, User, now

log = logging.getLogger(__name__)


def email_client(db: Session, intake: Intake, subject: str, body: str) -> None:
    """Emails the client only if they said email is safe. Callers must keep the
    subject and body free of sensitive detail: someone else may read the inbox."""
    if intake.safe_contact_method == "email" and intake.email:
        db.add(Notification(intake_id=intake.id, channel="email", recipient=intake.email,
                            subject=subject, body=body))


def notify_staff(db: Session, user: User, intake: Intake, subject: str, body: str) -> None:
    db.add(Notification(intake_id=intake.id, channel="in_app", user_id=user.id, recipient=user.name,
                        subject=subject, body=body, status="sent", sent_at=now()))
    db.add(Notification(intake_id=intake.id, channel="email", recipient=user.email,
                        subject=subject, body=body))


def _send_email(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.mail_from, to, subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)


def deliver_pending() -> None:
    """Send every pending email. Run as a background task after a commit."""
    # ponytail: in-process delivery, no automatic retry of failed rows.
    # Move to a queue/worker if volume or retries start to matter.
    with database.SessionLocal() as db:
        pending = db.scalars(
            select(Notification)
            .where(Notification.channel == "email", Notification.status == "pending")
            .with_for_update(skip_locked=True)  # two concurrent runs never send the same row twice
        ).all()
        for notification in pending:
            try:
                _send_email(notification.recipient, notification.subject, notification.body)
                notification.status, notification.sent_at = "sent", now()
            except OSError:
                log.exception("Email delivery failed for notification %s", notification.id)
                notification.status = "failed"
        db.commit()
