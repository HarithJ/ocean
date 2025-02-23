from typing import List

from atlassian import Bitbucket
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.context import EventContextNotFoundError
from bitbucket.bitbucket_service import BitbucketService


def generate_bitbucket_client(host: str, username: str, password: str) -> Bitbucket:
    try:
        bitbucket_client = Bitbucket(
            url=host,
            username=username,
            password=password
        )
        logger.info("Successfully authenticated with Bitbucket")
        return bitbucket_client
    except Exception as e:
        logger.error(f"Failed to authenticate with Bitbucket: {str(e)}")
        raise


def get_all_services() -> List[BitbucketService]:
    logic_settings = ocean.integration_config
    all_services = []

    logger.info(
        f"Creating Bitbucket clients for {len(logic_settings['credentials'])} credentials"
    )
    for cred in logic_settings["credentials"]:
        bitbucket_client = generate_bitbucket_client(
            logic_settings["bitbucket_host"],
            cred["username"],
            cred["password"]
        )
        bitbucket_service = BitbucketService(
            bitbucket_client,
            logic_settings["app_host"],
            cred.get("workspace_filter", [])
        )
        all_services.append(bitbucket_service)

    return all_services


def get_cached_all_services() -> List[BitbucketService]:
    try:
        all_services = event.attributes.get("all_bitbucket_services")
        if not all_services:
            logger.info("Bitbucket clients are not cached, creating them")
            all_services = get_all_services()
            event.attributes["all_bitbucket_services"] = all_services
        return all_services
    except EventContextNotFoundError:
        return get_all_services()


class ObjectKind:
    WORKSPACE = "workspace"
    REPOSITORY = "repository"
    ISSUE = "issue"
    PULL_REQUEST = "pull-request"
    PIPELINE = "pipeline"
    BRANCH = "branch"
    FOLDER = "folder"
    FILE = "file"
    WORKSPACEWITHMEMBERS = "workspace-with-members"
    REPOSITORYWITHMEMBERS = "repository-with-members"
