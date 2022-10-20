# Copyright (c) 2022 Ansible, Inc.
# All Rights Reserved.

#
# This file is intended to hold all manually executed SQL queries.
# The intent is to isolate all manual SQL into a single file to support multiple DBs
# Currently all functions return a string but its conciveable that a function may need to actually do
#  a serries of steps if one DB platform requires multiple executions to perform the function of
#  another provider.
# All functions should raise an error if the connection.vendor is not supported.
# This will help when adding a new backend database.
# Occasionally, in the code you may want to test the DB vendor in a function, use connection.vendor to do this.
#
# We are not adding SQL from the awx.main.db.profiled_* objects.

# Django
from django.db import connection

# Python
import inspect

__all__ = [
    'get_db_version_sql',
    'get_database_conections',
    'partition_table',
    'get_max_id',
    'get_number_of_relations_for_last_minute',
    'get_job_history',
    'find_partitions_to_drop',
    'delete_partition',
]


def get_db_version_sql():
    if connection.vendor == 'postgresql':
        return 'SELECT version()'
    elif connection.vendor == 'microsoft':
        return 'SELECT @@version'
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def get_database_conections():
    if connection.vendor == 'postgresql':
        return f"select count(*) from pg_stat_activity where datname='{connection.settings_dict['NAME']}'"
    elif connection.vendor == 'microsoft':
        return f"SELECT COUNT(dbid) as NumberOfConnections FROM sys.sysprocesses WHERE dbid = DB_ID('{connection.settings_dict['NAME']}');"
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def partition_table(table_name, partition_label, start_timestamp, end_timestamp):
    if connection.vendor == 'postgresql':
        return f'''
               CREATE TABLE IF NOT EXISTS {table_name}_{partition_label}
               PARTITION OF {table_name}
               FOR VALUES FROM (\'{start_timestamp}\') to (\'{end_timestamp}\');'
               '''
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def get_max_id(table_name):
    if connection.vendor in ['postgresql', 'microsoft']:
        return f"SELECT MAX(id) FROM {table_name};"
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def get_number_of_relations_for_last_minute(table_name, minimum_id):
    if connection.vendor == 'postgresql':
        return f"SELECT MAX(id) - MIN(id) FROM {table_name} WHERE id > {minimum_id} AND modified > now() - '1 minute'::interval;"
    elif connection.vendor == 'microsoft':
        return f"SELECT MAX(id) - MIN(id) FROM {table_name} WHERE id > {minimum_id} AND modified > now() - DATEADD(minute, -15, getutcdate())"
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def get_job_history(job_template_id, number_of_previous_jobs):
    if connection.vendor in ['postgresql', 'microsoft']:
        return f'''
                SELECT 
                    b.id, b.job_id, b.host_name, b.created - a.created delta,
                    b.task task,
                    b.event_data::json->'task_action' task_action,
                    b.event_data::json->'task_path' task_path
                FROM main_jobevent a JOIN main_jobevent b
                ON b.parent_uuid = a.parent_uuid  AND a.host_name = b.host_name
                WHERE
                    a.event = 'runner_on_start' AND
                    b.event != 'runner_on_start' AND
                    b.event != 'runner_on_skipped' AND
                    b.failed = false AND
                    a.job_id IN (
                        SELECT unifiedjob_ptr_id FROM main_job
                        WHERE job_template_id={job_template_id}
                        ORDER BY unifiedjob_ptr_id DESC
                        LIMIT {number_of_previous_jobs}
                    )
                ORDER BY delta DESC;
                '''
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def find_partitions_to_drop(table_name, cutoff):
    if connection.vendor == 'postgresql':
        return f'''
               SELECT inhrelid::regclass::text AS child FROM pg_catalog.pg_inherits
                WHERE inhparent = '{tbl_name}'::regclass
                  AND TO_TIMESTAMP(LTRIM(inhrelid::regclass::text, '{tbl_name}_'), 'YYYYMMDD_HH24') < '{self.cutoff}'
               ORDER BY inhrelid::regclass::text"
               '''
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def drop_table(table_name):
    if connection.vendor in ['postgresql', 'microsoft']:
        return f"DROP TABLE {table_name}"
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def delete_partition(table_name, relation_name, primary_keys):
    if connection.vendor == 'postgresql':
        return f"DELETE FROM _unpartitioned_{table_name} WHERE {relation_name} IN ({primary_keys})"
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def get_roles_from_parents(parent_table, ids_to_find):
    if connection.vendor in ['postgresql', 'microsoft']:
        return f'SELECT DISTINCT from_role_id FROM {parent_table} WHERE to_role_id IN ({ids_to_find})'
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def add_role_ancestors(ancestor_table, role_table, parent_table, ids):
    if connection.vendor in ['postgresql', 'microsoft']:
        return f'''
               INSERT INTO {ancestor_table} (descendent_id, ancestor_id, role_field, content_type_id, object_id)
               SELECT from_id, to_id, new_ancestry_list.role_field, new_ancestry_list.content_type_id, new_ancestry_list.object_id FROM  (
                     SELECT roles.id from_id,
                            ancestors.ancestor_id to_id,
                            roles.role_field,
                            COALESCE(roles.content_type_id, 0) content_type_id,
                            COALESCE(roles.object_id, 0) object_id
                       FROM {role_table} as roles
                            INNER JOIN {parent_table} as parents
                                    ON (parents.from_role_id = roles.id)
                            INNER JOIN {ancestor_table} as ancestors
                                    ON (parents.to_role_id = ancestors.descendent_id)
                      WHERE roles.id IN ({ids})

                      UNION

                     SELECT id from_id,
                            id to_id,
                            role_field,
                            COALESCE(content_type_id, 0) content_type_id,
                            COALESCE(object_id, 0) object_id
                      from {role_table} WHERE id IN ({ids})
                ) new_ancestry_list
                WHERE NOT EXISTS (
                   SELECT 1 FROM {ancestor_table}
                    WHERE {ancestor_table}.descendent_id = new_ancestry_list.from_id
                          AND {ancestor_table}.ancestor_id = new_ancestry_list.to_id
                )
           '''
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')


def delete_role_ancestors(ancestor_table, parent_table, ids):
    if connection.vendor in ['postgresql', 'microsoft']:
        return f'''
               DELETE FROM %(ancestors_table)s
               WHERE descendent_id IN (%(ids)s)
                     AND descendent_id != ancestor_id
                     AND NOT EXISTS (
                         SELECT 1
                           FROM %(parents_table)s as parents
                                INNER JOIN %(ancestors_table)s as inner_ancestors
                                        ON (parents.to_role_id = inner_ancestors.descendent_id)
                          WHERE parents.from_role_id = %(ancestors_table)s.descendent_id
                                AND %(ancestors_table)s.ancestor_id = inner_ancestors.ancestor_id
                     )
               '''
    raise Exception(f'db vendor {connection.vendor} not supported for sql query {inspect.stack()[0][0].f_code.co_name}')
