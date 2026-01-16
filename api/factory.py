"""
Data provider factory.
Creates provider instances based on configuration.
"""

from typing import Dict, Optional
from .base import DataProvider
from .massive import MassiveDataProvider
from .topstep import TopstepXDataProvider
from .file import FileDataProvider


class DataProviderFactory:
    """
    Factory for creating data provider instances.

    Handles provider instantiation and authentication.
    """

    @staticmethod
    def create_provider(
        provider_type: str,
        config: Dict[str, Optional[str]]
    ) -> DataProvider:
        """
        Create and authenticate a data provider.

        Args:
            provider_type: Provider type ('massive', 'topstepx', or 'file')
            config: Configuration dictionary with credentials

        Returns:
            Authenticated DataProvider instance

        Raises:
            ValueError: If provider type is unknown or config is invalid
            ConnectionError: If authentication fails
        """
        provider_type = provider_type.lower()

        if provider_type == 'massive':
            api_key = config.get('MASSIVE_API_KEY')
            if not api_key:
                raise ValueError(
                    "MASSIVE_API_KEY not found in configuration. "
                    "Please set it in your .env file."
                )

            provider = MassiveDataProvider(api_key=api_key)

        elif provider_type in ['topstepx', 'topstep']:
            username = config.get('TOPSTEP_USERNAME')
            password = config.get('TOPSTEP_PASSWORD')
            api_key = config.get('TOPSTEP_APIKEY')
            current_token = config.get('TOPSTEP_CURRENT_TOKEN')

            if not all([username, password, api_key]):
                raise ValueError(
                    "TopstepX credentials incomplete. Required: "
                    "TOPSTEP_USERNAME, TOPSTEP_PASSWORD, TOPSTEP_APIKEY. "
                    "Please set them in your .env file."
                )

            provider = TopstepXDataProvider(
                username=username,
                password=password,
                api_key=api_key,
                current_token=current_token
            )

        elif provider_type == 'file':
            data_dir = config.get('DATA_DIR', './data')
            provider = FileDataProvider(data_dir=data_dir)

        else:
            supported = DataProviderFactory.get_supported_providers()
            raise ValueError(
                f"Unknown provider type: '{provider_type}'. "
                f"Supported providers: {', '.join(supported)}"
            )

        # Authenticate provider
        if not provider.authenticate():
            raise ConnectionError(
                f"Failed to authenticate with {provider_type} provider. "
                "Please check your credentials in .env file."
            )

        print(f"✓ Successfully authenticated with {provider_type} provider")
        return provider

    @staticmethod
    def get_supported_providers() -> list:
        """
        Get list of supported provider types.

        Returns:
            list: Supported provider types
        """
        return ['massive', 'topstepx', 'file']
