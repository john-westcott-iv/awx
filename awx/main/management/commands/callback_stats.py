import time
import sys

from django.db import connection
from django.core.management.base import BaseCommand

from awx.main.db.sql_queries import get_max_id, get_number_of_relations_for_last_minute


class Command(BaseCommand):
    def handle(self, *args, **options):

        with connection.cursor() as cursor:
            start = {}
            for relation in ('main_jobevent', 'main_inventoryupdateevent', 'main_projectupdateevent', 'main_adhoccommandevent'):
                cursor.execute(get_max_id(relation))
                start[relation] = cursor.fetchone()[0] or 0
            clear = False
            while True:
                lines = []
                for relation in ('main_jobevent', 'main_inventoryupdateevent', 'main_projectupdateevent', 'main_adhoccommandevent'):
                    lines.append(relation)
                    minimum = start[relation]
                    cursor.execute(get_number_of_relations_for_last_minute(relation, minimum_id))
                    events = cursor.fetchone()[0] or 0
                    lines.append(f'↳  last minute {events}')
                    lines.append('')
                if clear:
                    for i in range(12):
                        sys.stdout.write('\x1b[1A\x1b[2K')
                for line in lines:
                    print(line)
                clear = True
                time.sleep(0.25)
