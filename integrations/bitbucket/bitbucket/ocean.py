import asyncio
from itertools import islice
from typing import Any, cast

from loguru import logger
from starlette.requests import Request

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.log.sensetive import sensitive_log_filter
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from bitbucket.bitbucket_service import BitbucketService
from bitbucket.utils import ObjectKind, get_cached_all_services

NO_WEBHOOK_WARNING = "Without setting up the webhook, the integration will not export live changes from Bitbucket"
RESYNC_BATCH_SIZE = 10

@ocean.router.post("/webhook/{workspace_id}")
async def handle_webhook_request(workspace_id: str, request: Request) -> dict[str, Any]:
    event_id = f"{request.headers.get('X-Event-Key')}:{workspace_id}"
    with logger.contextualize(event_id=event_id):
        try:
            logger.info(f"Received webhook event {event_id} from Bitbucket")
            body = await request.json()
            # Process webhook event based on X-Event-Key
            # Implement webhook handling logic here
            return {"ok": True}
        except Exception as e:
            logger.exception(
                f"Failed to handle webhook event {event_id} from Bitbucket, error: {e}"
            )
            return {"ok": False, "error": str(e)}

@ocean.on_start()
async def on_start() -> None:
    integration_config = ocean.integration_config
    credentials = integration_config.get("credentials", [])
    
    # Hide sensitive information in logs
    for cred in credentials:
        if cred.get("username"):
            sensitive_log_filter.hide_sensitive_strings(cred["username"])
        if cred.get("password"):
            sensitive_log_filter.hide_sensitive_strings(cred["password"])

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if not integration_config.get("app_host"):
        logger.warning(
            f"No app host provided, skipping webhook creation. {NO_WEBHOOK_WARNING}"
        )
        return

    # Initialize Bitbucket services
    try:
        services = get_cached_all_services()
        for service in services:
            # Setup webhooks for each workspace if needed
            pass
    except Exception as e:
        logger.exception(f"Failed to setup Bitbucket services: {e}. {NO_WEBHOOK_WARNING}")


@ocean.on_resync(ObjectKind.WORKSPACE)
async def resync_workspaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for workspaces_batch in service.get_all_workspaces():
            yield [workspace.asdict() for workspace in workspaces_batch]

@ocean.on_resync(ObjectKind.WORKSPACEWITHMEMBERS)
async def resync_workspaces_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for workspaces in service.get_all_workspaces():
            workspaces_batch_iter = iter(workspaces)
            workspaces_processed = 0

            while workspaces_batch := tuple(islice(workspaces_batch_iter, RESYNC_BATCH_SIZE)):
                workspaces_processed += len(workspaces_batch)
                logger.info(
                    f"Processing extras for {workspaces_processed}/{len(workspaces)} workspaces in batch"
                )
                tasks = [
                    service.enrich_workspace_with_members(workspace)
                    for workspace in workspaces_batch
                ]
                enriched_workspaces = await asyncio.gather(*tasks)
                yield [enriched_workspace.asdict() for enriched_workspace in enriched_workspaces]

@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        masked_username = len(str(service.bitbucket_client.username)[:-4]) * "*"
        logger.info(f"Fetching repositories for user {masked_username}")
        async for repositories in service.get_all_repositories():
            repositories_batch_iter = iter(repositories)
            repositories_processed = 0

            while repositories_batch := tuple(islice(repositories_batch_iter, RESYNC_BATCH_SIZE)):
                repositories_processed += len(repositories_batch)
                logger.info(
                    f"Processing extras for {repositories_processed}/{len(repositories)} repositories in batch"
                )
                tasks = [
                    service.enrich_repository_with_extras(repository)
                    for repository in repositories_batch
                ]
                enriched_repositories = await asyncio.gather(*tasks)
                yield [
                    enriched_repository.asdict() for enriched_repository in enriched_repositories
                ]


