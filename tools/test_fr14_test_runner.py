"""Offline runner safety checks: mock drivers and Python fixture graphs, no database."""

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from io import StringIO
import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.db.backends.mysql.base import Database

from config.fr14_test_guard import (
    APPROVAL_ENV, APPROVAL_PHRASE, Guard, PRODUCTION_UUID, Target, offline_database,
)
from tools import fr14_tests as runner


TARGET = Target(3311, "test-host", "47c73b62-df2c-11f1-b343-df6f8d76a6e0",
                PRODUCTION_UUID, approved=True)


class OfflineCase(TestCase):
    def setUp(self):
        self.enterContext(runner.block_network())
        self.enterContext(redirect_stdout(StringIO()))
        for name in ("connect", "Connect", "Connection"):
            self.enterContext(patch.object(Database, name,
                side_effect=AssertionError("Real MySQL forbidden in offline runner tests.")))


class ChatOrderTests(OfflineCase):
    def test_reply_and_retry_children_are_deleted_before_all_parents(self):
        rows=[(10,None,None),(3,10,None),(2,10,3),(1,3,None)]
        self.assertEqual(runner.chat_message_delete_order(rows),[1,2,3,10])

    def test_shared_parent_edges_are_counted_once_and_order_is_deterministic(self):
        rows=[(1,None,None),(2,1,1),(3,None,None)]
        self.assertEqual(runner.chat_message_delete_order(rows),[2,1,3])
        self.assertEqual(runner.chat_message_delete_order(list(reversed(rows))),[2,1,3])

    def test_empty_graph(self):
        self.assertEqual(runner.chat_message_delete_order([]),[])

    def test_cycle_self_reference_or_missing_parent_stops(self):
        for rows in ([(1,1,None)],[(1,2,None),(2,None,1)],[(1,99,None)],
                     [(1,None,None),(2,None,99)],[(1,2,None),(2,1,None),(3,None,None)]):
            with self.subTest(rows=rows),self.assertRaises(runner.RunnerError):
                runner.chat_message_delete_order(rows)

    def test_invalid_duplicate_or_boolean_ids_stop(self):
        for rows in ([(1,None,None),(1,None,None)],[(True,None,None)],
                     [(0,None,None)],[(1,'2',None)],[(1,None,-1)]):
            with self.subTest(rows=rows),self.assertRaises(runner.RunnerError):
                runner.chat_message_delete_order(rows)


class FixtureCursor:
    """Strict SQL mock backed only by Python dictionaries; rejects wrong delete order."""
    def __init__(self, messages):
        self.messages={row[0]:tuple(row) for row in messages}
        self.other={'django_migrations':[1], 'appointments':[1], 'chat_sessions':[1], 'users':[1]}
        self.keys=[('chat_messages','reply_to_id','chat_messages','id'),
                   ('chat_messages','retry_of_id','chat_messages','id'),
                   ('chat_messages','session_id','chat_sessions','id'),
                   ('chat_sessions','user_id','users','id')]
        self.calls=[]
        self.result=[]
        self.rowcount=0
        self.bad_rowcount=False

    def __enter__(self):return self
    def __exit__(self,*args):return False
    def fetchall(self):return self.result
    def fetchone(self):return self.result[0] if self.result else None

    def execute(self, sql, params=None):
        self.calls.append((sql,params))
        if 'information_schema.KEY_COLUMN_USAGE' in sql:
            self.result=self.keys
        elif sql.startswith('SELECT id, reply_to_id, retry_of_id'):
            self.result=[self.messages[key] for key in sorted(self.messages)]
        elif sql.startswith('SELECT 1 FROM '):
            table=sql.split()[3].strip('`')
            self.result=[(1,)] if (self.messages if table=='chat_messages' else self.other[table]) else []
        elif sql=='DELETE FROM chat_messages WHERE id = %s':
            identifier=params[0]
            if any(identifier in (row[1],row[2]) for row in self.messages.values()):
                raise AssertionError('Parent deleted while a reply/retry child remains')
            del self.messages[identifier]
            self.rowcount=0 if self.bad_rowcount else 1
        elif sql.startswith('DELETE FROM '):
            table=sql.split()[2].strip('`')
            if table=='django_migrations':raise AssertionError('System table deletion forbidden')
            if table=='chat_sessions' and self.messages:raise AssertionError('Messages remain')
            if table=='users' and self.other['chat_sessions']:raise AssertionError('Sessions remain')
            self.other[table]=[]
        else:
            raise AssertionError('Unexpected SQL in offline mock: '+sql)


