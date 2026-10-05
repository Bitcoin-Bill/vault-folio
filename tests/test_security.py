"""Security boundaries: OR unlock, authenticated metadata, schema and atomic saves."""
import copy
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import folio_security as crypto
import folio_storage as storage
from folio_document import prepare_plan
from folio_catalog import ensure_sections, extra_risks
spec = importlib.util.spec_from_file_location('folio', Path(__file__).resolve().parents[1] / 'vault-folio.py')
folio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(folio)


def device(secret):
    return lambda challenge, slot: hmac.new(secret, challenge, hashlib.sha1).digest()


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = ensure_sections(folio.blank_plan())
        cls.plan['lawyers'] = [{'name': 'Example counsel', 'access': 'Location hints only'}]
        cls.plan['backupRecords'] = [{'label': 'Backup A', 'hint': 'Ask the family trustee', 'scheme': 'SLIP39 threshold shares (one signing key)', 'threshold': '2 of 3'}]
        cls.password = 'a long independently held passphrase'
        cls.answers = ['A private invented answer', 'Another private answer', 'Third unrelated answer']
        cls.methods = [
            {'kind': 'passphrase', 'label': 'Trustee', 'passphrase': cls.password},
            {'kind': 'yubikey', 'label': 'Owner key', 'slot': 2},
            {'kind': 'yubikey', 'label': 'Lawyer key', 'slot': 2},
            {'kind': 'questions', 'label': 'Family', 'questions': ['First clue?', 'Second clue?', 'Third clue?'], 'answers': cls.answers},
        ]
        providers = iter([device(b'owner'), device(b'lawyer')])
        cls.env = crypto.seal(cls.plan, cls.methods, response_provider=lambda c, s: next(providers)(c, s))

    def no_hardware(self, *_):
        self.fail('Hardware must not be accessed')

    def test_each_method_unlocks_independently(self):
        self.assertEqual(crypto.open_package(self.env, credential=self.password, response_provider=self.no_hardware), self.plan)
        for index, secret in [(1, b'owner'), (2, b'lawyer')]:
            self.assertEqual(crypto.open_package(self.env, method_index=index, response_provider=device(secret)), self.plan)
        self.assertEqual(crypto.open_package(self.env, method_index=3, credential=self.answers, response_provider=self.no_hardware), self.plan)
        encoded = json.dumps(self.env)
        for secret in [self.password, *self.answers, 'Example counsel', 'Ask the family trustee']:
            self.assertNotIn(secret, encoded)
        self.assertIn('First clue?', encoded)

    def test_wrong_credentials_do_not_fall_back(self):
        cases = [(0, 'wrong password', device(b'owner')), (1, None, device(b'lawyer')),
                 (2, None, device(b'owner')), (3, self.answers[:2] + ['wrong'], self.no_hardware)]
        for index, credential, provider in cases:
            with self.subTest(index=index), self.assertRaises(ValueError):
                crypto.open_package(self.env, method_index=index, credential=credential, response_provider=provider)

    def test_questions_require_all_answers_and_normalize(self):
        normalized = ['  A PRIVATE   INVENTED ANSWER ', 'another private answer', 'third unrelated answer']
        self.assertEqual(crypto.open_package(self.env, method_index=3, credential=normalized), self.plan)
        for answers in [self.answers[:2], self.answers + ['extra'], ['', *self.answers[1:]], None]:
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                crypto.open_package(self.env, method_index=3, credential=answers)
        self.assertEqual(crypto.question_material(['Ａ', ' B ', 'c']), crypto.question_material(['a', 'b', 'C']))
        self.assertNotEqual(crypto.question_material(['a!', 'b', 'c']), crypto.question_material(['a', 'b', 'c']))

    def test_single_method_packages(self):
        for method, credential in [(self.methods[0], self.password), (self.methods[1], None), (self.methods[3], self.answers)]:
            env = crypto.seal(self.plan, [method], response_provider=device(b'owner'))
            self.assertEqual(crypto.open_package(env, credential=credential, response_provider=device(b'owner')), self.plan)

    def test_duplicate_key_configuration_rejected(self):
        with self.assertRaisesRegex(ValueError, 'already enrolled'):
            crypto.seal(self.plan, self.methods[1:3], response_provider=device(b'same configuration'))

    def test_tampering_including_unselected_method(self):
        cases = []
        for field in ['iv', 'data']:
            env = copy.deepcopy(self.env)
            raw = bytearray(crypto.unb64(env[field])); raw[0] ^= 1
            env[field] = crypto.b64(raw); cases.append(env)
        for index in range(len(self.env['methods'])):
            env = copy.deepcopy(self.env)
            raw = bytearray(crypto.unb64(env['methods'][index]['wrapped'])); raw[0] ^= 1
            env['methods'][index]['wrapped'] = crypto.b64(raw); cases.append(env)
        for index, field, value in [(1, 'slot', 1), (2, 'label', 'Changed holder'), (3, 'questions', ['Changed?', 'Second clue?', 'Third clue?'])]:
            env = copy.deepcopy(self.env); env['methods'][index]['meta'][field] = value; cases.append(env)
        env = copy.deepcopy(self.env); env['methods'].pop(); cases.append(env)
        env = copy.deepcopy(self.env); env['methods'][1:3] = reversed(env['methods'][1:3]); cases.append(env)
        for index, env in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                crypto.open_package(env, credential=self.password, response_provider=self.no_hardware)

    def test_malformed_rejected_before_hardware(self):
        cases = [None, [], {}, {'magic': crypto.MAGIC}]
        for field, value in [('iterations', 10**30), ('slot', True), ('challenge', 'bad'), ('kind', 'unknown')]:
            env = copy.deepcopy(self.env); env['methods'][1]['meta'][field] = value; cases.append(env)
        env = copy.deepcopy(self.env); env['methods'] *= 4; cases.append(env)
        env = copy.deepcopy(self.env); env['methods'][0] = {'meta': [], 'wrapped': ''}; cases.append(env)
        env = copy.deepcopy(self.env); env['methods'][3]['meta']['questions'] = ['Same?']*3; cases.append(env)
        for env in cases:
            with self.assertRaises(ValueError):
                crypto.open_package(env, method_index=1, response_provider=self.no_hardware)
        for index in [-1, True, '1', 4]:
            with self.assertRaises(ValueError):
                crypto.open_package(self.env, method_index=index, response_provider=self.no_hardware)

    def test_all_setup_metadata_validated_before_hardware(self):
        for invalid in [dict(self.methods[0], passphrase='short'), dict(self.methods[1], slot=True),
                        dict(self.methods[3], questions=['Repeated?']*3)]:
            with self.assertRaises(ValueError):
                crypto.seal(self.plan, [self.methods[1], invalid], response_provider=self.no_hardware)

    def test_legacy_read_and_extended_runbook(self):
        env = folio.encrypt_plan(self.plan, self.password)
        self.assertEqual(folio.decrypt_plan(env, self.password), self.plan)
        with self.assertRaises(ValueError):
            folio.decrypt_plan(env, 'wrong password')
        runbook = folio.build_runbook_text(self.plan)
        for expected in ['Example counsel', 'Ask the family trustee', '2 of 3']:
            self.assertIn(expected, runbook)
        self.assertTrue(extra_risks(self.plan))

    def test_adapter_never_provisions_and_hides_diagnostics(self):
        with patch('folio_security.shutil.which', return_value='/trusted/ykman'), patch('folio_security.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout='ab'*20+'\n', stderr='')
            self.assertEqual(len(crypto.yubikey_response(b'x'*32, 2)), 20)
            args, kw = run.call_args
            self.assertEqual(args[0], ['/trusted/ykman', 'otp', 'calculate', '2', (b'x'*32).hex()])
            self.assertNotIn('shell', kw)
            run.return_value = subprocess.CompletedProcess([], 1, stdout='SECRET', stderr='SECRET')
            with self.assertRaises(ValueError) as err:
                crypto.yubikey_response(b'x'*32, 2)
            self.assertNotIn('SECRET', str(err.exception))

    def test_fresh_randomness(self):
        other = crypto.seal(self.plan, [self.methods[1]], response_provider=device(b'owner'))
        self.assertNotEqual(other['iv'], self.env['iv'])
        self.assertNotEqual(other['methods'][0]['meta']['challenge'], self.env['methods'][1]['meta']['challenge'])
        self.assertNotEqual(other['data'], self.env['data'])


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = crypto.seal({"example": "private plan"}, [{"kind": "yubikey", "slot": 2}], response_provider=device(b"storage test"))

    def test_atomic_success_is_reloadable_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.csp.json'
            path.write_bytes(b'previous encrypted backup')
            storage.save_encrypted(path, self.env)
            self.assertEqual(json.loads(path.read_text()), self.env)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_failure_preserves_previous_backup(self):
        for failing_call in ['os.fsync', 'os.replace']:
            with self.subTest(call=failing_call), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'guide.csp.json'
                path.write_bytes(b'previous encrypted backup')
                with patch('folio_storage.' + failing_call, side_effect=OSError('simulated full disk')):
                    with self.assertRaises(OSError):
                        storage.save_encrypted(path, self.env)
                self.assertEqual(path.read_bytes(), b'previous encrypted backup')
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_oversize_rejected_before_touching_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.csp.json'; path.write_bytes(b'old')
            with self.assertRaises(ValueError):
                storage.save_encrypted(path, self.env, max_bytes=1)
            self.assertEqual(path.read_bytes(), b'old')


class DocumentTests(unittest.TestCase):
    def test_defaults_and_unknown_fields_preserved_without_mutation(self):
        original = {'meta': {'planName': 'Old guide'}, 'futureField': {'untouched': True}}
        before = copy.deepcopy(original)
        result = prepare_plan(original, folio.blank_plan())
        self.assertEqual(original, before)
        self.assertEqual(result['meta']['created'], '')
        self.assertEqual(result['meta']['planName'], 'Old guide')
        self.assertEqual(result['futureField'], {'untouched': True})
        self.assertEqual(result['lawyers'], [])

    def test_malformed_sections_rejected(self):
        cases = [None, [], {'meta': []}, {'meta': {'owner': []}}, {'people': {'heirs': ['bad']}},
                 {'vaults': [{'m': True}]}, {'vaults': [{'m': 0}]}, {'vaults': [{'keys': [None]}]},
                 {'vaults': [{'timelock': {'enabled': 'yes'}}]}, {'lawyers': [{'name': []}]},
                 {'accessRecords': [{}]*501}, {'signing': {'verifyRitual': 'not a checklist'}},
                 {'backups': {'descriptorLocations': [1]}}]
        for document in cases:
            with self.subTest(document=document), self.assertRaises(ValueError):
                prepare_plan(document, folio.blank_plan())


if __name__ == '__main__':
    unittest.main()
