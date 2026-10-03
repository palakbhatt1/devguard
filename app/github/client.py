import io
import logging
import zipfile
from typing import Optional
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def download_workflow_log(
    owner: str,
    repo: str,
    run_id: int,
    github_token: Optional[str] = None,
) -> str:
    """Download and extract raw text logs from GitHub Actions workflow run endpoint.

    Falls back to a realistic sample log if running offline or without GitHub token.
    """
    token = github_token or get_settings().GITHUB_TOKEN
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"

    if not token:
        logger.info(f"No GITHUB_TOKEN set. Returning sample mock log for run {run_id}.")
        return (
            "2024-03-30T10:00:00.000Z Run pytest tests/\n"
            "2024-03-30T10:00:01.000Z pytest tests/\n"
            "2024-03-30T10:00:02.000Z FAILED tests/test_main.py::test_api_status - AssertionError: 500 != 200\n"
            "2024-03-30T10:00:03.000Z Process completed with exit code 1.\n"
        )

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            # GitHub returns a zip file containing log text files
            if response.headers.get("content-type", "").startswith("application/zip") or response.content[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    log_contents = []
                    for filename in z.namelist():
                        if filename.endswith(".txt"):
                            log_contents.append(z.read(filename).decode("utf-8", errors="ignore"))
                    return "\n".join(log_contents)

            return response.text
        except Exception as e:
            logger.error(f"Error downloading log from GitHub API: {e}")
            return f"Failed to download log for run {run_id}: {e}"
