"""Offline guard checks. Run with python -B -m unittest tools.test_fr14_test_guard."""

from contextlib import contextmanager
from dataclasses import replace
import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.db.backends.mysql.base import CLIENT, Database, DatabaseWrapper, django_conversions
from django.db.utils import ConnectionHandler
from django.test import override_settings

from config.fr14_test_guard import (
    ACCOUNT, APPROVAL_ENV, APPROVAL_PHRASE, DATABASE, OPTIONS, PRIVILEGES,
    PRODUCTION_UUID, RESTORE_UUID, USER, Guard, GuardError, Target,
    check_grants, install_guard, require_isolated_database,
)
from tools.fr14_tests import block_network, django_context


TARGET = Target(3311, "test-host", "47c73b62-df2c-11f1-b343-df6f8d76a6e0",
                PRODUCTION_UUID, approved=True)
GUARD = Guard(TARGET, "fake-password")


@contextmanager
def fake_connection():
    raw = MagicMock()
    cursor = raw.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (
        DATABASE, ACCOUNT, TARGET.hostname, TARGET.port, TARGET.server_uuid, "8.4.11",
        "MySQL Community Server", "InnoDB", "NONE", "", 1,
    )
    cursor.fetchall.return_value = [
        (f"GRANT USAGE ON *.* TO `{USER}`@`127.0.0.1`",),
        (f"GRANT {', '.join(sorted(PRIVILEGES))} ON `{DATABASE}`.* TO `{USER}`@`127.0.0.1`",),
    ]
    with (patch.object(Database, "connect", return_value=raw) as driver,
          patch.object(DatabaseWrapper, "init_connection_state")):
        yield driver, raw, cursor


