import os
import subprocess
from pathlib import Path
import pytest
import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / "frontend" / ".env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000").rstrip("/")
SAMPLE_PID = "21b2a60b-be4c-490b-83d5-fe54f3822298"


def _token(email):
    return subprocess.check_output(["python3", str(ROOT_DIR / "tests" / "clerk_token.py"), email], text=True).strip()


@pytest.fixture(scope="session")
def token_a():
    return _token("forge.a+clerk_test@example.com")


@pytest.fixture(scope="session")
def token_b():
    return _token("forge.b+clerk_test@example.com")


@pytest.fixture
def client_a(token_a):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"})
    return s


@pytest.fixture
def client_b(token_b):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"})
    return s