class CleanupTests(OfflineCase):
    def configure_cleanup(self, rows):
        cursor=FixtureCursor(rows)
        connection=MagicMock()
        connection.cursor.return_value=cursor
        connection.ops.quote_name.side_effect=lambda name:'`'+name+'`'
        tables=set(cursor.other)|{'chat_messages'}
        guard=MagicMock()
        self.enterContext(patch.object(runner,'preflight',return_value=tables))
        @contextmanager
        def atomic(**kwargs):
            self.assertEqual(kwargs,{'using':'default'})
            before=deepcopy((cursor.messages,cursor.other))
            try:yield
            except BaseException:
                cursor.messages,cursor.other=before
                raise
        self.enterContext(patch('django.db.transaction.atomic',side_effect=atomic))
        return connection,guard,cursor,tables

    def test_cleanup_checks_guard_preserves_system_rows_and_deletes_children_first(self):
        connection,guard,cursor,_=self.configure_cleanup([(10,None,None),(3,10,None),(2,10,3),(1,3,None)])
        runner.remove_fixture_rows(connection,guard)
        guard.recheck.assert_called_once_with(connection)
        self.assertFalse(cursor.messages)
        self.assertEqual(cursor.other,{'django_migrations':[1],'appointments':[],'chat_sessions':[],'users':[]})
        deletes=[params for sql,params in cursor.calls if sql=='DELETE FROM chat_messages WHERE id = %s']
        self.assertEqual(deletes,[[1],[2],[3],[10]])
        self.assertTrue(any(sql.endswith('FOR UPDATE') for sql,_ in cursor.calls))

    def test_cycle_is_rejected_before_deleting_any_table_including_independent_rows(self):
        connection,guard,cursor,_=self.configure_cleanup([(1,2,None),(2,1,None),(3,None,None)])
        with self.assertRaises(runner.RunnerError):runner.remove_fixture_rows(connection,guard)
        self.assertFalse(any(sql.startswith('DELETE') for sql,_ in cursor.calls))
        self.assertEqual(cursor.other['appointments'],[1])

    def test_missing_parent_is_rejected_without_any_delete(self):
        connection,guard,cursor,_=self.configure_cleanup([(1,None,None),(2,1,99)])
        with self.assertRaises(runner.RunnerError):runner.remove_fixture_rows(connection,guard)
        self.assertFalse(any(sql.startswith('DELETE') for sql,_ in cursor.calls))

    def test_unknown_or_missing_self_foreign_keys_stop_without_any_delete(self):
        for change in ('unknown','missing'):
            with self.subTest(change=change):
                connection,guard,cursor,_=self.configure_cleanup([(1,None,None)])
                if change=='unknown':cursor.keys.append(('users','manager_id','users','id'))
                else:cursor.keys.pop(0)
                with self.assertRaises(runner.RunnerError):runner.remove_fixture_rows(connection,guard)
                self.assertFalse(any(sql.startswith('DELETE') for sql,_ in cursor.calls))

    def test_table_cycle_or_preserved_parent_reference_stops(self):
        for keys in ([('users','x','appointments','id'),('appointments','y','users','id')],
                     [('django_migrations','x','users','id')]):
            with self.subTest(keys=keys):
                cursor=MagicMock();cursor.fetchall.return_value=keys
                connection=MagicMock();connection.cursor.return_value.__enter__.return_value=cursor
                with self.assertRaises(runner.RunnerError):
                    runner.fixture_delete_order(connection,{'users','appointments','django_migrations'})

    def test_changed_dependencies_stop_before_deleting_rows(self):
        connection,guard,cursor,_=self.configure_cleanup([(1,None,None)])
        with self.assertRaises(runner.RunnerError):
            runner.remove_fixture_rows(connection,guard,expected_order=['wrong'])
        self.assertFalse(any(sql.startswith('DELETE') for sql,_ in cursor.calls))

    def test_delete_rowcount_failure_rolls_back_the_python_fixture_transaction(self):
        connection,guard,cursor,_=self.configure_cleanup([(1,None,None),(2,1,None)])
        cursor.bad_rowcount=True
        before=deepcopy((cursor.messages,cursor.other))
        with self.assertRaises(runner.RunnerError):runner.remove_fixture_rows(connection,guard)
        self.assertEqual((cursor.messages,cursor.other),before)


