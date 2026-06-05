"""Print a Gmail OAuth2 refresh_token to stdout.

Usage:
    python scripts/get_gmail_token.py client_secret_*.json

A browser window will open for authorization. After completing the flow the
refresh_token is printed to stdout. No file is written.
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/get_gmail_token.py <client_secret_file.json>", file=sys.stderr)
        sys.exit(1)

    client_secrets_file = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes=_SCOPES)
    credentials = flow.run_local_server(port=0)
    print(credentials.refresh_token)


if __name__ == "__main__":
    main()
