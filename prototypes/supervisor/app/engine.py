"""Durable, bounded Supervisor prototype (stdlib only).

Public JSON API (unknown IDs / invalid proposals raise ValueError):
  snapshot(): {mode: 'prototype', incidents: [Incident], decisions: [Decision],
               rules: [Rule], targets: [Target]}
  observe(target_id): Incident, or an ephemeral healthy Incident with id=None.
  decide(incident_id, {action?, why?, generation?, needs_approval?}): Decision.
  execute(incident_id), approve(incident_id, digest): Result.
  tick(): [Result], one per currently non-healthy configured target.
  feedback(incident_id, text, mode='candidate'), set_rule(id, enabled): Rule.

Incident: id, target_id, generation, state, status (same as state), kind,
  created_at, updated_at, config_digest, policy_digest, attempts, uncertain,
  decision_id, approval_digest, approval_expires_at, approval_used,
  verification, owner_required, reason. States: detected, unknown, deferred,
  ready, awaiting_approval, executing, verifying, resolved, superseded.
Decision: id, incident_id, target_id, generation, action, what, why, state,
  owner_required, policy_digest, approval_digest, expires_at, verification,
  created_at. Decisions are append-only journal entries (not mutable status).
Result: status, incident, decision (latest or None), verification, action_sent.
Verification: status ('healthy'|'failed'|'unknown'), checked_at, detail;
  no response body, URL or credentials are returned or persisted.
Rule: id, incident_id, decision_id, target_id, text, mode ('owner'|'candidate'),
  preference ('ask_first'|'authorized'|'wait'|None), enabled, created_at,
  updated_at. Only exact known phrases in owner mode activate preferences.
Target: id, name, kind, action, description, grant, effective_preference,
  verification (last check or None). URLs and action tokens are never exposed.

The host must authenticate owner-only approve/feedback/set_rule routes. Worker
input cannot choose endpoints, commands, tokens, policy or expanded actions.
Config is copied at construction; a newer constructor fences older instances.
One ledger requires one shared local filesystem supporting flock + SQLite.
Network operations are serialized under a process/thread-safe filesystem lock;
this intentionally simple prototype favors correctness over throughput.
The executor commits a reservation BEFORE POST, includes an idempotency key,
never follows redirects, and never resends an uncertain action. A crashed POST
is verified/deferred, not retried. An adapter must enforce idempotency itself.
Only a fresh matching functional GET may resolve an incident. A positive POST
acknowledgement alone cannot. Exhausted retries do not manufacture owner gates.
"""

