from django.db import migrations

# Migration scripts/utilities
from awx.main.migrations import _migration_utils as migration_utils
from awx.main.migrations import _rbac as rbac
from awx.main.migrations._create_system_jobs import create_clearsessions_jt, create_cleartokens_jt
from awx.main.migrations._create_credentialtypes import create_credentialtypes
from awx.main.migrations._galaxy import migrate_galaxy_settings


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20221012_2237'),
    ]

    operations = [
        # _migration_utils.py
        migrations.RunPython(migration_utils.set_current_apps_for_migrations),
        # _rbac.py
        migrations.RunPython(rbac.create_roles),
        # Create the managed credential types
        migrations.RunPython(create_credentialtypes, migrations.RunPython.noop),
        # _create_system_jobs.py
        migrations.RunPython(create_clearsessions_jt, migrations.RunPython.noop),
        migrations.RunPython(create_cleartokens_jt, migrations.RunPython.noop),
        #        migrations.RunPython(create_base_system_jobs, migrations.RunPython.noop),
        #        migrations.RunPython(create_new_credential_types, migrations.RunPython.noop),
        # These manage old data
        # _credentialtypes.py
        # _hg_removal.py
        # _inventory_source_vars.py
        # _multi_cred.py
        # _save_password_keys.py
        # _galaxy.py
        migrations.RunPython(migrate_galaxy_settings, migrations.RunPython.noop),
        # _inventory_source.py
        # _scan_jobs.py
    ]
