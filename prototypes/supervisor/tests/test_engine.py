"""Disposable local HTTP contracts; run: python3 -m unittest discover -s tests -v.

No production endpoints, chat, provider, Docker, or external dependencies.
"""
import copy
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import Supervisor


class TargetHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        state = self.server.state
        if state['probe_mode'] == 'redirect':
            self.send_response(302)
            self.send_header('Location', self.server.url + '/redirected')
            self.end_headers()
            state['redirect_gets'] += self.path == '/redirected'
            return
        if state['probe_mode'] == 'error':
            self.send_error(503)
            return
        body = (b'not json' if state['probe_mode'] == 'invalid' else
                json.dumps({'ok': state['ok'], 'private': 'not retained', 'work': {'done': state['ok']}}).encode())
        self.send_response(503 if state['probe_mode'] == 'json_error' else 200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        state = self.server.state
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with state['lock']:
            state['requests'].append({'body': body, 'authorization': self.headers.get('Authorization'),
                                      'idempotency': self.headers.get('Idempotency-Key'), 'path': self.path})
        if state['post_mode'] == 'redirect':
            self.send_response(307)
            self.send_header('Location', self.server.url + '/other-action')
            self.end_headers()
            return
        if state['repairs']:
            state['ok'] = True
        if state['post_mode'] == 'disconnect':
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'{}')


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.temp.name, 'ledger.sqlite')
        self.state = {'ok': False, 'repairs': True, 'probe_mode': 'normal', 'post_mode': 'normal',
                      'requests': [], 'redirect_gets': 0, 'lock': threading.Lock()}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), TargetHandler)
        self.server.daemon_threads = True
        self.server.state = self.state
        self.server.url = 'http://127.0.0.1:%s' % self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()
        self.config = {'targets': {'demo': {'name': 'Disposable service', 'kind': 'service',
            'probe_url': self.server.url + '/probe?secret=probe-secret',
            'action_url': self.server.url + '/action?secret=action-secret',
            'action_token': 'sensitive-test-token', 'expected': {'ok': True},
            'grant': True, 'action': 'repair', 'description': 'Only the disposable target'}}, 'max_attempts': 2}
        self.now = 1000.0
        self.engine = Supervisor(self.db, self.config, clock=lambda: self.now)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
        self.temp.cleanup()

    def restart(self):
        self.engine = Supervisor(self.db, self.config, clock=lambda: self.now)
        return self.engine

    def incident(self):
        return self.engine.observe('demo')

    def gate(self):
        self.config['targets']['demo']['grant'] = False
        self.restart()
        inc = self.incident()
        decision = self.engine.decide(inc['id'], {})
        self.assertEqual(decision['state'], 'awaiting_approval')
        return inc, decision

    def test_json_http_error_establishes_failure_but_cannot_prove_health(self):
        self.state['probe_mode'] = 'json_error'
        engine = Supervisor(self.db, self.config)
        inc = engine.observe('demo')
        self.assertEqual(inc['verification']['status'], 'failed')
        self.state['ok'] = True
        self.assertEqual(engine.observe('demo')['verification']['status'], 'failed')

    def test_explicit_owner_preference_retires_worker_wait(self):
        inc = self.incident()
        before = self.engine.snapshot()['targets'][0]['policy_digest']
        self.engine.decide(inc['id'], {'action': 'wait', 'why': 'Awaiting more context'})
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'deferred')
        self.engine.feedback(inc['id'], 'handle authorized repairs', mode='owner')
        self.assertNotEqual(before, self.engine.snapshot()['targets'][0]['policy_digest'])
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'resolved')

    def test_real_repair_and_verified_resolution(self):
        result = self.engine.tick()[0]
        self.assertEqual(result['status'], 'resolved')
        self.assertEqual(result['verification']['status'], 'healthy')
        self.assertTrue(result['action_sent'])
        request = self.state['requests'][0]
        self.assertEqual(request['body']['action'], 'repair')
        self.assertEqual(request['body']['incident'], result['incident']['id'])
        self.assertEqual(request['body']['generation'], 1)
        self.assertEqual(request['body']['idempotency_key'], request['idempotency'])
        self.assertEqual(request['authorization'], 'Bearer sensitive-test-token')
        self.assertEqual(request['path'], '/action?secret=action-secret')
        self.assertEqual(self.restart().tick(), [])
        self.assertEqual(len(self.state['requests']), 1)

    def test_worker_approval_request_does_not_make_owner_gate(self):
        inc = self.incident()
        for action in ('repair', 'needs approval', 'needs_approval'):
            decision = self.engine.decide(inc['id'], {'action': action, 'needs_approval': True,
                                                     'why': 'Worker would prefer approval.'})
            self.assertEqual(decision['state'], 'ready')
            self.assertFalse(decision['owner_required'])
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'resolved')

    def test_missing_grant_immutable_one_use_approval(self):
        inc, decision = self.gate()
        repeated = self.engine.decide(inc['id'], {'action': 'repair', 'why': 'duplicate'})
        self.assertEqual(decision['approval_digest'], repeated['approval_digest'])
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'awaiting_approval')
        self.assertEqual(self.state['requests'], [])
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], 'wrong')
        result = self.engine.approve(inc['id'], decision['approval_digest'])
        self.assertEqual(result['status'], 'resolved')
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], decision['approval_digest'])
        self.assertEqual(len(self.state['requests']), 1)
        self.state['ok'] = False
        self.assertEqual(self.engine.tick()[0]['status'], 'awaiting_approval')
        self.assertEqual(len(self.state['requests']), 1)

    def test_expired_approval_and_config_drift_are_rejected(self):
        inc, decision = self.gate()
        self.now += 301
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], decision['approval_digest'])
        fresh = self.engine.decide(inc['id'], {})
        self.assertNotEqual(decision['approval_digest'], fresh['approval_digest'])
        old_engine = self.engine
        self.config['targets']['demo']['action_url'] += '&new=1'
        self.restart()
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], fresh['approval_digest'])
        with self.assertRaises(ValueError):
            old_engine.tick()
        newer = self.incident()
        self.assertEqual(newer['generation'], 2)
        self.assertEqual(self.state['requests'], [])

    def test_recommendations_cannot_expand_scope_or_inject_endpoints(self):
        inc = self.incident()
        for proposal in ({'action': 'delete'}, {'action_url': self.server.url}, {'command': 'sh'},
                         {'grant': True}, {'why': 'x' * 1001}, {'generation': 99}):
            with self.assertRaises(ValueError):
                self.engine.decide(inc['id'], proposal)
        self.assertEqual(self.state['requests'], [])

    def test_dedupe_new_generation_and_late_proposal(self):
        inc = self.incident()
        self.assertEqual(inc['id'], self.incident()['id'])
        self.engine.execute(inc['id'])
        self.state['ok'] = False
        newer = self.incident()
        self.assertEqual(newer['generation'], 2)
        self.assertNotEqual(newer['id'], inc['id'])
        with self.assertRaises(ValueError):
            self.engine.decide(inc['id'], {'action': 'repair'})
        self.assertEqual(len(self.engine.snapshot()['incidents']), 2)

    def test_unknown_probe_is_not_functional_false_or_resolved(self):
        for mode in ('error', 'invalid', 'redirect'):
            self.state['probe_mode'] = mode
            result = self.engine.tick()[0]
            self.assertEqual(result['status'], 'unknown')
            self.assertFalse(result['incident']['owner_required'])
            self.assertEqual(self.state['requests'], [])
        self.assertEqual(self.state['redirect_gets'], 0)
        self.state['probe_mode'] = 'normal'
        self.assertEqual(self.engine.tick()[0]['status'], 'resolved')

    def test_success_ack_without_functional_recovery_exhausts_budget(self):
        self.state['repairs'] = False
        for _ in range(4):
            result = self.engine.tick()[0]
        self.assertEqual(result['status'], 'deferred')
        self.assertFalse(result['incident']['owner_required'])
        self.assertEqual(result['verification']['status'], 'failed')
        self.assertEqual(len(self.state['requests']), 2)
        self.restart().tick()
        self.assertEqual(len(self.state['requests']), 2)
        self.state['ok'] = True
        self.engine.tick()
        self.assertEqual(self.engine.snapshot()['incidents'][-1]['state'], 'resolved')

    def test_unknown_post_is_not_replayed_even_if_probe_failed(self):
        self.state.update(post_mode='disconnect', repairs=False)
        result = self.engine.tick()[0]
        self.assertEqual(result['status'], 'deferred')
        self.assertTrue(result['incident']['uncertain'])
        self.restart().tick()
        self.engine.tick()
        self.assertEqual(len(self.state['requests']), 1)
        self.assertFalse(self.engine.snapshot()['incidents'][0]['owner_required'])

    def test_lost_ack_with_successful_readback_can_resolve(self):
        self.state['post_mode'] = 'disconnect'
        self.assertEqual(self.engine.tick()[0]['status'], 'resolved')
        self.assertEqual(len(self.state['requests']), 1)

    def test_action_redirect_is_not_followed_or_retried(self):
        self.state['post_mode'] = 'redirect'
        self.engine.tick()
        self.restart().tick()
        self.assertEqual(len(self.state['requests']), 1)
        self.assertNotEqual(self.engine.snapshot()['incidents'][0]['state'], 'resolved')

    def test_process_crash_before_dispatch_never_blindly_resends(self):
        inc = self.incident()
        code = ('import json,os,sys; from app.engine import Supervisor; '
                's=Supervisor(sys.argv[1],json.loads(sys.argv[2])); '
                's._post=lambda *args: os._exit(19); s.execute(sys.argv[3])')
        proc = subprocess.run([sys.executable, '-c', code, self.db, json.dumps(self.config), inc['id']],
                              cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 19, proc.stderr)
        self.assertEqual(self.state['requests'], [])
        self.restart().tick()
        result = self.engine.snapshot()['incidents'][0]
        self.assertEqual(result['state'], 'deferred')
        self.assertTrue(result['uncertain'])
        self.assertEqual(result['attempts'], 1)
        self.assertEqual(self.state['requests'], [])

    def test_process_crash_after_real_dispatch_verifies_without_resending(self):
        inc = self.incident()
        code = '''import json,os,sys
from app.engine import Supervisor
s=Supervisor(sys.argv[1],json.loads(sys.argv[2]))
original=s._post
def crash(*args):
    original(*args)
    os._exit(23)
s._post=crash
s.execute(sys.argv[3])
'''
        proc = subprocess.run([sys.executable, '-c', code, self.db, json.dumps(self.config), inc['id']],
                              cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 23, proc.stderr)
        self.restart().tick()
        self.assertEqual(self.engine.snapshot()['incidents'][0]['state'], 'resolved')
        self.assertEqual(len(self.state['requests']), 1)

    def test_concurrent_instances_dedupe_action(self):
        other = Supervisor(self.db, self.config, clock=lambda: self.now)
        barrier = threading.Barrier(8)
        def run(index):
            barrier.wait(timeout=5)
            return (self.engine if index % 2 else other).tick()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(run, range(8)))
        self.assertEqual(len(self.state['requests']), 1)
        self.assertEqual(len(self.engine.snapshot()['incidents']), 1)

    def test_concurrent_approval_consumed_once(self):
        inc, decision = self.gate()
        def run(_):
            try:
                return self.engine.approve(inc['id'], decision['approval_digest'])['status']
            except ValueError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run, range(4)))
        self.assertEqual(results.count('resolved'), 1)
        self.assertEqual(results.count('rejected'), 3)
        self.assertEqual(len(self.state['requests']), 1)

    def test_feedback_scope_reversal_and_candidate_is_not_authority(self):
        inc = self.incident()
        candidate = self.engine.feedback(inc['id'], 'ask first for this target')
        self.assertEqual(candidate['mode'], 'candidate')
        self.assertEqual(self.engine.decide(inc['id'], {})['state'], 'ready')
        with self.assertRaises(ValueError):
            self.engine.set_rule(candidate['id'], True)
        unknown = self.engine.feedback(inc['id'], 'please magically delete everything', mode='owner')
        self.assertEqual(unknown['mode'], 'candidate')
        rule = self.engine.feedback(inc['id'], 'ask first for this target', mode='owner')
        decision = self.engine.decide(inc['id'], {})
        self.assertEqual(decision['state'], 'awaiting_approval')
        self.engine.set_rule(rule['id'], False)
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], decision['approval_digest'])
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'resolved')

    def test_owner_wait_and_authorized_preference_cannot_expand_grant(self):
        inc, _ = self.gate()
        wait = self.engine.feedback(inc['id'], 'wait', mode='owner')
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'deferred')
        self.assertEqual(self.state['requests'], [])
        self.engine.set_rule(wait['id'], False)
        self.engine.feedback(inc['id'], 'handle authorized repairs', mode='owner')
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'awaiting_approval')
        self.assertEqual(self.state['requests'], [])

    def test_feedback_preserves_contrasting_target_and_job_contract(self):
        job = copy.deepcopy(self.config['targets']['demo'])
        job.update(kind='job', action='rerun', name='Disposable job', expected={'work': {'done': True}})
        self.config['targets']['job'] = job
        self.restart()
        inc = self.incident()
        self.engine.feedback(inc['id'], 'wait', mode='owner')
        job_inc = self.engine.observe('job')
        result = self.engine.execute(job_inc['id'])
        self.assertEqual(result['status'], 'resolved')
        self.assertEqual(self.state['requests'][0]['body']['action'], 'rerun')
        self.assertEqual(self.engine.snapshot()['targets'][0]['effective_preference'], 'wait')

    def test_json_public_records_and_ledger_redact_secrets(self):
        inc = self.incident()
        secret = self.config['targets']['demo']['action_token']
        text = secret + ' ' + self.config['targets']['demo']['action_url']
        self.engine.decide(inc['id'], {'why': text})
        self.engine.feedback(inc['id'], text)
        public = json.dumps(self.engine.snapshot())
        with sqlite3.connect(self.db) as db:
            persisted = str(db.execute('SELECT value FROM records').fetchall())
        for value in (secret, self.server.url, 'not retained', 'action-secret', 'probe-secret'):
            self.assertNotIn(value, public)
            self.assertNotIn(value, persisted)

    def test_healthy_no_incident_and_type_strict_expected(self):
        self.state['ok'] = True
        healthy = self.incident()
        self.assertIsNone(healthy['id'])
        self.assertEqual(self.engine.snapshot()['incidents'], [])
        self.state['ok'] = 1
        self.assertEqual(self.incident()['verification']['status'], 'failed')

    def test_config_round_trip_cannot_resurrect_an_old_approval(self):
        inc, decision = self.gate()
        original = copy.deepcopy(self.config)
        self.config['targets']['demo']['description'] += ' temporary change'
        self.restart()
        self.config = original
        self.restart()
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], decision['approval_digest'])
        self.assertEqual(self.state['requests'], [])

    def test_reversing_owner_policy_cannot_resurrect_an_old_approval(self):
        inc, decision = self.gate()
        rule = self.engine.feedback(inc['id'], 'wait', mode='owner')
        self.engine.set_rule(rule['id'], False)
        with self.assertRaises(ValueError):
            self.engine.approve(inc['id'], decision['approval_digest'])
        fresh = self.engine.decide(inc['id'], {})
        self.assertNotEqual(fresh['approval_digest'], decision['approval_digest'])
        self.assertEqual(self.engine.approve(inc['id'], fresh['approval_digest'])['status'], 'resolved')

    def test_short_token_redaction_cannot_corrupt_record_identity(self):
        self.config['targets']['demo']['action_token'] = 'a'
        self.restart()
        inc = self.incident()
        self.assertRegex(inc['id'], r'^[a-f0-9]{32}$')
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'resolved')
        self.assertEqual(self.state['requests'][0]['body']['action'], 'repair')

    def test_worker_wait_is_preserved_until_a_new_decision(self):
        inc = self.incident()
        self.engine.decide(inc['id'], {'action': 'wait', 'why': 'Investigating the affected function.'})
        self.assertEqual(self.restart().execute(inc['id'])['status'], 'deferred')
        self.assertEqual(self.state['requests'], [])
        self.engine.decide(inc['id'], {'action': 'repair'})
        self.assertEqual(self.engine.execute(inc['id'])['status'], 'resolved')

    def test_config_change_cannot_replay_uncertain_action(self):
        self.state.update(post_mode='disconnect', repairs=False)
        self.engine.tick()
        self.config['targets']['demo']['description'] += ' Updated owner description.'
        self.restart().tick()
        self.assertEqual(len(self.state['requests']), 1)
        newest = self.engine.snapshot()['incidents'][-1]
        self.assertEqual(newest['state'], 'deferred')
        self.assertTrue(newest['uncertain'])

    def test_independent_processes_share_one_dispatch(self):
        code = ('import json,sys; from app.engine import Supervisor; '
                'Supervisor(sys.argv[1],json.loads(sys.argv[2])).tick()')
        processes = [subprocess.Popen([sys.executable, '-c', code, self.db, json.dumps(self.config)],
                     cwd=str(Path(__file__).resolve().parents[1]), stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE) for _ in range(4)]
        for proc in processes:
            _, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, stderr)
        self.assertEqual(len(self.state['requests']), 1)
        self.assertEqual(len(self.engine.snapshot()['incidents']), 1)

    def test_config_is_detached_from_callers_and_input_validation(self):
        self.config['targets']['demo']['action_url'] = 'http://example.invalid/'
        self.assertEqual(self.engine.tick()[0]['status'], 'resolved')
        invalid = copy.deepcopy(self.config)
        invalid['targets']['demo']['probe_url'] = 'file:///etc/passwd'
        with self.assertRaises(ValueError):
            Supervisor(self.db, invalid)


if __name__ == '__main__':
    unittest.main()
