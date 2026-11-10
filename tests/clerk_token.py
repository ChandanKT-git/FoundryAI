import os, json, sys, urllib.request, urllib.parse
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
SK = os.environ["CLERK_SECRET_KEY"]


def bapi(path, body=None, method="POST"):
    req = urllib.request.Request("https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json", "User-Agent": "foundryai-test"})
    return json.load(urllib.request.urlopen(req))


def get_user(email):
    found = bapi("/users?email_address=" + urllib.parse.quote(email), method="GET")
    if found:
        return found[0]
    return bapi("/users", {"email_address": [email], "password": "Forge-test-12345!", "skip_password_checks": True})


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "forge.a+clerk_test@example.com"
    mode = sys.argv[2] if len(sys.argv) > 2 else "token"
    user = get_user(email)
    if mode == "ticket":
        print(bapi("/sign_in_tokens", {"user_id": user["id"], "expires_in_seconds": 3600})["token"])
    else:
        s = bapi("/sessions", {"user_id": user["id"]})
        print(bapi(f"/sessions/{s['id']}/tokens", {"expires_in_seconds": 3600})["jwt"])
