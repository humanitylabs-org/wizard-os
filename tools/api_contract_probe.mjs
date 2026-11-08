#!/usr/bin/env node
// Exercise the Agent Service v1 contract (spec/AGENT_SERVICE_API.md) against an isolated service.
//
//   node tools/api_contract_probe.mjs --service <wizard-agent-service checkout> [--spec spec/AGENT_SERVICE_API.md] [--print]
//
// Starts the service from that checkout (createWizardServer) in-process, in front of its own deterministic Hermes
// fixture (server/fixture.mjs) plus a tiny STT and router fixture, with every state path in a throwaway directory.
// Nothing on the box is read or written, and no live endpoint is called. The checkout needs `npm ci` first (jose).
//
// For every documented route of class stable, passthrough, compat or box it runs at least one representative request
// and checks status and response shape. Negative controls prove that undocumented paths, un-allowlisted Hermes paths
// and query keys, the proposed (not shipped) routes and the known gaps all answer 404, so a pass is not the catch-all.
// Exit 0 = every case passed and every route was exercised; 1 = a failure (each printed); 2 = usage.
import { createHash } from 'node:crypto'
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const args = process.argv.slice(2)
const opt = (name, fallback = '') => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback }
const serviceDir = opt('--service')
const specPath = resolve(opt('--spec', new URL('../spec/AGENT_SERVICE_API.md', import.meta.url).pathname))
const PRINT = args.includes('--print')
if (!serviceDir) { process.stderr.write('usage: api_contract_probe.mjs --service <wizard-agent-service checkout> [--spec FILE] [--print]\n'); process.exit(2) }

// ---------- the route table (same parser as tools/check_api_contract.py) ----------
export function parseRoutes(text) {
  const block = /```routes\n([\s\S]*?)```/u.exec(text)
  if (!block) throw new Error('no ```routes block in the spec')
  const routes = []
  for (const raw of block[1].split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const [methods, path, cls, ux, query = '-'] = line.split(/\s+/u)
    for (const method of methods.split(',')) routes.push({ method, path, cls, ux, query: query === '-' ? [] : query.split(','), key: `${method} ${path}` })
  }
  return routes
}
const routes = parseRoutes(readFileSync(specPath, 'utf8'))

// ---------- isolated service ----------
const svc = (p) => import(pathToFileURL(resolve(serviceDir, p)).href)
const { createWizardServer, listen } = await svc('server/service.mjs')
const { createHermesFixture } = await svc('server/fixture.mjs')

const dir = mkdtempSync(join(tmpdir(), 'wos-api-contract-'))
for (const d of ['dist', 'ux', 'media', 'os/skills', 'state']) mkdirSync(join(dir, d), { recursive: true })
writeFileSync(join(dir, 'dist/index.html'), '<!doctype html><title>Wizard (legacy)</title><meta name="wizard-account" content="wizard-account-local">')
writeFileSync(join(dir, 'ux/index.html'), '<!doctype html><title>Wizard UX</title>')
writeFileSync(join(dir, 'os/settings.json'), JSON.stringify({ owner: { name: 'Sam' }, agent: { name: 'Wizard' }, clock: { timezone: 'Asia/Bangkok' }, voice: { language: 'en', vocabulary: ['Runtipi'] }, network: { base_url: 'https://box.example.ts.net' } }))
writeFileSync(join(dir, 'os/apps.json'), JSON.stringify({ store: 'wizardapps', apps: [
  { id: 'hello-wizard', name: 'Hello Wizard', status: 'running', summary: 'Says hello.', provides: ['greeting'], view: '/hello-wizard/', mcp: { url: 'http://127.0.0.1:9/mcp', transport: 'streamable-http' }, skill: 'skills/hello-wizard/SKILL.md' },
] }))
writeFileSync(join(dir, 'os/launcher.json'), JSON.stringify({ links: [{ id: 'notes', name: 'Notes', url: 'https://notes.example.com/' }] }))

const fixture = createHermesFixture({ expectedKey: 'probe-hermes-key' })
const fixtureOrigin = `http://127.0.0.1:${(await listen(fixture)).port}`
const sent = [] // every request the service makes to Hermes, to observe what it forwards
const fetchImpl = async (url, init = {}) => {
  if (String(url).startsWith(fixtureOrigin)) sent.push({ url: String(url).slice(fixtureOrigin.length), method: init.method || 'GET', body: typeof init.body === 'string' ? init.body : Buffer.isBuffer(init.body) ? init.body.toString('utf8') : '' })
  return fetch(url, init)
}
const aux = createServer(async (req, res) => {
  const reply = (status, value) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(value)) }
  for await (const _ of req) { /* drain */ }
  if (req.url === '/health') return reply(200, { status: 'ok', provider: 'local', model: 'fixture-stt', attested: false })
  if (req.url === '/v1/audio/transcriptions') return reply(200, { text: 'remind me to water the plants', provider: 'local', model: 'fixture-stt' })
  if (req.url === '/router') return reply(200, { choices: [{ message: { content: '{"route":"agent","summary":"water the plants"}' } }] })
  reply(404, { error: 'not found' })
})
const auxOrigin = `http://127.0.0.1:${(await listen(aux)).port}`