class GuardTests(TestCase):
    def setUp(self):
        self.enterContext(block_network())
        # Even a broken guard cannot reach the real C driver in these tests.
        for name in ("connect", "Connect", "Connection"):
            self.enterContext(patch.object(Database, name, side_effect=AssertionError("Real MySQL forbidden offline.")))

    def test_media_override_preserves_live_verification(self):
        from django.conf import settings

        with fake_connection() as (driver, raw, cursor), django_context(GUARD) as connections:
            with override_settings(MEDIA_ROOT="test-media"):
                self.assertIsNone(settings.SETTINGS_MODULE)
                require_isolated_database()
                self.assertIs(connections["default"].connection, raw)
                self.assertEqual(driver.call_args.kwargs["port"], 3311)
                self.assertEqual(cursor.execute.call_args_list.count((("SHOW GRANTS",), {})), 2)

    def test_override_of_schema_host_port_or_user_stops_before_connect(self):
        cases = ({"NAME": "annhien_spa"}, {"NAME": "annhien_spa_restore"},
                 {"PORT": "3306"}, {"PORT": "3310"}, {"PORT": "3307"},
                 {"HOST": "localhost"}, {"HOST": "192.0.2.1"}, {"USER": "root"})
        with fake_connection() as (driver, _, _), django_context(GUARD):
            for values in cases:
                with self.subTest(values=values), override_settings(
                    DATABASES={"default": GUARD.database_settings() | values}
                ), self.assertRaises(GuardError):
                    require_isolated_database()
            driver.assert_not_called()

    def test_invalid_driver_parameters_are_rejected_before_opening_socket(self):
        params = dict(host="127.0.0.1", port=3311, database=DATABASE, user=USER,
                      password=GUARD.password, client_flag=CLIENT.FOUND_ROWS,
                      conv=django_conversions, **OPTIONS)
        with fake_connection() as (driver, _, _), install_guard(GUARD):
            wrapper = ConnectionHandler({"default": GUARD.database_settings()})["default"]
            for changes in ({'port':3306},{'port':3310},{'port':3307},{'host':'localhost'},
                            {'database':'annhien_spa_restore'},{'user':'root'},
                            {'unix_socket':'unexpected'},{'read_default_file':'unexpected'},
                            {'password':'incorrect'},{'conv':{}},{'port':'3311'}):
                with self.subTest(changes=tuple(changes)):
                    with self.assertRaises(GuardError):
                        wrapper.get_new_connection(params | changes)
            for name in ('connect','Connect','Connection'):
                with self.subTest(entrypoint=name), self.assertRaises(GuardError):
                    getattr(Database,name)(**params)
            driver.assert_not_called()

    def test_target_rejects_every_other_port_without_a_driver_call(self):
        with fake_connection() as (driver, _, _):
            for port in (3306,3310,3307,0,65536,True,'3311'):
                with self.subTest(port=port), self.assertRaises(GuardError):
                    replace(TARGET,port=port)
            driver.assert_not_called()

    def test_approval_is_required_and_never_inferred_from_port(self):
        for approved in (False,None,1,'true'):
            with self.subTest(approved=approved), self.assertRaises(GuardError):
                replace(TARGET,approved=approved)
        environment = {
            'ANNHIEN_FR14_TEST_PORT':'3311', 'ANNHIEN_FR14_TEST_HOSTNAME':TARGET.hostname,
            'ANNHIEN_FR14_TEST_SERVER_UUID':TARGET.server_uuid,
            'ANNHIEN_FR14_MAIN_SERVER_UUID':TARGET.main_uuid,
        }
        with patch.dict(os.environ,environment,clear=True):
            with self.assertRaises(GuardError):Target.from_environment()
            os.environ[APPROVAL_ENV]=APPROVAL_PHRASE
            self.assertEqual(Target.from_environment(),TARGET)
            os.environ['ANNHIEN_FR14_TEST_PORT']='3310'
            with self.assertRaises(GuardError):Target.from_environment()

    def test_known_production_and_restore_uuids_cannot_be_approved(self):
        for identifier in (PRODUCTION_UUID,RESTORE_UUID,TARGET.main_uuid):
            with self.subTest(identifier=identifier), self.assertRaises(GuardError):
                replace(TARGET,server_uuid=identifier)
        # Changing the configured main UUID must not remove the known denylist.
        with self.assertRaises(GuardError):
            replace(TARGET,server_uuid=RESTORE_UUID,main_uuid=TARGET.server_uuid)

    def test_mutated_target_is_revalidated_at_connection_boundary(self):
        target=replace(TARGET)
        guard=Guard(target,'fake-password')
        object.__setattr__(target,'port',3310)
        with fake_connection() as (driver, _, _), install_guard(guard):
            with self.assertRaises(GuardError):guard.database_settings()
            driver.assert_not_called()

    def test_live_identity_and_roles_are_verified_before_session_initialization(self):
        cases={0:'annhien_spa_restore',1:'root@localhost',2:'wrong-host',3:3310,
               4:RESTORE_UUID,7:'MyISAM',8:'unexpected-role',9:'mandatory-role'}
        for field,value in cases.items():
            with self.subTest(field=field), fake_connection() as (_,raw,cursor), install_guard(GUARD):
                row=list(cursor.fetchone.return_value);row[field]=value;cursor.fetchone.return_value=tuple(row)
                wrapper=ConnectionHandler({'default':GUARD.database_settings()})['default']
                with self.assertRaises(GuardError):wrapper.ensure_connection()
                raw.close.assert_called_once()
                self.assertIsNone(wrapper.connection)
                DatabaseWrapper.init_connection_state.assert_not_called()

    def test_each_new_connection_is_verified(self):
        with fake_connection() as (driver, _, cursor), install_guard(GUARD):
            for _ in range(2):
                wrapper=ConnectionHandler({'default':GUARD.database_settings()})['default']
                wrapper.ensure_connection();wrapper.close()
            self.assertEqual(driver.call_count,2)
            self.assertEqual(cursor.execute.call_args_list.count((("SHOW GRANTS",), {})),2)

    def test_account_host_must_match_the_provisioned_tcp_account_exactly(self):
        for account in (f'{USER}@localhost',f'{USER}@%',f'{USER}@192.0.2.1'):
            with self.subTest(account=account),fake_connection() as (_,raw,cursor),install_guard(GUARD):
                row=list(cursor.fetchone.return_value);row[1]=account;cursor.fetchone.return_value=tuple(row)
                wrapper=ConnectionHandler({'default':GUARD.database_settings()})['default']
                with self.assertRaises(GuardError):wrapper.ensure_connection()
                raw.close.assert_called_once()

    def test_unescaped_schema_wildcards_and_broad_grants_are_rejected(self):
        grants=[(f'GRANT USAGE ON *.* TO `{USER}`@`127.0.0.1`',),
                (f"GRANT {', '.join(sorted(PRIVILEGES))} ON `{DATABASE}`.* TO `{USER}`@`127.0.0.1`",)]
        with self.assertRaises(GuardError):check_grants(grants,0)
        escaped=DATABASE.replace('_',r'\_')
        grants[1]=(f"GRANT {', '.join(sorted(PRIVILEGES))} ON `{escaped}`.* TO `{USER}`@`127.0.0.1`",)
        check_grants(grants,0)
        with self.assertRaises(GuardError):check_grants(grants+[(f'GRANT SELECT ON *.* TO `{USER}`@`127.0.0.1`',)],0)

    def test_wrong_server_uuid_or_grants_closes_connection_before_django_uses_it(self):
        for field in ("uuid", "grants"):
            with self.subTest(field=field), fake_connection() as (_, raw, cursor), install_guard(GUARD):
                if field == "uuid":
                    row = list(cursor.fetchone.return_value)
                    row[4] = TARGET.main_uuid
                    cursor.fetchone.return_value = tuple(row)
                else:
                    cursor.fetchall.return_value.append((f"GRANT SELECT ON *.* TO `{USER}`@`127.0.0.1`",))
                wrapper = ConnectionHandler({"default": GUARD.database_settings()})["default"]
                with self.assertRaises(GuardError):
                    wrapper.ensure_connection()
                raw.close.assert_called_once()
                self.assertIsNone(wrapper.connection)

    def test_fixture_guard_requires_an_active_guard(self):
        with self.assertRaises(GuardError):
            require_isolated_database()