class PreparationTests(OfflineCase):
    def preparation_mocks(self, plans):
        connection,guard=MagicMock(),MagicMock()
        guard.target=TARGET
        self.enterContext(patch.object(runner,'preflight',return_value={'django_migrations'}))
        empty=self.enterContext(patch.object(runner,'require_empty_fixture_tables'))
        self.enterContext(patch.object(runner,'migration_plan',side_effect=plans))
        confirm=self.enterContext(patch.object(runner,'confirm'))
        command=self.enterContext(patch('django.core.management.call_command'))
        self.enterContext(patch('django.apps.apps.get_models',return_value=[]))
        return connection,guard,empty,confirm,command

    def test_schema_preparation_calls_only_mocked_migrate_and_not_tests_or_cleanup(self):
        plan=[('example','0001')]
        connection,guard,_,confirm,command=self.preparation_mocks([plan,plan,[]])
        with patch.object(runner,'run_tests') as tests,patch.object(runner,'remove_fixture_rows') as cleanup:
            runner.prepare_schema(connection,guard)
        command.assert_called_once_with('migrate',database='default',interactive=False,verbosity=1)
        confirm.assert_called_once_with('PREPARE','Apply 1 migrations only; no regression or cleanup',TARGET)
        guard.recheck.assert_called_once_with(connection)
        tests.assert_not_called();cleanup.assert_not_called()

    def test_prepared_schema_is_read_only_and_needs_no_mutation_confirmation(self):
        connection,guard,_,confirm,command=self.preparation_mocks([[],[]])
        runner.prepare_schema(connection,guard)
        confirm.assert_not_called();command.assert_not_called()

    def test_nonempty_schema_stops_before_confirmation_or_migrate(self):
        connection,guard,empty,confirm,command=self.preparation_mocks([])
        empty.side_effect=runner.RunnerError('Existing data')
        with self.assertRaises(runner.RunnerError):runner.prepare_schema(connection,guard)
        confirm.assert_not_called();command.assert_not_called()

    def test_declined_confirmation_or_changed_plan_stops_before_migrate(self):
        plan=[('example','0001')]
        for reason in ('declined','changed'):
            with self.subTest(reason=reason):
                connection,guard,_,confirm,command=self.preparation_mocks([plan,[]])
                if reason=='declined':confirm.side_effect=runner.RunnerError('Declined')
                with self.assertRaises(runner.RunnerError):runner.prepare_schema(connection,guard)
                command.assert_not_called()

    def test_failed_migration_does_not_retry_run_tests_or_cleanup(self):
        plan=[('example','0001')]
        connection,guard,_,_,command=self.preparation_mocks([plan,plan])
        command.side_effect=RuntimeError('Migration failed')
        with patch.object(runner,'run_tests') as tests,patch.object(runner,'remove_fixture_rows') as cleanup:
            with self.assertRaises(RuntimeError):runner.prepare_schema(connection,guard)
        self.assertEqual(command.call_count,1)
        tests.assert_not_called();cleanup.assert_not_called()

    def test_remaining_plan_or_incomplete_schema_stops_after_mocked_migrate(self):
        plan=[('example','0001')]
        for problem in ('pending','missing-table'):
            with self.subTest(problem=problem):
                plans=[plan,plan,plan if problem=='pending' else []]
                connection,guard,_,_,command=self.preparation_mocks(plans)
                if problem=='missing-table':
                    model=SimpleNamespace(_meta=SimpleNamespace(db_table='expected_missing_table'))
                    self.enterContext(patch('django.apps.apps.get_models',return_value=[model]))
                with self.assertRaises(runner.RunnerError):runner.prepare_schema(connection,guard)
                self.assertEqual(command.call_count,1)

    def test_conflicting_or_backwards_migrations_stop_without_execution(self):
        for conflict in (True,False):
            with self.subTest(conflict=conflict),patch('django.db.migrations.executor.MigrationExecutor') as factory:
                executor=factory.return_value
                executor.loader.detect_conflicts.return_value={'example':['a','b']} if conflict else {}
                executor.migration_plan.return_value=[(SimpleNamespace(app_label='example',name='0001'),True)]
                with self.assertRaises(runner.RunnerError):runner.migration_plan(MagicMock())
                executor.migrate.assert_not_called()

    def test_prepare_cli_does_not_discover_or_run_the_regression_suite(self):
        @contextmanager
        def context(guard):yield {'default':MagicMock()}
        with patch('sys.argv',['fr14_tests.py','prepare']),patch.object(Target,'from_environment',return_value=TARGET), \
                patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',return_value='fake-password'), \
                patch.object(runner,'django_context',side_effect=context),patch.object(runner,'prepare_schema') as prepare, \
                patch.object(runner,'discover') as discover,patch.object(runner,'run_tests') as tests:
            self.assertEqual(runner.main(),0)
        prepare.assert_called_once();discover.assert_not_called();tests.assert_not_called()

    def test_cli_without_approval_or_with_forbidden_port_stops_before_password_and_database(self):
        for port in ('3306','3310','3307','3311'):
            environment={'ANNHIEN_FR14_TEST_PORT':port,'ANNHIEN_FR14_TEST_HOSTNAME':TARGET.hostname,
                'ANNHIEN_FR14_TEST_SERVER_UUID':TARGET.server_uuid,'ANNHIEN_FR14_MAIN_SERVER_UUID':TARGET.main_uuid}
            if port!='3311':environment[APPROVAL_ENV]=APPROVAL_PHRASE
            with self.subTest(port=port),patch.dict(os.environ,environment,clear=True), \
                    patch('sys.argv',['fr14_tests.py','prepare']),patch('getpass.getpass') as password, \
                    patch.object(runner,'django_context') as context:
                self.assertEqual(runner.main(),1)
                password.assert_not_called();context.assert_not_called()

    def test_schema_prepare_rejects_test_labels(self):
        with patch('sys.argv',['fr14_tests.py','prepare','core']), \
                patch('sys.stderr',StringIO()),self.assertRaises(SystemExit) as error:
            runner.main()
        self.assertEqual(error.exception.code,2)

    def test_chat_concurrency_is_discoverable_with_no_database_access(self):
        from django.test.runner import DiscoverRunner
        with runner.django_context(Guard(None)),offline_database():
            discovery=DiscoverRunner(verbosity=0,interactive=False)
            expected=runner.suite_ids(discovery.build_suite(runner.REGRESSION))
            chat=runner.suite_ids(discovery.build_suite(['ai_features.tests.ConcurrentChatTests']))
            ordinary=runner.suite_ids(discovery.build_suite(['ai_features.tests.ChatTests']))
            self.assertEqual(chat.total(),1)
            self.assertFalse(chat-expected)
            self.assertFalse(set(ordinary)&set(expected))
