from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule, env_fallback
from ansible.module_utils.six.moves import StringIO
from ansible.module_utils.six.moves.configparser import ConfigParser, NoOptionError
from ansible.module_utils.six.moves.urllib.parse import urlparse
from os.path import isfile, expanduser, split, join, exists, isdir
from os import access, R_OK, getcwd
from socket import gethostbyname
from distutils.util import strtobool
import re

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class ConfigFileException(Exception):
    pass


class TowerModule(AnsibleModule):
    honorred_settings = ('host', 'username', 'password', 'verify_ssl', 'oauth_token')
    host = '127.0.0.1'
    username = None
    password = None
    verify_ssl = True
    oauth_token = None
    oauth_token_id = None
    authenticated = False
    config_name = 'tower_cli.cfg'
    ENCRYPTED_STRING = "$encrypted$"

    def __init__(self, argument_spec, **kwargs):
        args = dict(
            tower_host=dict(required=False, fallback=(env_fallback, ['TOWER_HOST'])),
            tower_username=dict(required=False, fallback=(env_fallback, ['TOWER_USERNAME'])),
            tower_password=dict(no_log=True, required=False, fallback=(env_fallback, ['TOWER_PASSWORD'])),
            validate_certs=dict(type='bool', aliases=['tower_verify_ssl'], required=False, fallback=(env_fallback, ['TOWER_VERIFY_SSL'])),
            tower_oauthtoken=dict(type='str', no_log=True, required=False, fallback=(env_fallback, ['TOWER_OAUTH_TOKEN'])),
            tower_config_file=dict(type='path', required=False, default=None),
        )
        args.update(argument_spec)

        self.json_output = {'changed': False}

        super(TowerModule, self).__init__(argument_spec=args, **kwargs)

        self.load_config_files()

        # Parameters specified on command line will override settings in any config
        if self.params.get('tower_host'):
            self.host = self.params.get('tower_host')
        if self.params.get('tower_username'):
            self.username = self.params.get('tower_username')
        if self.params.get('tower_password'):
            self.password = self.params.get('tower_password')
        if self.params.get('validate_certs') is not None:
            self.verify_ssl = self.params.get('validate_certs')
        if self.params.get('tower_oauthtoken'):
            self.oauth_token = self.params.get('tower_oauthtoken')

        # Perform some basic validation
        if not re.match('^https{0,1}://', self.host):
            self.host = "https://{0}".format(self.host)

        # Try to parse the hostname as a url
        try:
            self.url = urlparse(self.host)
        except Exception as e:
            self.fail_json(msg="Unable to parse tower_host as a URL ({1}): {0}".format(self.host, e))

        # Try to resolve the hostname
        hostname = self.url.netloc.split(':')[0]
        try:
            gethostbyname(hostname)
        except Exception as e:
            self.fail_json(msg="Unable to resolve tower_host ({1}): {0}".format(hostname, e))

    def load_config_files(self):
        # Load configs like TowerCLI would have from least import to most
        config_files = ['/etc/tower/tower_cli.cfg', join(expanduser("~"), ".{0}".format(self.config_name))]
        local_dir = getcwd()
        config_files.append(join(local_dir, self.config_name))
        while split(local_dir)[1]:
            local_dir = split(local_dir)[0]
            config_files.insert(2, join(local_dir, ".{0}".format(self.config_name)))

        for config_file in config_files:
            if exists(config_file) and not isdir(config_file):
                # Only throw a formatting error if the file exists and is not a directory
                try:
                    self.load_config(config_file)
                except ConfigFileException as e:
                    self.fail_json(msg='The config file {0} is not properly formatted {1}'.format(config_file, e))

        # If we have a specified  tower config, load it
        if self.params.get('tower_config_file'):
            duplicated_params = []
            for direct_field in ('tower_host', 'tower_username', 'tower_password', 'validate_certs', 'tower_oauthtoken'):
                if self.params.get(direct_field):
                    duplicated_params.append(direct_field)
            if duplicated_params:
                self.warn((
                    'The parameter(s) {0} were provided at the same time as tower_config_file. '
                    'Precedence may be unstable, we suggest either using config file or params.'
                ).format(', '.join(duplicated_params)))
            try:
                # TODO: warn if there are conflicts with other params
                self.load_config(self.params.get('tower_config_file'))
            except ConfigFileException as cfe:
                # Since we were told specifically to load this we want it to fail if we have an error
                self.fail_json(msg=cfe)

    def load_config(self, config_path):
        # Validate the config file is an actual file
        if not isfile(config_path):
            raise ConfigFileException('The specified config file does not exist')

        if not access(config_path, R_OK):
            raise ConfigFileException("The specified config file cannot be read")

        # Read in the file contents:
        with open(config_path, 'r') as f:
            config_string = f.read()

        # First try to yaml load the content (which will also load json)
        try:
            config_data = yaml.load(config_string, Loader=yaml.SafeLoader)
            # If this is an actual ini file, yaml will return the whole thing as a string instead of a dict
            if type(config_data) is not dict:
                raise AssertionError("The yaml config file is not properly formatted as a dict.")

        except(AttributeError, yaml.YAMLError, AssertionError):
            # TowerCLI used to support a config file with a missing [general] section by prepending it if missing
            if '[general]' not in config_string:
                config_string = '[general]{0}'.format(config_string)

            config = ConfigParser()

            try:
                placeholder_file = StringIO(config_string)
                # py2 ConfigParser has readfp, that has been deprecated in favor of read_file in py3
                # This "if" removes the deprecation warning
                if hasattr(config, 'read_file'):
                    config.read_file(placeholder_file)
                else:
                    config.readfp(placeholder_file)

                # If we made it here then we have values from reading the ini file, so let's pull them out into a dict
                config_data = {}
                for honorred_setting in self.honorred_settings:
                    try:
                        config_data[honorred_setting] = config.get('general', honorred_setting)
                    except NoOptionError:
                        pass

            except Exception as e:
                raise ConfigFileException("An unknown exception occured trying to ini load config file: {0}".format(e))

        except Exception as e:
            raise ConfigFileException("An unknown exception occured trying to load config file: {0}".format(e))

        # If we made it here, we have a dict which has values in it from our config, any final settings logic can be performed here
        for honorred_setting in self.honorred_settings:
            if honorred_setting in config_data:
                # Veriffy SSL must be a boolean
                if honorred_setting == 'verify_ssl':
                    if type(config_data[honorred_setting]) is str:
                        setattr(self, honorred_setting, strtobool(config_data[honorred_setting]))
                    else:
                        setattr(self, honorred_setting, bool(config_data[honorred_setting]))
                else:
                    setattr(self, honorred_setting, config_data[honorred_setting])

    def logout(self):
        # This method is intended to be overridden
        pass

    def fail_json(self, **kwargs):
        # Try to log out if we are authenticated
        self.logout()
        super(TowerModule, self).fail_json(**kwargs)

    def exit_json(self, **kwargs):
        # Try to log out if we are authenticated
        self.logout()
        super(TowerModule, self).exit_json(**kwargs)
