#!/usr/bin/env python

import requests
import json
import os
import sys

session = requests.Session()

try:
    with open(".github_creds", "r") as f:
        user, password = f.read().strip().split(":")
    print("Loading credentials")
    session.auth(user, password)
except Exception:
    pass

print("Getting current versions")
response = session.get('https://api.github.com/repos/ansible/awx/releases', headers={'Accept': 'application/vnd.github.v3+json'})
print(json.dumps(response.json(), indent=4))
awx_version = response.json()[0]['tag_name']
print("    AWX: {}".format(awx_version))
response = session.get('https://api.github.com/repos/ansible/awx-operator/releases', headers={'Accept': 'application/vnd.github.v3+json'})
operator_version = response.json()[0]['tag_name']
print("    Operator: {}".format(operator_version))

response = session.get('https://api.github.com/repos/ansible/awx/compare/{}...devel'.format(awx_version), headers={'Accept': 'application/vnd.github.v3+json'})
with open('data.json', 'w') as f:
    f.write(json.dumps(response.json(), indent=4))
print("AWX devel is {} commit(s) ahead of release {}".format(response.json()['total_commits'], awx_version))
print("https://github.com/ansible/awx/compare/{}...devel".format(awx_version))
for commit in response.json()['commits']:
    author = commit['commit']['author']['name']
    pretty_message = commit['commit']['message'].replace("\n\n+", "\n").replace("\n", "\n{}".format(" " * (len(author) + 3)))
    print("[{}] {}".format(author, pretty_message))

print("Select next AWX version [x,y or z]:")
