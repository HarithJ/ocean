from enum import StrEnum
from datetime import datetime, timedelta
from typing import Any, Dict
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers import JQEntityProcessor
from pydantic import Field
from typing import List, Literal



class Kind(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    PROJECT = "project"
    USER = "user"


PULL_REQUEST_SEARCH_CRITERIA: list[dict[str, Any]] = [
    {"searchCriteria.status": "active"},
    {
        "searchCriteria.status": "abandoned",
        "searchCriteria.minTime": datetime.now() - timedelta(days=7),
    },
    {
        "searchCriteria.status": "completed",
        "searchCriteria.minTime": datetime.now() - timedelta(days=7),
    },
]


class BitbucketProjectResourceConfig(ResourceConfig):
    class BitbucketSelector(Selector):
        query: str
        default_team: bool = Field(
            default=False,
            description="If set to true, it ingests default team for each project to Port. This causes latency while syncing the entities to Port.  Default value is false. ",
            alias="defaultTeam",
        )

    kind: Literal["project"]
    selector: BitbucketSelector


class BitbucketRepositoryResourceConfig(ResourceConfig):
    class BitbucketSelector(Selector):
        query: str
        include_private: bool = Field(
            default=True,
            description="If set to true, it includes private repositories. Default value is true.",
            alias="includePrivate",
        )
        include_archived: bool = Field(
            default=False,
            description="If set to true, it includes archived repositories. Default value is false.",
            alias="includeArchived",
        )

    kind: Literal["repository"]
    selector: BitbucketSelector


class BitbucketPullRequestResourceConfig(ResourceConfig):
    class BitbucketSelector(Selector):
        query: str
        states: List[str] = Field(
            default=["OPEN", "MERGED", "DECLINED", "SUPERSEDED"],
            description="List of pull request states to include. Possible values are: OPEN, MERGED, DECLINED, SUPERSEDED.",
        )
        include_comments: bool = Field(
            default=True,
            description="If set to true, it includes pull request comments. Default value is true.",
            alias="includeComments",
        )
        include_activity: bool = Field(
            default=True,
            description="If set to true, it includes pull request activity (updates, approvals, etc). Default value is true.",
            alias="includeActivity",
        )
        max_age_days: int = Field(
            default=30,
            description="Maximum age in days for non-open pull requests to be included. Default value is 30 days.",
            alias="maxAgeDays",
            ge=1
        )

    kind: Literal["pull-request"]
    selector: BitbucketSelector


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            entity_processor = SearchEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)


class GitPortAppConfig(PortAppConfig):
    spec_path: List[str] | str = Field(alias="specPath", default="port.yml")
    use_default_branch: bool | None = Field(
        default=None,
        description=(
            "If set to true, it uses default branch of the repository"
            " for syncing the entities to Port. If set to false or None"
            ", it uses the branch mentioned in the `branch` config pro"
            "perty."
        ),
        alias="useDefaultBranch",
    )
    branch: str = "main"
    resources: list[
        BitbucketProjectResourceConfig |
        BitbucketRepositoryResourceConfig |
        BitbucketPullRequestResourceConfig
    ] = Field(default_factory=list)


def extract_branch_name_from_ref(ref: str) -> str:
    return "/".join(ref.split("/")[2:])
