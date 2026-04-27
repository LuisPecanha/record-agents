"""Gmail API client. No business logic."""

import email
import email.header
import email.message
import imaplib
import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class GmailClient:
    def __init__(self):
        email_address = os.getenv("BALTERS_EMAIL")
        app_password = os.getenv("GMAIL_APP_PASSWORD")

        if not email_address:
            raise EnvironmentError("BALTERS_EMAIL not found in environment.")
        if not app_password:
            raise EnvironmentError("GMAIL_APP_PASSWORD not found in environment.")

        self.email_address: str = email_address
        self.app_password: str = app_password

        print(f"[GmailClient] Initialized for {self.email_address}")

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        conn.login(self.email_address, self.app_password)
        return conn

    def _decode_header(self, value: str) -> str:
        parts = email.header.decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return "".join(decoded)

    def _extract_plain_text(self, msg: email.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and part.get("Content-Disposition") is None:
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="replace")  # type: ignore[union-attr]
        else:
            if msg.get_content_type() == "text/plain":
                charset = msg.get_content_charset() or "utf-8"
                return msg.get_payload(decode=True).decode(charset, errors="replace")  # type: ignore[union-attr]
        return ""

    def get_unread_messages(self) -> list[dict]:
        try:
            conn = self._connect_imap()
            conn.select("INBOX")

            status, data = conn.uid("search", None, "UNSEEN")  # type: ignore[arg-type]
            if status != "OK" or not data[0]:
                conn.logout()
                return []

            uids = data[0].split()
            messages = []

            for uid in uids:
                status, msg_data = conn.uid("fetch", uid, "(BODY.PEEK[])")
                if status != "OK":
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                messages.append({
                    "id": uid.decode(),
                    "thread_id": msg.get("Message-ID", ""),
                    "from": self._decode_header(msg.get("From", "")),
                    "subject": self._decode_header(msg.get("Subject", "")),
                    "body": self._extract_plain_text(msg),
                    "date": msg.get("Date", ""),
                })

            conn.logout()
            print(f"[GmailClient] Fetched {len(messages)} unread message(s).")
            return messages

        except Exception as e:
            print(f"[GmailClient] get_unread_messages error: {e}")
            return []

    def create_draft(self, to: str, subject: str, body: str, thread_id: str | None = None) -> bool:
        try:
            now = datetime.now(timezone.utc)

            mime = MIMEMultipart()
            mime["From"] = self.email_address
            mime["To"] = to
            mime["Subject"] = subject
            mime["Date"] = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

            if thread_id:
                mime["In-Reply-To"] = thread_id
                mime["References"] = thread_id

            mime.attach(MIMEText(body, "plain", "utf-8"))

            conn = self._connect_imap()

            draft_folders = ["[Gmail]/Drafts", "[Gmail]/Rascunhos"]
            appended = False

            for folder in draft_folders:
                try:
                    status, _ = conn.append(
                        folder,
                        "\\Draft",
                        imaplib.Time2Internaldate(now.timetuple()),
                        mime.as_bytes(),
                    )
                    if status == "OK":
                        print(f"[GmailClient] Draft saved to {folder}.")
                        appended = True
                        break
                except Exception:
                    continue

            conn.logout()

            if not appended:
                print("[GmailClient] create_draft: could not find Drafts folder.")

            return appended

        except Exception as e:
            print(f"[GmailClient] create_draft error: {e}")
            return False

    def mark_as_read(self, uid: str) -> bool:
        try:
            conn = self._connect_imap()
            conn.select("INBOX")
            status, _ = conn.uid("store", uid, "+FLAGS", "\\Seen")
            conn.logout()

            if status == "OK":
                print(f"[GmailClient] Message {uid} marked as read.")
                return True

            print(f"[GmailClient] mark_as_read: unexpected status {status} for UID {uid}.")
            return False

        except Exception as e:
            print(f"[GmailClient] mark_as_read error: {e}")
            return False

    def send_message(self):
        raise NotImplementedError(
            "Agents never send emails automatically. Use create_draft() to stage a reply "
            "and let a human review and send it from Gmail."
        )