const app = createWizardServer({
  upstreamOrigin: fixtureOrigin, helmOrigin: fixtureOrigin, hermesKey: 'probe-hermes-key', requireAccess: false, fetchImpl,
  distDir: join(dir, 'dist'), uxDir: join(dir, 'ux'), uxPrefix: 'wizard-os-home',
  settingsPath: join(dir, 'os/settings.json'), appsJsonPath: join(dir, 'os/apps.json'), launcherPath: join(dir, 'os/launcher.json'),
  wizardOsHome: join(dir, 'os'), mcpToken: 'probe-mcp-token', bridgeLog: () => {}, bridgeWatchMs: 60_000,
  sttOrigin: auxOrigin, router: { url: `${auxOrigin}/router`, model: 'fixture-router', key: '' },
  mediaRoot: join(dir, 'media'), mediaAgentRoot: '/media', mediaIndexPath: join(dir, 'state/media-files.json'),
  runQueueStatePath: join(dir, 'state/run-queue.sqlite3'), runQueuePollIntervalMs: 50, runQueueRetryDelayMs: 50,
  uploadStatePath: join(dir, 'state/uploads.sqlite3'), uploadStagingDir: join(dir, 'state/upload-staging'), uploadReserveBytes: 0,
  userFilesRoot: join(dir, 'userfiles'),
  threadSeenStatePath: join(dir, 'state/thread-seen.json'), threadDispositionStatePath: join(dir, 'state/thread-dispositions.json'),
  threadTitleStatePath: join(dir, 'state/thread-titles.json'), threadStatusBackfillPath: join(dir, 'state/backfill.json'),
  dismissedFailureStatePath: join(dir, 'state/dismissed.json'), threadAppsStatePath: join(dir, 'state/thread-apps.json'),
  voiceRecoveryManifestPath: join(dir, 'state/voice-recoveries.json'), operatorWorkerStatePath: join(dir, 'state/operator.json'),
  agentArtifactDir: join(dir, 'state/artifacts'), agentArtifactRoots: [join(dir, 'state/images')],
  inboxDbPath: join(dir, 'state/no-inbox.sqlite3'), helmDbPath: '', hermesStatePath: '',
  claudeCredentialsPath: join(dir, 'none.json'), codexAuthPath: join(dir, 'none.json'), hermesAuthPath: join(dir, 'none.json'), hermesHome: join(dir, 'hermes'),
  joinedDelegation: 'prefer', followThrough: false,
})
const base = `http://127.0.0.1:${(await listen(app)).port}`

// ---------- cases ----------
const results = []
const exercised = new Set()
const J = { 'Content-Type': 'application/json' }
async function call(method, path, { headers = {}, body, raw = false, sse = false } = {}) {
  const ctrl = new AbortController()
  const r = await fetch(base + path, { method, headers, body, signal: ctrl.signal })
  let text = ''
  if (sse) {
    const reader = r.body.getReader()
    const deadline = Date.now() + 3000
    while (Date.now() < deadline && !/\n\n/u.test(text)) { const { value, done } = await reader.read(); if (done) break; text += Buffer.from(value).toString('utf8') }
    ctrl.abort()
  } else text = method === 'HEAD' ? '' : Buffer.from(await r.arrayBuffer()).toString(raw ? 'latin1' : 'utf8')
  let json = null
  try { json = JSON.parse(text) } catch { /* not json */ }
  return { status: r.status, headers: r.headers, text, json }
}
function check(route, label, ok, res, note = '') {
  const key = route
  if (!routes.some((r) => r.key === key) && !label.startsWith('negative')) throw new Error(`case names an undocumented route: ${key}`)
  if (ok && !label.startsWith('negative')) exercised.add(key)
  results.push({ route: key, label, ok: Boolean(ok), status: res?.status, note })
  if (PRINT || !ok) process.stdout.write(`${ok ? 'PASS' : 'FAIL'}  ${key}  [${label}]  -> ${res?.status} ${(res?.text || '').replace(/\s+/gu, ' ').slice(0, PRINT ? 400 : 200)}${note ? `  (${note})` : ''}\n`)
}
const has = (obj, keys) => Boolean(obj) && keys.every((k) => Object.hasOwn(obj, k))
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