@ocean.on_resync(ObjectKind.PROJECTWITHMEMBERS)
async def resync_project_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        project_with_members_resource_config: GitlabObjectWithMembersResourceConfig = (
            typing.cast(GitlabObjectWithMembersResourceConfig, event.resource_config)
        )
        if not isinstance(
            project_with_members_resource_config, GitlabObjectWithMembersResourceConfig
        ):
            return

        project_with_members_selector = project_with_members_resource_config.selector
        include_inherited_members = (
            project_with_members_selector.include_inherited_members
        )
        include_bot_members = project_with_members_selector.include_bot_members

        async for projects in service.get_all_projects():
            projects_batch_iter = iter(projects)
            projects_processed_in_full_batch = 0
            while projects_batch := tuple(
                islice(projects_batch_iter, RESYNC_BATCH_SIZE)
            ):
                projects_processed_in_full_batch += len(projects_batch)
                logger.info(
                    f"Processing extras for {projects_processed_in_full_batch}/{len(projects)} projects in batch"
                )
                tasks = [
                    service.enrich_project_with_extras(project)
                    for project in projects_batch
                ]
                projects_enriched_with_extras = await asyncio.gather(*tasks)
                logger.info(
                    f"Finished Processing extras for {projects_processed_in_full_batch}/{len(projects)} projects in batch"
                )
                members_tasks = [
                    service.enrich_object_with_members(
                        project,
                        include_inherited_members,
                        include_bot_members,
                    )
                    for project in projects_enriched_with_extras
                ]
                projects_enriched_with_members = await asyncio.gather(*members_tasks)
                yield [
                    enriched_projects.asdict()
                    for enriched_projects in projects_enriched_with_members
                ]


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        gitlab_resource_config: GitlabResourceConfig = typing.cast(
            "GitlabResourceConfig", event.resource_config
        )
        if not isinstance(gitlab_resource_config, GitlabResourceConfig):
            return
        selector = gitlab_resource_config.selector
        async for projects_batch in service.get_all_projects():
            for folder_selector in selector.folders:
                for project in projects_batch:
                    if project.name in folder_selector.repos:
                        async for (
                            folders_batch
                        ) in service.get_all_folders_in_project_path(
                            project, folder_selector
                        ):
                            yield folders_batch


@ocean.on_resync(ObjectKind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        gitlab_resource_config: GitLabFilesResourceConfig = typing.cast(
            "GitLabFilesResourceConfig", event.resource_config
        )
        if not isinstance(gitlab_resource_config, GitLabFilesResourceConfig):
            logger.error("Invalid resource config type for GitLab files resync")
            return

        selector = gitlab_resource_config.selector

        if not (selector.files and selector.files.path):
            logger.warning("No path provided in the selector, skipping fetching files")
            return

        async for projects in service.get_all_projects():
            projects_batch_iter = iter(projects)
            projects_processed_in_full_batch = 0
            while projects_batch := tuple(
                islice(projects_batch_iter, RESYNC_BATCH_SIZE)
            ):
                projects_processed_in_full_batch += len(projects_batch)
                logger.info(
                    f"Processing project files for {projects_processed_in_full_batch}/{len(projects)} "
                    f"projects in batch: {[project.path_with_namespace for project in projects_batch]}"
                )
                tasks = []
                matching_projects = []
                for project in projects_batch:
                    if service.should_process_project(project, selector.files.repos):
                        matching_projects.append(project)
                        tasks.append(
                            service.search_files_in_project(
                                project, selector.files.path
                            )
                        )

                if tasks:
                    logger.info(
                        f"Found {len(tasks)} relevant projects in batch, projects: {[project.path_with_namespace for project in matching_projects]}"
                    )
                    async for batch in stream_async_iterators_tasks(*tasks):
                        yield batch
                else:
                    logger.info(
                        f"No relevant projects were found in batch for path '{selector.files.path}', skipping projects: {[project.path_with_namespace for project in projects_batch]}"
                    )
                logger.info(
                    f"Finished Processing project files for {projects_processed_in_full_batch}/{len(projects)}"
                )
        logger.info(
            f"Finished processing all projects for path '{selector.files.path}'"
        )


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    updated_after = datetime.now() - timedelta(days=14)

    for service in get_cached_all_services():
        async for groups_batch in service.get_all_root_groups():
            for group in groups_batch:
                async for merge_request_batch in service.get_opened_merge_requests(
                    group
                ):
                    yield [
                        merge_request.asdict() for merge_request in merge_request_batch
                    ]
                async for merge_request_batch in service.get_closed_merge_requests(
                    group, updated_after
                ):
                    yield [
                        merge_request.asdict() for merge_request in merge_request_batch
                    ]


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for groups_batch in service.get_all_root_groups():
            for group in groups_batch:
                async for issues_batch in service.get_all_issues(group):
                    yield [issue.asdict() for issue in issues_batch]


@ocean.on_resync(ObjectKind.JOB)
async def resync_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for projects_batch in service.get_all_projects():
            for project in projects_batch:
                async for jobs_batch in service.get_all_jobs(project):
                    yield [job.asdict() for job in jobs_batch]


@ocean.on_resync(ObjectKind.PIPELINE)
async def resync_pipelines(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for service in get_cached_all_services():
        async for projects_batch in service.get_all_projects():
            for project in projects_batch:
                logger.info(
                    f"Fetching pipelines for project {project.path_with_namespace}"
                )
                async for pipelines_batch in service.get_all_pipelines(project):
                    logger.info(
                        f"Found {len(pipelines_batch)} pipelines for project {project.path_with_namespace}"
                    )
                    yield [
                        {**pipeline.asdict(), "__project": project.asdict()}
                        for pipeline in pipelines_batch
                    ]
