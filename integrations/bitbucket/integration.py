"""
Bitbucket integration module.
"""
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from bitbucket.models import BitbucketPortAppConfig


class BitbucketIntegration(BaseIntegration):
    """Bitbucket integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        """Bitbucket app config handler class."""

        CONFIG_CLASS = BitbucketPortAppConfig