try {
  // settings / bootstrap / apps / router
  let r = await call('GET', '/wizard/v1/bootstrap')
  check('GET /wizard/v1/bootstrap', 'boots', r.status === 200 && r.json.bootstrap === 1 && r.json.api === 'wizard-agent-service/1'
    && has(r.json, ['settings', 'settings_source', 'capabilities', 'endpoints']) && has(r.json.endpoints, ['apps', 'sessions', 'runs', 'transcribe', 'route', 'upload', 'uploads', 'shares'])
    && r.json.capabilities.resumable_uploads === true && r.json.capabilities.upload_destinations === true && r.json.endpoints.user_files === '/wizard/v1/user-files' && r.json.endpoints.uploads === '/wizard/v1/uploads' && r.json.endpoints.shares === '/wizard/v1/shares'
    && r.json.settings.fast_router.endpoint === undefined && r.json.settings.network.base_url === 'https://box.example.ts.net', r)
  r = await call('GET', '/wizard/v1/apps')
  check('GET /wizard/v1/apps', 'launcher list', r.status === 200 && r.json.schema === 1 && r.json.apps.some((a) => a.source === 'apps.json') && r.json.apps.some((a) => a.source === 'launcher.json') && !r.text.includes('127.0.0.1:9/mcp'), r)
  r = await call('POST', '/wizard/v1/route', { headers: J, body: JSON.stringify({ text: 'remind me to water the plants', apps: ['Hello Wizard'] }) })
  check('POST /wizard/v1/route', 'routes an utterance', r.status === 200 && r.json.cmd?.route === 'agent' && r.json.model === 'fixture-router', r)
  r = await call('POST', '/wizard/v1/route', { headers: J, body: '{"text":' })
  check('POST /wizard/v1/route', 'bad JSON -> 400', r.status === 400 && r.json?.error === 'invalid_request', r)
  r = await call('POST', '/wizard-os-home/api/route', { headers: J, body: JSON.stringify({ text: 'open notes' }) })
  check('POST /wizard-os-home/api/route', 'pre-bootstrap alias', r.status === 200 && has(r.json, ['cmd', 'ms', 'model']), r)

  // voice
  r = await call('GET', '/wizard/voice/status')
  check('GET /wizard/voice/status', 'ready', r.status === 200 && has(r.json, ['ready', 'provider', 'name', 'model', 'attested']) && r.json.ready === true, r)
  r = await call('POST', '/wizard/voice/transcribe', { headers: { 'Content-Type': 'audio/webm', 'X-Wizard-Filename': 'voice.webm' }, body: Buffer.from('fixture-audio') })
  check('POST /wizard/voice/transcribe', 'audio -> text', r.status === 200 && has(r.json, ['text', 'provider', 'model']), r)
  r = await call('POST', '/wizard/voice/transcribe', { headers: J, body: '{}' })
  check('POST /wizard/voice/transcribe', 'non-audio -> 415', r.status === 415 && r.json?.error === 'audio_required', r)
  const form = new FormData(); form.append('file', new Blob([Buffer.from('fixture-audio')], { type: 'audio/aac' }), 'voice.aac')
  r = await call('POST', '/wizard-os-home/api/transcribe', { body: form })
  check('POST /wizard-os-home/api/transcribe', 'multipart alias', r.status === 200 && has(r.json, ['text', 'ms']), r)
  r = await call('POST', '/wizard/voice/recovery-receipt', { headers: J, body: JSON.stringify({ recovery_id: 'nope' }) })
  check('POST /wizard/voice/recovery-receipt', 'unknown recovery -> 400', r.status === 400 && r.json?.error === 'voice_recovery_unverified', r)

  // usage, health, agent context, MCP gateway
  r = await call('GET', '/wizard/ai-usage')
  check('GET /wizard/ai-usage', 'usage snapshot', r.status === 200 && r.json && typeof r.json === 'object', r)
  r = await call('GET', '/wizard/health')
  check('GET /wizard/health', 'liveness', r.status === 200 && r.json.status === 'ok' && r.json.upstream_reachable === true && has(r.json, ['queue']), r)
  r = await call('GET', '/wizard/v1/agent-context?format=json', { headers: { Authorization: 'Bearer probe-mcp-token' } })
  check('GET /wizard/v1/agent-context', 'kernel json', r.status === 200 && has(r.json, ['text', 'chars', 'harness', 'mcp_server', 'apps']), r)
  r = await call('GET', '/wizard/v1/agent-context', { headers: { Authorization: 'Bearer probe-mcp-token' } })
  check('GET /wizard/v1/agent-context', 'kernel text', r.status === 200 && /text\/plain/u.test(r.headers.get('content-type')) && r.text.length > 40, r)
  const init = { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'probe', version: '1' } } }
  r = await call('POST', '/wizard/mcp', { headers: { ...J, Accept: 'application/json, text/event-stream' }, body: JSON.stringify(init) })
  check('POST /wizard/mcp', 'no bearer -> 401', r.status === 401 && r.json?.error === 'unauthorized', r)
  r = await call('POST', '/wizard/mcp', { headers: { ...J, Accept: 'application/json, text/event-stream', Authorization: 'Bearer probe-mcp-token', 'X-Forwarded-For': '100.64.0.9' }, body: JSON.stringify(init) })
  check('POST /wizard/mcp', 'via proxy -> 403 box_only', r.status === 403 && r.json?.error === 'box_only', r)
  r = await call('POST', '/wizard/mcp', { headers: { ...J, Accept: 'application/json, text/event-stream', Authorization: 'Bearer probe-mcp-token' }, body: JSON.stringify(init) })
  const mcpSession = r.headers.get('mcp-session-id')
  check('POST /wizard/mcp', 'initialize', r.status === 200 && r.json?.result?.serverInfo?.name === 'wizard-os' && Boolean(mcpSession), r)
  r = await call('POST', '/wizard/mcp', { headers: { ...J, Accept: 'application/json, text/event-stream', Authorization: 'Bearer probe-mcp-token', 'Mcp-Session-Id': mcpSession }, body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list' }) })
  check('POST /wizard/mcp', 'tools/list', r.status === 200 && Array.isArray(r.json?.result?.tools) && r.json.result.tools.some((t) => t.name === 'wizard_apps'), r)
  r = await call('GET', '/wizard/mcp', { headers: { Authorization: 'Bearer probe-mcp-token', 'Mcp-Session-Id': mcpSession }, sse: true })
  check('GET /wizard/mcp', 'notification stream', r.status === 200 && r.text.startsWith(': wizard-os'), r)
  r = await call('DELETE', '/wizard/mcp', { headers: { Authorization: 'Bearer probe-mcp-token', 'Mcp-Session-Id': mcpSession } })
  check('DELETE /wizard/mcp', 'end session', r.status === 200, r)

  // files (WizardOS box mode: mediaRoot)
  r = await call('POST', '/wizard/files/upload', { headers: { 'Content-Type': 'application/octet-stream', 'X-Wizard-Filename': 'notes.txt', 'X-Wizard-Mime': 'text/plain' }, body: Buffer.from('hello files') })
  const fileId = r.json?.file?.id
  check('POST /wizard/files/upload', 'bytes -> file', r.status === 201 && /^wf_[0-9a-f]{32}$/u.test(fileId || '') && !r.text.includes(dir), r)
  r = await call('POST', '/wizard/files/upload', { headers: J, body: '{}' })
  check('POST /wizard/files/upload', 'JSON body -> 415', r.status === 415 && r.json?.error === 'bytes_required', r)
  r = await call('GET', '/wizard/files')
  check('GET /wizard/files', 'list', r.status === 200 && r.json.files.some((f) => f.id === fileId), r)
  r = await call('GET', `/wizard/files/${fileId}/content`, { headers: { Range: 'bytes=0-4' } })
  check('GET /wizard/files/{id}/content', 'range', r.status === 206 && r.text === 'hello', r)
  r = await call('HEAD', `/wizard/files/${fileId}/content`)
  check('HEAD /wizard/files/{id}/content', 'head', r.status === 200, r)
  r = await call('GET', '/wizard/files/wf_00000000000000000000000000000000/content')
  check('GET /wizard/files/{id}/content', 'unknown id -> 404', r.status === 404, r)
  r = await call('POST', '/wizard/files/invite', { headers: J, body: '{}' })
  check('POST /wizard/files/invite', 'no Wizard Inbox -> 503', r.status === 503 && r.json?.error === 'service_unavailable', r, 'needs the Wizard Inbox (James\'s box); route exists')

  // attachments (agent artifacts, then Helm fallback)
  const att = '1'.repeat(32)
  r = await call('GET', `/wizard/attachments/${att}`)
  check('GET /wizard/attachments/{id}', 'helm-served image', r.status === 200 && /image\/png/u.test(r.headers.get('content-type')), r)
  r = await call('HEAD', `/wizard/attachments/${att}`)
  check('HEAD /wizard/attachments/{id}', 'head', r.status === 200 && /image\/png/u.test(r.headers.get('content-type')), r)
  r = await call('GET', `/wizard/attachments/${'9'.repeat(32)}`)
  check('GET /wizard/attachments/{id}', 'unknown -> 404', r.status === 404 && r.json?.error === 'attachment_not_found', r)

  // read state
  r = await call('GET', '/wizard/thread-seen')
  check('GET /wizard/thread-seen', 'state', r.status === 200 && has(r.json, ['state']), r)
  const seen = { initializedAt: 1791763200000, threads: { 'direct:chat-recent': { updatedAt: '2026-10-12T00:00:00.000Z', previewFingerprint: 'abc123', messageCount: 2, status: 'completed', seenAt: 1791763300000 } } }
  r = await call('PUT', '/wizard/thread-seen', { headers: J, body: JSON.stringify(seen) })
  check('PUT /wizard/thread-seen', 'merge', r.status === 200 && r.json?.state?.threads?.['direct:chat-recent']?.seenAt === 1791763300000, r)
  r = await call('PUT', '/wizard/thread-seen', { headers: J, body: JSON.stringify({ threads: {} }) })
  check('PUT /wizard/thread-seen', 'invalid state -> 400', r.status === 400 && r.json?.error === 'invalid_request', r)
  r = await call('PUT', '/wizard/thread-seen', { headers: { 'Content-Type': 'text/plain' }, body: 'x' })
  check('PUT /wizard/thread-seen', 'non-JSON -> 415', r.status === 415, r)
  r = await call('GET', '/wizard/thread-dispositions')
  check('GET /wizard/thread-dispositions', 'state', r.status === 200 && has(r.json, ['state']), r)
  r = await call('PUT', '/wizard/thread-dispositions', { headers: J, body: JSON.stringify({ runtime: 'direct', sessionId: 'chat-recent', deferred: true }) })
  check('PUT /wizard/thread-dispositions', 'defer', r.status === 200 && has(r.json, ['record']), r)
  r = await call('GET', '/wizard/thread-dispositions?x=1')
  check('GET /wizard/thread-dispositions', 'query -> 400', r.status === 400, r)

  // attention, failures, filings (Helm-backed on James's box)
  r = await call('GET', '/wizard/attention')
  check('GET /wizard/attention', 'list', r.status === 200 && Array.isArray(r.json?.attention), r)
  r = await call('POST', '/wizard/attention/not-a-uuid/retry')
  check('POST /wizard/attention/{id}/retry', 'bad id -> 400', r.status === 400 && r.json?.error === 'invalid_request', r)
  r = await call('POST', '/wizard/attention/not-a-uuid/dismiss')
  check('POST /wizard/attention/{id}/dismiss', 'bad id -> 400', r.status === 400 && r.json?.error === 'invalid_request', r)
  r = await call('POST', '/wizard/session-failure/chat-recent/dismiss')
  check('POST /wizard/session-failure/{id}/dismiss', 'dismiss', r.status === 200 && r.json?.dismissed === true && r.json.session_id === 'chat-recent', r)
  r = await call('POST', '/wizard/filings', { headers: J, body: JSON.stringify({ session_id: 'bad id!', client_command_id: 'c1' }) })
  check('POST /wizard/filings', 'bad session -> 400', r.status === 400 && r.json?.error === 'invalid_request', r)
  r = await call('POST', '/wizard/filings', { headers: J, body: JSON.stringify({ session_id: 'chat-recent', client_command_id: 'cmd-1', runtime: 'direct' }) })
  check('POST /wizard/filings', 'no Helm -> error, route exists', r.status >= 400 && r.json?.error && r.json.error !== 'not_found', r, 'filing needs Helm (James\'s box); the UX falls back to archive')
  r = await call('POST', '/wizard/filings/chat-recent/status', { headers: J, body: JSON.stringify({ runtime: 'direct' }) })
  check('POST /wizard/filings/{id}/status', 'no Helm -> error, route exists', r.status >= 400 && r.json?.error && r.json.error !== 'not_found', r)

  // Hermes passthrough: threads
  r = await call('GET', '/wizard/hermes/api/model/options')
  check('GET /wizard/hermes/api/model/options', 'options', r.status === 200 && Array.isArray(r.json?.options), r)
  r = await call('GET', '/wizard/hermes/api/sessions?limit=100&offset=0&include_children=false')
  check('GET /wizard/hermes/api/sessions', 'list', r.status === 200 && JSON.stringify(r.json).includes('chat-recent'), r)
  r = await call('POST', '/wizard/hermes/api/sessions', { headers: J, body: JSON.stringify({ source: 'wizard-mobile', id: 'wizard_probe_1' }) })
  check('POST /wizard/hermes/api/sessions', 'create', r.status === 201 && r.json?.id === 'wizard_probe_1', r)
  r = await call('GET', '/wizard/hermes/api/sessions/chat-recent')
  check('GET /wizard/hermes/api/sessions/{id}', 'read', r.status === 200 && r.json?.id === 'chat-recent', r)
  r = await call('PATCH', '/wizard/hermes/api/sessions/wizard_probe_1', { headers: J, body: JSON.stringify({ title: 'Probe thread' }) })
  check('PATCH /wizard/hermes/api/sessions/{id}', 'rename', r.status === 200 && r.json?.title === 'Probe thread', r)
  r = await call('GET', '/wizard/hermes/api/sessions/chat-recent/messages?order=oldest&limit=500&offset=0&include_compacted=true&view=wizard')
  const rows = r.json?.messages || r.json?.data || []
  const ids = rows.map((m) => m.id)
  const byId = Object.fromEntries(rows.map((m) => [m.id, m]))
  check('GET /wizard/hermes/api/sessions/{id}/messages', 'history (view=wizard)', r.status === 200 && byId['m-1'] && byId['m-2']
    && !byId['m-delegation'] && !byId['m-task-restore'] && byId['m-process-wakeup']?.display_kind === 'process_wakeup'
    && rows.every((m) => typeof m.shareable === 'boolean'), r, `rows ${JSON.stringify(rows.map((m) => [m.id, m.display_kind ?? null]))}`)
  r = await call('GET', '/wizard/hermes/api/sessions/chat-recent/messages?order=latest&limit=200')
  const rawIds = (r.json?.messages || r.json?.data || []).map((m) => m.id)
  check('GET /wizard/hermes/api/sessions/{id}/messages', 'history without view keeps internal rows', r.status === 200 && rawIds.includes('m-delegation'), r)
  r = await call('POST', '/wizard/hermes/api/sessions/chat-recent/model', { headers: J, body: JSON.stringify({ model: 'fixture-fast' }) })
  check('POST /wizard/hermes/api/sessions/{id}/model', 'switch model', r.status === 200 && r.json?.model === 'fixture-fast', r)

  // Hermes passthrough: runs (queued admission, as deployed)
  const admit = async (session, input, key) => call('POST', '/wizard/hermes/v1/runs', { headers: { ...J, 'Idempotency-Key': key }, body: JSON.stringify({ session_id: session, input, instructions: 'CLIENT-VIEW-CONTEXT-7f3a' }) })
  r = await admit('wizard_probe_1', 'please hold while I steer', 'probe-key-1')
  const runId = r.json?.run_id
  check('POST /wizard/hermes/v1/runs', 'durable admission (202, public wizardq_ id)', r.status === 202 && /^wizardq_[0-9a-f]{32}$/u.test(runId || '') && r.json.session_id === 'wizard_probe_1'
    && ['queued', 'running'].includes(r.json.status) && r.headers.get('idempotency-replayed') === 'false', r)
  r = await admit('wizard_probe_1', 'please hold while I steer', 'probe-key-1')
  check('POST /wizard/hermes/v1/runs', 'same Idempotency-Key replays', r.status === 202 && r.json?.run_id === runId && r.headers.get('idempotency-replayed') === 'true', r)
  r = await call('POST', '/wizard/hermes/v1/runs', { headers: { 'Content-Type': 'text/plain' }, body: 'hi' })
  check('POST /wizard/hermes/v1/runs', 'non-JSON -> 415', r.status === 415 && r.json?.error === 'json_required', r)
  let run = null
  for (let i = 0; i < 60; i++) { r = await call('GET', `/wizard/hermes/v1/runs/${runId}`); run = r.json; if (run?.status === 'running') break; await wait(50) }
  check('GET /wizard/hermes/v1/runs/{id}', 'status by public id', r.status === 200 && run?.run_id === runId && run.status === 'running', r)
  const forwarded = sent.filter((s) => s.method === 'POST' && s.url === '/v1/runs').map((s) => s.body).join('\n')
  const dropped = forwarded.length > 0 && !forwarded.includes('CLIENT-VIEW-CONTEXT-7f3a')
  check('POST /wizard/hermes/v1/runs', 'observed: client `instructions` replaced by the service (discrepancy D1)', dropped, r, 'documented as a known discrepancy; flips if the service starts merging them')
  r = await call('GET', `/wizard/hermes/v1/runs/${runId}/events`, { sse: true })
  check('GET /wizard/hermes/v1/runs/{id}/events', 'SSE stream', r.status === 200 && /^event: /mu.test(r.text), r)
  r = await call('POST', `/wizard/hermes/v1/runs/${runId}/steer`, { headers: J, body: JSON.stringify({ input: 'continue holding, also check the docs' }) })
  check('POST /wizard/hermes/v1/runs/{id}/steer', 'accepted', r.status === 200 && r.json?.accepted === true, r)
  r = await call('POST', `/wizard/hermes/v1/runs/${runId}/stop`)
  check('POST /wizard/hermes/v1/runs/{id}/stop', 'stop', r.status === 202 && r.json?.accepted === true, r)
  r = await call('POST', '/wizard/hermes/v1/runs/wizardq_00000000000000000000000000000000/steer', { headers: J, body: JSON.stringify({ input: 'x' }) })
  check('POST /wizard/hermes/v1/runs/{id}/steer', 'unknown queued id -> 404', r.status === 404, r)
  r = await admit('chat-long', 'this needs approval', 'probe-key-2')
  const approvalRun = r.json?.run_id
  for (let i = 0; i < 80; i++) { r = await call('GET', `/wizard/hermes/v1/runs/${approvalRun}`); run = r.json; if (run?.status === 'waiting_for_approval') break; await wait(50) }
  r = await call('POST', `/wizard/hermes/v1/runs/${approvalRun}/approval`, { headers: J, body: JSON.stringify({ choice: 'deny', request_id: run?.approval?.request_id }) })
  check('POST /wizard/hermes/v1/runs/{id}/approval', 'answer', r.status === 200 && r.json?.accepted === true, r)

  // resumable uploads and shares (WizardOS box mode: mediaRoot)
  const bytes = Buffer.from('resumable upload body, two chunks')
  const digest = createHash('sha256').update(bytes).digest('hex')
  const uploadBody = { client_upload_id: 'probe-upload-1', filename: 'notes.txt', mime: 'text/plain', bytes: bytes.length, sha256: digest }
  r = await call('POST', '/wizard/v1/uploads', { headers: J, body: JSON.stringify(uploadBody) })
  const uploadId = r.json?.upload_id
  check('POST /wizard/v1/uploads', 'create', r.status === 201 && /^up_[0-9a-f]{32}$/u.test(uploadId || '') && r.json.offset === 0 && r.json.bytes === bytes.length && r.json.chunk_bytes === 8388608 && r.json.status === 'uploading', r)
  r = await call('POST', '/wizard/v1/uploads', { headers: J, body: JSON.stringify({ ...uploadBody, client_upload_id: 'probe-too-big', bytes: 2 ** 52, sha256: undefined }) })
  check('POST /wizard/v1/uploads', 'does not fit -> 507', r.status === 507 && r.json?.error === 'insufficient_storage', r)
  const O = { 'Content-Type': 'application/offset+octet-stream' }
  r = await call('PATCH', `/wizard/v1/uploads/${uploadId}`, { headers: { ...O, 'Upload-Offset': '0' }, body: bytes.subarray(0, 10) })
  check('PATCH /wizard/v1/uploads/{id}', 'chunk -> 204 + Upload-Offset', r.status === 204 && r.headers.get('upload-offset') === '10', r)
  r = await call('PATCH', `/wizard/v1/uploads/${uploadId}`, { headers: { ...O, 'Upload-Offset': '0' }, body: bytes.subarray(0, 10) })
  check('PATCH /wizard/v1/uploads/{id}', 'offset mismatch -> 409 + server offset', r.status === 409 && r.json?.error === 'offset_mismatch' && r.json.offset === 10, r)
  r = await call('POST', '/wizard/v1/uploads', { headers: J, body: JSON.stringify(uploadBody) })
  check('POST /wizard/v1/uploads', 'same client_upload_id -> same upload, current offset', r.status === 201 && r.json?.upload_id === uploadId && r.json.offset === 10, r)
  r = await call('GET', `/wizard/v1/uploads/${uploadId}`)
  check('GET /wizard/v1/uploads/{id}', 'offset', r.status === 200 && r.json?.offset === 10 && r.json.status === 'uploading', r)
  r = await call('POST', `/wizard/v1/uploads/${uploadId}/complete`, { headers: J, body: '{}' })
  check('POST /wizard/v1/uploads/{id}/complete', 'incomplete -> 409', r.status === 409 && r.json?.error === 'upload_incomplete' && r.json.offset === 10, r)
  r = await call('PATCH', `/wizard/v1/uploads/${uploadId}`, { headers: { ...O, 'Upload-Offset': '10' }, body: bytes.subarray(10) })
  r = await call('POST', `/wizard/v1/uploads/${uploadId}/complete`, { headers: J, body: '{}' })
  const uploadedFile = r.json?.file
  check('POST /wizard/v1/uploads/{id}/complete', 'file, same shape as /wizard/files/upload', r.status === 200 && /^wf_[0-9a-f]{32}$/u.test(uploadedFile?.id || '') && uploadedFile.sha256 === digest && uploadedFile.bytes === bytes.length && !r.text.includes(dir), r)
  r = await call('GET', `/wizard/files/${uploadedFile?.id}/content`)
  check('GET /wizard/files/{id}/content', 'resumable upload is a Wizard file', r.status === 200 && r.text === bytes.toString(), r)
  r = await call('POST', '/wizard/v1/shares', { headers: J, body: JSON.stringify({ client_share_id: 'probe-share-x', agent: 'nobody', files: [{ filename: 'a.txt', bytes: 1 }] }) })
  check('POST /wizard/v1/shares', 'unknown agent -> 409, no fallback', r.status === 409 && r.json?.error === 'agent_unavailable', r)
  const shareBody = JSON.stringify({ client_share_id: 'probe-share-1', note: 'Filed from the share sheet', files: [{ filename: 'scan.pdf', mime: 'application/pdf', bytes: bytes.length, sha256: digest }] })
  r = await call('POST', '/wizard/v1/shares', { headers: J, body: shareBody })
  const share = r.json
  check('POST /wizard/v1/shares', 'create (default agent, new thread)', r.status === 201 && /^sh_[0-9a-f]{32}$/u.test(share?.share_id || '') && share.agent === 'hermes' && /^wizard_\d+_[0-9a-f]{12}$/u.test(share.thread_id) && share.status === 'uploading' && share.uploads?.length === 1, r)
  r = await call('POST', '/wizard/v1/shares', { headers: J, body: shareBody })
  check('POST /wizard/v1/shares', 'same client_share_id -> same share', r.status === 201 && r.json?.share_id === share?.share_id, r)
  const shareUpload = share?.uploads?.[0]?.upload_id
  await call('PATCH', `/wizard/v1/uploads/${shareUpload}`, { headers: { ...O, 'Upload-Offset': '0' }, body: bytes })
  const runsBefore = sent.filter((s) => s.method === 'POST' && s.url === '/v1/runs').length
  await Promise.all([1, 2, 3].map(() => call('POST', `/wizard/v1/uploads/${shareUpload}/complete`, { headers: J, body: '{}' })))
  let shareStatus = null
  for (let i = 0; i < 100; i++) { r = await call('GET', `/wizard/v1/shares/${share?.share_id}`); shareStatus = r.json; if (shareStatus?.status === 'delivered') break; await wait(50) }
  await call('POST', '/wizard/v1/shares', { headers: J, body: shareBody })
  for (let i = 0; i < 40 && sent.filter((s) => s.method === 'POST' && s.url === '/v1/runs').length === runsBefore; i++) await wait(50)
  await wait(300)
  const shareRuns = sent.filter((s) => s.method === 'POST' && s.url === '/v1/runs').slice(runsBefore).map((s) => JSON.parse(s.body || '{}'))
  check('GET /wizard/v1/shares/{id}', 'delivered once into the new thread', r.status === 200 && shareStatus?.status === 'delivered' && shareStatus.thread_id === share?.thread_id
    && shareRuns.length === 1 && shareRuns[0].session_id === share?.thread_id && JSON.stringify(shareRuns[0].input).includes('Filed from the share sheet'), r, `runs ${shareRuns.length}`)

  // upload destination (Files app) and the user-files read API
  mkdirSync(join(dir, 'userfiles', 'Projects'), { recursive: true })
  const destBytes = Buffer.from('placed in a folder')
  r = await call('POST', '/wizard/v1/uploads', { headers: J, body: JSON.stringify({ client_upload_id: 'probe-dest-1', filename: 'clip.txt', mime: 'text/plain', bytes: destBytes.length, destination: { folder: 'Projects' } }) })
  const destId = r.json?.upload_id
  check('POST /wizard/v1/uploads', 'destination folder -> create', r.status === 201 && /^up_[0-9a-f]{32}$/u.test(destId || ''), r)
  await call('PATCH', `/wizard/v1/uploads/${destId}`, { headers: { ...O, 'Upload-Offset': '0' }, body: destBytes })
  r = await call('POST', `/wizard/v1/uploads/${destId}/complete`, { headers: J, body: '{}' })
  check('POST /wizard/v1/uploads/{id}/complete', 'destination -> placed in the folder by path', r.status === 200 && r.json?.file?.path === 'Projects/clip.txt' && r.json.file.location === 'files_root' && !r.text.includes(dir), r)
  r = await call('POST', '/wizard/v1/uploads', { headers: J, body: JSON.stringify({ client_upload_id: 'probe-dest-2', filename: 'x', bytes: 1, destination: { folder: '../escape' } }) })
  check('POST /wizard/v1/uploads', 'destination outside the root -> 400', r.status === 400 && r.json?.field === 'destination.folder', r)
  r = await call('GET', '/wizard/v1/user-files?folder=Projects')
  check('GET /wizard/v1/user-files', 'list a folder', r.status === 200 && r.json?.folder === 'Projects' && r.json.entries?.some((e) => e.name === 'clip.txt' && e.is_dir === false && e.size === destBytes.length), r)
  r = await call('GET', '/wizard/v1/user-files?folder=..')
  check('GET /wizard/v1/user-files', 'escaping folder -> 400', r.status === 400, r)
  r = await call('GET', '/wizard/v1/user-files/content?path=Projects/clip.txt', { headers: { Range: 'bytes=0-5' } })
  check('GET /wizard/v1/user-files/content', 'range', r.status === 206 && r.text === 'placed', r)
  r = await call('HEAD', '/wizard/v1/user-files/content?path=Projects/clip.txt')
  check('HEAD /wizard/v1/user-files/content', 'head', r.status === 200 && r.headers.get('content-length') === String(destBytes.length), r)

  // pages and static
  r = await call('GET', '/wizard/')
  check('GET /wizard/', 'legacy Wizard page', r.status === 200 && /<title>Wizard \(legacy\)/u.test(r.text), r)
  r = await call('GET', '/wizard-os-home/')
  check('GET /wizard-os-home/', 'Wizard UX page', r.status === 200 && /<title>Wizard UX/u.test(r.text), r)

  // negative controls: each must answer 404, proving a pass above was not the catch-all
  const negatives = [
    ['GET', '/wizard/v1/does-not-exist', 'undocumented /wizard/v1 path'],
    ['POST', '/wizard/v1/does-not-exist', 'undocumented POST'],
    ['GET', '/wizard/hermes/api/config', 'Hermes path outside the allowlist'],
    ['GET', '/wizard/hermes/api/sessions?evil=1', 'query key outside the allowlist'],
    ['GET', '/wizard/hermes/api/sessions/chat-recent/messages?limit=501', 'limit above 500'],
    ['DELETE', '/wizard/hermes/api/sessions/chat-recent', 'method outside the allowlist'],
  ]
  for (const route of routes.filter((x) => x.cls === 'proposed' || x.cls === 'gap')) negatives.push([route.method, route.path.replace(/\{[^}]+\}/gu, 'x'), `${route.cls} route is not served on this commit`])
  for (const [method, path, why] of negatives) {
    r = await call(method, path)
    check(`${method} ${path}`, `negative: ${why}`, r.status === 404, r)
  }

  // every documented, served route must have been exercised
  for (const route of routes) {
    if (['stable', 'passthrough', 'compat', 'box', 'page'].includes(route.cls) && !exercised.has(route.key)) {
      results.push({ route: route.key, label: 'coverage', ok: false, note: 'documented route has no passing probe case' })
      process.stdout.write(`FAIL  ${route.key}  [coverage] documented route has no passing probe case\n`)
    }
  }
} finally {
  app.closeAllConnections?.(); await new Promise((r) => app.close(r))
  aux.closeAllConnections?.(); await new Promise((r) => aux.close(r))
  await fixture.closeFixture()
}

const failed = results.filter((r) => !r.ok)
const served = routes.filter((r) => ['stable', 'passthrough', 'compat', 'box', 'page'].includes(r.cls))
process.stdout.write(`\n${results.length} cases, ${failed.length} failed; ${exercised.size}/${served.length} documented served routes exercised; ${results.filter((r) => r.label.startsWith('negative')).length} negative controls\n`)
process.exit(failed.length ? 1 : 0)
