import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_github_signature(
    body_bytes: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """Verify GitHub webhook payload HMAC SHA-256 signature.

    Args:
        body_bytes: Raw request body bytes.
        signature_header: Content of 'X-Hub-Signature-256' header (format 'sha256=...').
        secret: Webhook secret configured in GitHub repository settings.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not secret or not signature_header:
        logger.warning("Missing secret or signature header for GitHub webhook verification")
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header.split("sha256=")[1]
    mac = hmac.new(secret.encode("utf-8"), msg=body_bytes, digestmod=hashlib.sha256)
    computed_sig = mac.hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)
