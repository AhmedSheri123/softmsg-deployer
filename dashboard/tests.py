from django.test import TestCase

# Create your tests here.
from django.db.migrations.executor import MigrationExecutor
from django.db import connection

def are_migrations_done():
    executor = MigrationExecutor(connection)
    unapplied_migrations = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return not unapplied_migrations  # إذا كانت القائمة فارغة، فكل الهجرات مطبقة

are_migrations_done()