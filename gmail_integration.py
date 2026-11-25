"""Read-only Gmail integration for Student Ecosystem."""

import base64
import logging
import secrets
from pathlib import Path

from bs4 import BeautifulSoup
from flask import Blueprint, current_app, jsonify, redirect, request, session

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ai_summarizer import summarize_notice
from config import Config
from database import create_summary


logger = logging.getLogger(__name__)

gmail_bp = Blueprint("gmail", __name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def token_path():
    return Path(current_app.config["GMAIL_TOKEN_FILE"])


def save_credentials(credentials):
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")
    temporary.write_text(credentials.to_json(), encoding="utf-8")
    temporary.replace(path)


def load_credentials():
    path = token_path()

    if not path.exists():
        return None

    try:
        credentials = Credentials.from_authorized_user_file(
            str(path), SCOPES
        )

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_credentials(credentials)

        if not credentials.valid:
            return None

        return credentials

    except (OSError, ValueError):
        logger.exception("Could not load Gmail credentials")
        return None


def gmail_service(credentials):
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def decode_body(data):
    if not data:
        return ""

    decoded = base64.urlsafe_b64decode(data)
    return decoded.decode("utf-8", errors="replace")


def extract_email_body(payload):
    plain_parts = []
    html_parts = []

    def visit(part):
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})

        if body.get("data"):
            content = decode_body(body["data"])

            if mime_type == "text/plain":
                plain_parts.append(content)
            elif mime_type == "text/html":
                html_parts.append(content)

        for child in part.get("parts", []):
            visit(child)

    visit(payload)

    if plain_parts:
        return "\n".join(plain_parts)

    if html_parts:
        soup = BeautifulSoup(
            "\n".join(html_parts), "html.parser"
        )
        return soup.get_text(separator="\n", strip=True)

    return ""


@gmail_bp.get("/auth/google")
def google_login():
    credentials_file = current_app.config[
        "GOOGLE_CLIENT_SECRETS_FILE"
    ]

    if not Path(credentials_file).is_file():
        return jsonify({"error": "Google credentials file not found."}), 500

    flow = Flow.from_client_secrets_file(
        credentials_file,
        scopes=SCOPES,
    )
    flow.redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    session["gmail_oauth_state"] = state
    return redirect(authorization_url)


@gmail_bp.get("/auth/google/callback")
def google_callback():
    expected_state = session.pop("gmail_oauth_state", None)
    received_state = request.args.get("state", "")

    if not expected_state or not secrets.compare_digest(
        expected_state, received_state
    ):
        return jsonify({"error": "Invalid OAuth state. Please reconnect."}), 400

    if request.args.get("error"):
        return jsonify({"error": "Google authorization was not completed."}), 400

    try:
        flow = Flow.from_client_secrets_file(
            current_app.config["GOOGLE_CLIENT_SECRETS_FILE"],
            scopes=SCOPES,
            state=expected_state,
        )
        flow.redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        save_credentials(credentials)

        return redirect("/#mail")

    except Exception:
        logger.exception("Google OAuth callback failed")
        return jsonify({"error": "Could not complete Google authorization."}), 400


@gmail_bp.get("/api/gmail/status")
def gmail_status():
    credentials = load_credentials()
    return jsonify({"connected": bool(credentials and credentials.valid)})


@gmail_bp.get("/api/gmail/messages")
def gmail_messages():
    credentials = load_credentials()

    if not credentials:
        return jsonify({"error": "Connect Gmail first."}), 401

    try:
        service = gmail_service(credentials)

        result = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=10,
        ).execute()

        messages = []

        for item in result.get("messages", []):
            message = service.users().messages().get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()

            headers = {
                header["name"].lower(): header["value"]
                for header in message.get("payload", {}).get("headers", [])
            }

            messages.append({
                "id": item["id"],
                "subject": headers.get("subject", "(No subject)"),
                "sender": headers.get("from", "Unknown sender"),
                "date": headers.get("date", ""),
                "snippet": message.get("snippet", ""),
            })

        return jsonify({"messages": messages})

    except HttpError:
        logger.exception("Gmail API request failed")
        return jsonify({"error": "Could not read Gmail messages."}), 502


@gmail_bp.post("/api/gmail/messages/<message_id>/summarize")
def summarize_gmail_message(message_id):
    credentials = load_credentials()

    if not credentials:
        return jsonify({"error": "Connect Gmail first."}), 401

    try:
        service = gmail_service(credentials)

        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()

        headers = {
            header["name"].lower(): header["value"]
            for header in message.get("payload", {}).get("headers", [])
        }

        subject = headers.get("subject", "(No subject)")
        sender = headers.get("from", "Unknown sender")
        body = extract_email_body(message.get("payload", {}))

        body = body[:Config.AI_MAX_INPUT_CHARS]

        if len(body.strip()) < 20:
            return jsonify({"error": "This email does not contain enough readable text."}), 422

        summary = summarize_notice(
            body,
            subject=subject,
            sender=sender,
        )

        saved = create_summary({
            **summary,
            "subject": subject,
            "sender": sender,
            "source": "gmail",
            "body": body,
        })

        return jsonify({
            "summary": saved,
            "ai_mode": summary.get("mode", "heuristic"),
        }), 201

    except HttpError:
        logger.exception("Could not fetch Gmail message")
        return jsonify({"error": "Could not retrieve this email."}), 502


@gmail_bp.post("/api/gmail/disconnect")
def gmail_disconnect():
    path = token_path()

    if path.exists():
        path.unlink()

    session.pop("gmail_oauth_state", None)
    return jsonify({"connected": False})
