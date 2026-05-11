from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_report(subject: str, body: str, attachment_path: str | None = None) -> None:
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("REPORT_RECIPIENT")

    missing = [
        name
        for name, value in {
            "GMAIL_USER": gmail_user,
            "GMAIL_APP_PASSWORD": gmail_password,
            "REPORT_RECIPIENT": recipient,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing email environment variables: {', '.join(missing)}")

    message = EmailMessage()
    message["From"] = gmail_user
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if attachment_path:
        with open(attachment_path, "rb") as file:
            data = file.read()
        filename = os.path.basename(attachment_path)
        message.add_attachment(
            data,
            maintype="text",
            subtype="markdown",
            filename=filename,
        )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(message)
