import json
import asyncio

from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_iterator_result

from .base_client import HTTPBaseClient


API_VERSION = "2.0"
API_URL_PREFIX = "api"
MAX_PAGELEN = 100


class BitbucketClient(HTTPBaseClient):
    def __init__(self, workspace: str, personal_access_token: str) -> None:
        super().__init__(personal_access_token)
        self._workspace = workspace
        self._base_url = f"https://api.bitbucket.org/{API_VERSION}"

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        if cache := event.attributes.get("bitbucket_client"):
            return cache
        bitbucket_client = cls(
            ocean.integration_config["bitbucketWorkspace"],
            ocean.integration_config["bitbucketPassword"],
        )
        event.attributes["bitbucket_client"] = bitbucket_client
        return bitbucket_client

    async def get_single_repository(self, repo_slug: str) -> dict[str, Any]:
        repo_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}"
        repo = (await self.send_request("GET", repo_url)).json()
        return repo

    @cache_iterator_result()
    async def generate_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Generate all repositories in the workspace."""
        params = {"pagelen": MAX_PAGELEN}
        repos_url = f"{self._base_url}/repositories/{self._workspace}"
        
        while repos_url:
            response = await self.send_request("GET", repos_url, params=params)
            data = response.json()
            yield data["values"]
            
            repos_url = data.get("next")


    async def generate_pull_requests(
        self, repo_slug: str, state: str = "OPEN"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Generate pull requests for a specific repository.
        
        Args:
            repo_slug: The repository slug
            state: Filter PRs by state (OPEN, MERGED, DECLINED, SUPERSEDED)
        """
        params = {"pagelen": MAX_PAGELEN, "state": state}
        prs_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests"
        
        while prs_url:
            response = await self.send_request("GET", prs_url, params=params)
            data = response.json()
            yield data["values"]
            
            prs_url = data.get("next")

    async def get_pull_request(
        self, repo_slug: str, pull_request_id: int
    ) -> dict[str, Any]:
        """Get a specific pull request by ID.
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
        """
        pr_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        response = await self.send_request("GET", pr_url)
        return response.json()
        return pull_request_data

    async def get_repository(self, repository_id: str) -> dict[Any, Any]:
        get_single_repository_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/repositories/{repository_id}"
        response = await self.send_request("GET", get_single_repository_url)
        repository_data = response.json()
        return repository_data

    async def merge_pull_request(self, repo_slug: str, pull_request_id: int, message: Optional[str] = None) -> dict[str, Any]:
        """Merge a pull request.
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
            message: Optional merge commit message
        """
        pr_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}/merge"
        data = {"message": message} if message else {}
        response = await self.send_request("POST", pr_url, json=data)
        return response.json()

    async def decline_pull_request(self, repo_slug: str, pull_request_id: int) -> dict[str, Any]:
        """Decline a pull request.
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
        """
        pr_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}/decline"
        response = await self.send_request("POST", pr_url)
        return response.json()

    async def update_pull_request_reviewers(self, repo_slug: str, pull_request_id: int, reviewers: list[str]) -> dict[str, Any]:
        """Update the reviewers of a pull request.
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
            reviewers: List of reviewer UUIDs
        """
        pr_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        data = {"reviewers": [{"uuid": reviewer} for reviewer in reviewers]}
        response = await self.send_request("PUT", pr_url, json=data)
        return response.json()

    async def get_pull_request_comments(self, repo_slug: str, pull_request_id: int) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get comments on a pull request.
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
        """
        params = {"pagelen": MAX_PAGELEN}
        comments_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}/comments"
        
        while comments_url:
            response = await self.send_request("GET", comments_url, params=params)
            data = response.json()
            yield data["values"]
            
            comments_url = data.get("next")

    async def add_pull_request_comment(self, repo_slug: str, pull_request_id: int, content: str) -> dict[str, Any]:
        """Add a comment to a pull request.
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
            content: The comment content in raw format
        """
        comments_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}/comments"
        data = {"content": {"raw": content}}
        response = await self.send_request("POST", comments_url, json=data)
        return response.json()

    async def get_pull_request_activity(self, repo_slug: str, pull_request_id: int) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get activity feed for a pull request (comments, updates, approvals, etc).
        
        Args:
            repo_slug: The repository slug
            pull_request_id: The pull request ID
        """
        params = {"pagelen": MAX_PAGELEN}
        activity_url = f"{self._base_url}/repositories/{self._workspace}/{repo_slug}/pullrequests/{pull_request_id}/activity"
        
        while activity_url:
            response = await self.send_request("GET", activity_url, params=params)
            data = response.json()
            yield data["values"]
            
            activity_url = data.get("next")