import contextlib
import copy
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Supervisor:
    APPROVAL_TTL = 300
    HTTP_TIMEOUT = 3
    MAX_BODY = 65536
    PREFERENCES = {
        'ask first for this target': 'ask_first',
        'handle authorized repairs': 'authorized',
        'wait': 'wait',
    }

    def __init__(self, db_path, config, clock=time.time):
        self.db_path = os.path.abspath(os.fspath(db_path))
        self.config = copy.deepcopy(config)
        self.clock = clock
        self._validate_config()
        self.config_digest = self._hash(self.config)
        self._http = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._locked(check_config=False) as db:
            db.execute('CREATE TABLE IF NOT EXISTS records '
                       '(kind TEXT, id TEXT, value TEXT NOT NULL, PRIMARY KEY(kind,id))')
            self._save(db, 'meta', 'config', {'digest': self.config_digest})
            for inc in self._all(db, 'incident'):
                if inc['state'] == 'executing':
                    inc.update(state='verifying', uncertain=True,
                               reason='Interrupted action; verify before any further action.')
                    self._save_inc(db, inc)
            db.commit()

    @staticmethod
    def _hash(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode()).hexdigest()

    def _validate_config(self):
        targets = self.config.get('targets')
        if not isinstance(targets, dict):
            raise ValueError('targets must be an owner-controlled mapping')
        if type(self.config.get('max_attempts', 2)) is not int or not 1 <= self.config.get('max_attempts', 2) <= 10:
            raise ValueError('max_attempts must be an integer from 1 to 10')
        for ident, target in targets.items():
            if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ident):
                raise ValueError('invalid target identifier')
            if target.get('kind') not in ('service', 'job') or target.get('action') not in ('repair', 'rerun'):
                raise ValueError('invalid target kind/action')
            if type(target.get('grant')) is not bool or not isinstance(target.get('expected'), dict) or not target['expected']:
                raise ValueError('grant must be boolean and expected must be nonempty JSON object')
            for key in ('name', 'description'):
                if not isinstance(target.get(key), str):
                    raise ValueError('target name and description required')
            for key in ('probe_url', 'action_url'):
                parsed = urllib.parse.urlsplit(target.get(key, ''))
                if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                    raise ValueError('target endpoints must be absolute HTTP(S) URLs without userinfo/fragment')
            token = target.get('action_token', '')
            if not isinstance(token, str) or '\r' in token or '\n' in token:
                raise ValueError('invalid action token')
        self._hash(self.config)  # Reject non-JSON config, NaN and Infinity.

    def _clean(self, value):
        if isinstance(value, str):
            for target in self.config['targets'].values():
                for key in ('action_token', 'action_url', 'probe_url'):
                    if target.get(key):
                        value = value.replace(target[key], '[redacted]')
            return re.sub(r'https?://[^\s<>]+', '[redacted-url]', value)
        if isinstance(value, dict):
            return {k: self._clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._clean(v) for v in value]
        return value

    @contextlib.contextmanager
    def _locked(self, check_config=True):
        # Separate open descriptors give flock cross-thread as well as cross-process exclusion.
        with open(self.db_path + '.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            db = sqlite3.connect(self.db_path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                db.execute('PRAGMA busy_timeout=10000')
                db.execute('PRAGMA synchronous=FULL')
                db.execute('BEGIN IMMEDIATE')
                if check_config and self._get(db, 'meta', 'config')['digest'] != self.config_digest:
                    raise ValueError('stale supervisor configuration; reload current owner config')
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()
                fcntl.flock(lock, fcntl.LOCK_UN)

    @staticmethod
    def _get(db, kind, ident):
        row = db.execute('SELECT value FROM records WHERE kind=? AND id=?', (kind, ident)).fetchone()
        return json.loads(row['value']) if row else None

    @staticmethod
    def _all(db, kind):
        return [json.loads(row['value']) for row in db.execute(
            'SELECT value FROM records WHERE kind=? ORDER BY rowid', (kind,))]

    def _save(self, db, kind, ident, value):
        db.execute('INSERT INTO records(kind,id,value) VALUES(?,?,?) '
                   'ON CONFLICT(kind,id) DO UPDATE SET value=excluded.value',
                   (kind, ident, json.dumps(self._clean(value), allow_nan=False)))

    def _save_inc(self, db, inc):
        inc['status'] = inc['state']
        inc['updated_at'] = self.clock()
        self._save(db, 'incident', inc['id'], inc)

    def _target(self, ident):
        if ident not in self.config['targets']:
            raise ValueError('unknown target')
        return self.config['targets'][ident]

    def _policy(self, db, target_id):
        rules = [r for r in self._all(db, 'rule') if r['target_id'] == target_id
                 and r['mode'] == 'owner' and r['enabled'] and r['preference']]
        preference = rules[-1]['preference'] if rules else 'authorized'
        return preference, self._hash({'config': self.config_digest, 'rules': rules})

    def _current(self, db, incident_id):
        inc = self._get(db, 'incident', incident_id)
        if not inc:
            raise ValueError('unknown incident')
        if inc['config_digest'] != self.config_digest or inc['state'] in ('resolved', 'superseded'):
            raise ValueError('stale or settled incident')
        latest = [i for i in self._all(db, 'incident') if i['target_id'] == inc['target_id']][-1]
        if latest['id'] != incident_id:
            raise ValueError('stale incident generation')
        return inc

    @staticmethod
    def _matches(expected, actual):
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(k in actual and Supervisor._matches(v, actual[k]) for k, v in expected.items())
        return type(expected) is type(actual) and expected == actual

    def _probe(self, target):
        verification = {'status': 'unknown', 'checked_at': self.clock(),
                        'detail': 'Functional probe unavailable or invalid.'}
        try:
            req = urllib.request.Request(target['probe_url'], headers={'Accept': 'application/json'})
            with self._http.open(req, timeout=self.HTTP_TIMEOUT) as response:
                body = response.read(self.MAX_BODY + 1)
                if response.status != 200 or len(body) > self.MAX_BODY:
                    return verification
                actual = json.loads(body, parse_constant=lambda _: None)
                if not isinstance(actual, dict):
                    return verification
                healthy = self._matches(target['expected'], actual)
                verification.update(status='healthy' if healthy else 'failed',
                                    detail='Expected functional JSON matched.' if healthy else 'Expected functional JSON did not match.')
        except (OSError, ValueError, urllib.error.URLError):
            pass  # Exception strings may contain URLs/tokens; never persist them.
        return verification

    def _observe(self, db, target_id):
        target = self._target(target_id)
        check = self._probe(target)
        self._save(db, 'target', target_id, check)
        history = [i for i in self._all(db, 'incident') if i['target_id'] == target_id]
        inc = history[-1] if history and history[-1]['state'] not in ('resolved', 'superseded') else None
        if inc and inc['config_digest'] != self.config_digest:
            inc.update(state='superseded', owner_required=False, approval_digest=None,
                       reason='Owner configuration changed; old generation fenced.')
            self._save_inc(db, inc)
            inc = None
        if inc is None and check['status'] == 'healthy':
            return {'id': None, 'target_id': target_id, 'generation': history[-1]['generation'] if history else 0,
                    'state': 'healthy', 'status': 'healthy', 'verification': check, 'owner_required': False}
        if inc is None:
            inc = {'id': uuid.uuid4().hex, 'target_id': target_id,
                   'generation': history[-1]['generation'] + 1 if history else 1,
                   'kind': target['kind'], 'created_at': self.clock(),
                   'config_digest': self.config_digest, 'policy_digest': self._policy(db, target_id)[1],
                   'attempts': 0, 'uncertain': False, 'decision_id': None,
                   'approval_digest': None, 'approval_expires_at': None, 'approval_used': False,
                   'owner_required': False, 'state': 'detected', 'reason': 'Functional failure detected.'}
        inc['verification'] = check
        if check['status'] == 'healthy':
            inc.update(state='resolved', owner_required=False, approval_digest=None,
                       reason='Independent functional readback passed.')
            self._journal(db, inc, 'verify', inc['reason'])
        elif inc['state'] == 'executing':
            inc.update(state='verifying', uncertain=True, owner_required=False,
                       reason='Interrupted action; outcome remains uncertain.')
        elif check['status'] == 'unknown':
            inc.update(state='unknown', owner_required=False, approval_digest=None,
                       reason='Probe unavailable; failure and recovery are not established.')
        elif inc['state'] == 'unknown':
            inc.update(state='detected', reason='Functional failure confirmed.')
        self._save_inc(db, inc)
        return inc

    def observe(self, target_id):
        with self._locked() as db:
            return self._clean(self._observe(db, target_id))

    def _journal(self, db, inc, action, why):
        decision = {'id': uuid.uuid4().hex, 'incident_id': inc['id'], 'target_id': inc['target_id'],
                    'generation': inc['generation'], 'action': action,
                    'what': action + ' ' + self._target(inc['target_id'])['name'],
                    'why': why, 'state': inc['state'], 'owner_required': inc['owner_required'],
                    'policy_digest': inc['policy_digest'], 'approval_digest': inc['approval_digest'],
                    'expires_at': inc['approval_expires_at'], 'verification': inc['verification'],
                    'created_at': self.clock()}
        inc['decision_id'] = decision['id']
        self._save(db, 'decision', decision['id'], decision)
        return self._clean(decision)

    def _decide(self, db, inc, recommendation):
        if not isinstance(recommendation, dict) or set(recommendation) - {'action', 'why', 'generation', 'needs_approval'}:
            raise ValueError('recommendation may only contain action, why, generation, needs_approval')
        target = self._target(inc['target_id'])
        action = recommendation.get('action', target['action'])
        if action not in (target['action'], 'wait', 'needs_approval', 'needs approval'):
            raise ValueError('recommendation action is outside configured scope')
        if 'generation' in recommendation and recommendation['generation'] != inc['generation']:
            raise ValueError('stale recommendation generation')
        why = recommendation.get('why', '')
        if not isinstance(why, str) or len(why) > 1000:
            raise ValueError('why must be a bounded string')
        preference, policy = self._policy(db, inc['target_id'])
        if (inc['state'] == 'awaiting_approval' and inc['policy_digest'] == policy
                and inc['approval_expires_at'] > self.clock()):
            return self._get(db, 'decision', inc['decision_id'])
        inc.update(policy_digest=policy, approval_digest=None, approval_expires_at=None,
                   owner_required=False)
        if inc['uncertain'] or inc['state'] in ('executing', 'verifying'):
            inc.update(state='deferred', reason='Prior action outcome uncertain; verification only, no replay.')
        elif inc['verification']['status'] == 'unknown':
            inc.update(state='unknown', reason='Cannot act on an unavailable functional probe.')
        elif inc['attempts'] >= self.config.get('max_attempts', 2):
            inc.update(state='deferred', reason='Attempt budget exhausted; degraded, still system-owned.')
        elif preference == 'wait' or action == 'wait':
            inc.update(state='deferred', reason='Scoped wait preference; no owner decision requested.')
        elif not target['grant'] or preference == 'ask_first':
            inc.update(state='awaiting_approval', owner_required=True, approval_used=False,
                       approval_expires_at=self.clock() + self.APPROVAL_TTL,
                       reason='Owner authority required for the exact configured action.' if not target['grant'] else 'Owner requested ask-first for this target.')
            inc['approval_digest'] = self._hash({'incident': inc['id'], 'generation': inc['generation'],
                'policy': policy, 'action': target['action'], 'expires': inc['approval_expires_at'],
                'nonce': uuid.uuid4().hex})
        else:
            inc.update(state='ready', reason='Exact configured action is already authorized; worker approval requests do not create a gate.')
        if why:
            inc['reason'] += ' Worker context: ' + self._clean(why)
        decision = self._journal(db, inc, target['action'] if inc['state'] in ('ready', 'awaiting_approval') else 'wait', inc['reason'])
        self._save_inc(db, inc)
        return decision

    def decide(self, incident_id, recommendation):
        with self._locked() as db:
            return self._decide(db, self._current(db, incident_id), recommendation)

    def _result(self, db, inc, sent=False):
        return self._clean({'status': inc['state'], 'incident': inc,
                           'decision': self._get(db, 'decision', inc['decision_id']) if inc.get('decision_id') else None,
                           'verification': inc['verification'], 'action_sent': sent})

    def _post(self, target, payload):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                   'Idempotency-Key': payload['idempotency_key']}
        if target.get('action_token'):
            headers['Authorization'] = 'Bearer ' + target['action_token']
        request = urllib.request.Request(target['action_url'], data=json.dumps(payload).encode(), headers=headers, method='POST')
        with self._http.open(request, timeout=self.HTTP_TIMEOUT) as response:
            # A 2xx acknowledges dispatch, not functional recovery. Body is not trusted.
            return 200 <= response.status < 300

    def _execute(self, db, inc, approved=False):
        # Fresh preflight, under the same exclusive lock as reservation/dispatch.
        inc = self._observe(db, inc['target_id'])
        if inc['state'] == 'resolved' or inc['verification']['status'] != 'failed':
            return self._result(db, inc)
        if not approved:
            self._decide(db, inc, {})
            if inc['state'] != 'ready':
                return self._result(db, inc)
        target = self._target(inc['target_id'])
        inc.update(state='executing', attempts=inc['attempts'] + 1, uncertain=True,
                   owner_required=False, approval_used=approved or inc['approval_used'], approval_digest=None,
                   reason='Reserved exact action; functional verification required.')
        payload = {'action': target['action'], 'incident': inc['id'], 'generation': inc['generation'],
                   'idempotency_key': '%s:%s:%s' % (inc['id'], inc['generation'], inc['attempts'])}
        self._save_inc(db, inc)
        db.commit()  # The crash fence must be durable before ANY external side effect.
        acknowledged = False
        try:
            acknowledged = self._post(target, payload)
        except (OSError, ValueError, urllib.error.URLError):
            pass
        db.execute('BEGIN IMMEDIATE')
        check = self._probe(target)
        self._save(db, 'target', inc['target_id'], check)
        inc.update(verification=check, uncertain=not acknowledged)
        if check['status'] == 'healthy':
            inc.update(state='resolved', reason='Independent functional readback passed after action.')
        elif not acknowledged:
            inc.update(state='deferred', reason='Action outcome uncertain; do not resend. Continue independent verification.')
        elif inc['attempts'] >= self.config.get('max_attempts', 2):
            inc.update(state='deferred', reason='Attempt budget exhausted; functional recovery not verified.')
        else:
            inc.update(state='detected', reason='Action acknowledged but functional recovery not verified.')
        self._journal(db, inc, 'verify', inc['reason'])
        self._save_inc(db, inc)
        return self._result(db, inc, sent=True)

    def execute(self, incident_id):
        with self._locked() as db:
            inc = self._get(db, 'incident', incident_id)
            if inc and inc['state'] == 'resolved' and inc['config_digest'] == self.config_digest:
                return self._result(db, inc)
            return self._execute(db, self._current(db, incident_id))

    def approve(self, incident_id, digest):
        with self._locked() as db:
            inc = self._current(db, incident_id)
            if (inc['state'] != 'awaiting_approval' or inc['approval_used'] or not isinstance(digest, str)
                    or digest != inc['approval_digest'] or inc['approval_expires_at'] <= self.clock()
                    or inc['policy_digest'] != self._policy(db, inc['target_id'])[1]):
                raise ValueError('approval is stale, expired, consumed or mismatched')
            # Consume even if preflight now finds a recovered or unavailable target.
            inc.update(approval_used=True, approval_digest=None, owner_required=False)
            self._save_inc(db, inc)
            return self._execute(db, inc, approved=True)

    def tick(self):
        results = []
        for target_id in self.config['targets']:
            with self._locked() as db:
                inc = self._observe(db, target_id)
                if inc['id'] is not None and inc['state'] != 'resolved':
                    results.append(self._execute(db, inc))
        return results

    def feedback(self, incident_id, text, mode='candidate'):
        if mode not in ('owner', 'candidate') or not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise ValueError('feedback requires bounded text and owner/candidate mode')
        with self._locked() as db:
            inc = self._get(db, 'incident', incident_id)
            if not inc:
                raise ValueError('unknown incident')
            preference = self.PREFERENCES.get(text.strip().lower()) if mode == 'owner' else None
            rule = {'id': uuid.uuid4().hex, 'incident_id': incident_id, 'decision_id': inc['decision_id'],
                    'target_id': inc['target_id'], 'text': self._clean(text),
                    'mode': 'owner' if preference else 'candidate', 'preference': preference,
                    'enabled': bool(preference), 'created_at': self.clock(), 'updated_at': self.clock()}
            self._save(db, 'rule', rule['id'], rule)
            return rule

    def set_rule(self, rule_id, enabled):
        if type(enabled) is not bool:
            raise ValueError('enabled must be boolean')
        with self._locked() as db:
            rule = self._get(db, 'rule', rule_id)
            if not rule:
                raise ValueError('unknown rule')
            if enabled and rule['mode'] != 'owner':
                raise ValueError('candidate feedback is not an executable rule')
            rule.update(enabled=enabled, updated_at=self.clock())
            self._save(db, 'rule', rule_id, rule)
            return rule

    def snapshot(self):
        with self._locked() as db:
            targets = []
            for ident, target in self.config['targets'].items():
                record = {key: target[key] for key in ('name', 'kind', 'action', 'description', 'grant')}
                record.update(id=ident, effective_preference=self._policy(db, ident)[0],
                              verification=self._get(db, 'target', ident))
                targets.append(record)
            return self._clean({'mode': 'prototype', 'incidents': self._all(db, 'incident'),
                               'decisions': self._all(db, 'decision'), 'rules': self._all(db, 'rule'),
                               'targets': targets})
