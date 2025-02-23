from pydantic import BaseModel


class BitbucketWebhookGroupConfig(BaseModel):
    events: list[str]  # Bitbucket webhook event names (e.g., 'repo:push', 'repo:commit_comment_created')


class BitbucketWebhookTokenConfig(BaseModel):
    groups: dict[str, BitbucketWebhookGroupConfig]  # Mapping of group names to their webhook configurations


class BitbucketWebhookMappingConfig(BaseModel):
    tokens: dict[str, BitbucketWebhookTokenConfig]  # Mapping of workspace tokens to their webhook configurations
