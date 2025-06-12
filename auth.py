from functools import cache
import json
import os
import base64
import re
from shutil import ExecError
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.types import PublicKeyTypes
from cryptography.hazmat.primitives.asymmetric import padding


@cache
def _get_public_key() -> PublicKeyTypes:
    res = requests.get(
        "https://static.gopro.com/web-apps/assets/login/f52b4689338c803186ba4415d64b04814fae7c85/_next/static/chunks/pages/index-4f91eade1abfab95.js"
    )
    res.raise_for_status()
    if not (
        match := re.search(
            r"(?P<pem>-----BEGIN PUBLIC KEY-----.*-----END PUBLIC KEY-----)",
            res.text,
        )
    ) or not (pem := match.group("pem")):
        raise Exception("Could not find public key")

    # if not (pem := match.group("pem")):
    #     raise Exception("Could not find public key")
    return serialization.load_pem_public_key(pem.encode("utf-8"))


def _encrypt_with_public_key(data: str) -> str:
    """
    Encrypts data using the provided RSA public key.
    """
    public_key = _get_public_key()
    encrypted_data = public_key.encrypt(
        data.encode("utf-8"),
        padding.PKCS1v15(),  # Corresponds to crypto.constants.RSA_PKCS1_PADDING
    )
    return base64.b64encode(encrypted_data).decode("utf-8")


def get_token() -> tuple[str, str]:
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    if not email:
        raise ValueError("EMAIL environment variable must be set")
    if not password:
        raise ValueError("PASSWORD environment variable must be set")

    encrypted_password = _encrypt_with_public_key(password)
    headers = {
        "Accept": "application/vnd.gopro.jk.media+json; version=2.0.0",
        "Accept-Language": "en-US,en;q=0.9,bg;q=0.8,es;q=0.7",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    payload = {
        "email": email,
        "password": encrypted_password,
        "redirectUri": "https://gopro.com/en/us/",
        "redirect_uri": "https://gopro.com/en/us/",
    }

    try:
        response = requests.post(
            "https://gopro.com/login/api/login", headers=headers, json=payload
        )
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

    except requests.exceptions.RequestException as e:
        print(f"Failed to authenticate: {e}\n{response.text}")
        raise

    gp_user_id = response.cookies["gp_user_id"]
    gp_access_token = response.cookies["gp_access_token"]
    _write_latest_token(gp_user_id, gp_access_token)
    return gp_user_id, gp_access_token


_LATEST_TOKEN_FILE = ".latesttoken.json"


def _write_latest_token(user: str, token: str) -> None:
    with open(_LATEST_TOKEN_FILE, "w") as f:
        json.dump({"user": user, "token": token}, f)

    os.chmod(_LATEST_TOKEN_FILE, 0o400)


def read_latest_token() -> tuple[str, str]:
    with open(_LATEST_TOKEN_FILE, "r") as f:
        d = json.load(f)

    return d["user"], d["token"]


if __name__ == "__main__":
    print(get_token())
