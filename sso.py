import os
import hmac
import time

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

SSO_SALT = "cow-sso-v1"
TOKEN_MAX_AGE = 60

CLIENTS = {
    "library": {
        "name": "Library",
        "redirect_uri": "https://library.theorangecow.org/auth/cow/callback",
        "secret": os.environ.get("CLIENT_SECRET_LIBRARY", "dev-secret-library"),
    },
    "house-778": {
        "name": "House-778",
        "redirect_uri": "https://house-778.theorangecow.org/auth/cow/callback",
        "secret": os.environ.get("CLIENT_SECRET_HOUSE778", "dev-secret-house778"),
    },
    "cow-servers": {
        "name": "Cow Servers",
        "redirect_uri": "https://cow-servers.theorangecow.org/auth/cow/callback",
        "secret": os.environ.get("CLIENT_SECRET_COWSERVERS", "dev-secret-cowservers"),
    },
    "brain-wave": {
        "name": "Brain Wave",
        "redirect_uri": "https://brain-wave.theorangecow.org/auth/cow/callback",
        "secret": os.environ.get("CLIENT_SECRET_BRAINWAVE", "dev-secret-brainwave"),
    },
}

_used_tokens = {}


def _serializer(secret_key):
    return URLSafeTimedSerializer(secret_key, salt=SSO_SALT)


def issue_token(secret_key, user_id, username, client_id):
    payload = {"uid": user_id, "username": username, "client_id": client_id}
    return _serializer(secret_key).dumps(payload)


def redeem_token(secret_key, token, client_id):
    _cleanup_used_tokens()

    if token in _used_tokens:
        raise ValueError("token already used")

    try:
        payload = _serializer(secret_key).loads(token, max_age=TOKEN_MAX_AGE)
    except SignatureExpired:
        raise ValueError("token expired")
    except BadSignature:
        raise ValueError("invalid token")

    if payload.get("client_id") != client_id:
        raise ValueError("token was not issued for this client")

    _used_tokens[token] = time.time()
    return payload


def _cleanup_used_tokens():
    cutoff = time.time() - (TOKEN_MAX_AGE * 4)
    for t, ts in list(_used_tokens.items()):
        if ts < cutoff:
            _used_tokens.pop(t, None)


def check_client_secret(client_id, provided_secret):
    client = CLIENTS.get(client_id)
    if not client or not provided_secret:
        return False
    return hmac.compare_digest(client["secret"], provided_secret)
