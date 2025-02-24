from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from starlette.requests import Request

from bitbucket.client.bitbucket_client import BitbucketClient
from bitbucket.misc import Kind


@ocean.on_start()
async def setup_webhooks() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    if not ocean.integration_config.get("app_host"):
        logger.warning("No app host provided, skipping webhook creation.")
        return

    bitbucket_client = BitbucketClient.create_from_ocean_config()
    async for repositories in bitbucket_client.generate_repositories():
        for repo in repositories:
            logger.info(f"Setting up webhook for repository {repo['name']}")
            await setup_webhook(
                ocean.integration_config["app_host"],
                bitbucket_client,
                repo["slug"]
            )


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    bitbucket_client = BitbucketClient.create_from_ocean_config()
    async for repositories in bitbucket_client.generate_repositories():
        for repository in repositories:
            yield {
                "entity": repository,
                "kind": kind,
            }
        logger.info(f"Resyncing {len(projects)} projects")
        yield projects


@ocean.on_resync(Kind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    azure_devops_client = AzureDevopsClient.create_from_ocean_config()
    async for users in azure_devops_client.generate_users():
        logger.info(f"Resyncing {len(users)} members")
        yield users


@ocean.on_resync(Kind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    bitbucket_client = BitbucketClient.create_from_ocean_config()
    async for repositories in bitbucket_client.generate_repositories():
        for repository in repositories:
            async for pull_requests in bitbucket_client.generate_pull_requests(repository["slug"]):
                logger.info(f"Resyncing {len(pull_requests)} pull requests from {repository['name']}")
                for pull_request in pull_requests:
                    yield {
                        "entity": pull_request,
                        "kind": kind,
                    }


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    bitbucket_client = BitbucketClient.create_from_ocean_config()
    async for repositories in bitbucket_client.generate_repositories():
        logger.info(f"Resyncing {len(repositories)} repositories")
        for repository in repositories:
            yield {
                "entity": repository,
                "kind": kind,
            }


@ocean.router.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    event_data = await request.json()
    await handle_webhook(event_data)
    return {"ok": True}
