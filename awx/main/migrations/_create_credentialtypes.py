import logging

from awx.main.models import CredentialType as ModernCredentialType
from awx.main.utils.common import set_current_apps

logger = logging.getLogger('awx.main.migrations')

__all__ = [
    'create_credentialtypes',
]

'''
These methods are called by migrations to create the managed credential types
'''


def create_credentialtypes(apps, schema_editor):
    set_current_apps(apps)
    ModernCredentialType.setup_tower_managed_defaults(apps)
