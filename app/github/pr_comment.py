import logging
from typing import Optional
import httpx

from app.config import get_settings
from app.llm.schemas import CIFailureAnalysisResult

logger = logging.getLogger(__name__)


async def post_pr_comment(
    owner: str,
    repo: str,
    pr_number: int,
    analysis: CIFailureAnalysisResult,
    github_token: Optional[str] = None,
) -> bool:
    """Post markdown analysis comment on GitHub Pull Request."""
    token = github_token or get_settings().GITHUB_TOKEN
    if not token:
        logger.info(f"Mocking PR comment post for PR #{pr_number} (no GITHUB_TOKEN configured).")
        return True

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"

    comment_body = f"""### 🛡️ AI DevGuard - CI Failure Analysis

**Category:** `{analysis.failure_category}`
**Confidence:** `{analysis.confidence * 100:.0f}%`

#### 🔍 Root Cause Analysis
{analysis.root_cause}

#### 💡 Suggested Fix
{analysis.suggested_fix}

---
*Reported automatically by AI DevGuard*
"""

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.post(url, headers=headers, json={"body": comment_body})
            res.raise_for_status()
            logger.info(f"Successfully posted PR comment on {owner}/{repo}#{pr_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to post PR comment on {owner}/{repo}#{pr_number}: {e}")
            return False
