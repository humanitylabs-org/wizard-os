// Real Agent Service gateway (server/agent-bridge.mjs from the Service checkout given as argv[2]) on a loopback port.
// The agent side (the harness) speaks MCP to /wizard/mcp with the gateway token; the gateway reads apps.json and
// grants/agent-service.json exactly as on a box (no injected resolver) and proxies tool calls to the app listeners.
import { createServer } from 'node:http'
import { pathToFileURL } from 'node:url'
import { join } from 'node:path'

const [svcRoot, home, port, token] = process.argv.slice(2)
const { createAgentBridge } = await import(pathToFileURL(join(svcRoot, 'server/agent-bridge.mjs')).href)
const bridge = createAgentBridge({
  appsJsonPath: join(home, 'apps.json'), osHome: home, token, writeSkills: false, timeoutMs: 15000,
  log: (l) => process.stderr.write(`[bridge] ${l}\n`),
})
createServer((req, res) => {
  if (new URL(req.url, 'http://x').pathname === '/wizard/mcp') return bridge.handle(req, res)
  res.writeHead(404); res.end()
}).listen(Number(port), '127.0.0.1', () => process.stdout.write('ready\n'))
