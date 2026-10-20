# Private model providers

Status: **Direction approved by James (20 Oct 2026); Tinfoil path built and proven on the test rig; local provisioning decision recorded, implementation pending**, DECISIONS #66. Extends [AGENTS.md](AGENTS.md) §2, §6 and §8 and [AI_CONNECTIONS.md](AI_CONNECTIONS.md). Written for the target Wizard OS box, where every agent, the main one included, runs in its own container.

## The rule

A private agent is not tied to one provider. It uses a **private provider**, which is a connection app that declares `private-inference`. Tinfoil is the first. A model running on the owner's own hardware is the second. Any later private provider ships as its own app, and the Private agent needs no change to use it.

The owner picks the provider when creating a private agent and can switch it later to another private provider. Switching to a non-private provider is still refused (§6 of AGENTS.md, `agent.private_sealed`).

## Who can see what

This is the promise each piece has to keep. The tests in the acceptance section check it.

| Party | Sees conversation content? | Sees anything else |
| --- | --- | --- |
| The private agent | Yes, it is the agent | |
| Its in-seal client (below) | Yes, it sits inside the seal | |
| An `attested-relay` provider app (Tinfoil) | **No.** It only relays ciphertext | when, how big, which agent |
| A `local` provider app | Yes, it is (or reaches) the model | |
| The upstream service (Tinfoil) | No. It is decrypted only inside the attested enclave | when, how big, which API key |
| The main agent and every other agent | No | that the private agent exists |
| Other apps | No | nothing |
| Root on the box | Yes | out of scope; the owner's box is the owner's |

## The pieces

### 1. Provider app (owned by whoever builds the provider)

A normal connection app (AI_CONNECTIONS.md) plus:

```yaml
# wizard.md
provides: [ai-connection, private-inference]
private_inference:
  kind: attested-relay          # attested-relay | local
  client: tinfoil               # attested-relay only: which in-seal client profile encrypts for it
  relay_port: 8090              # where in-seal clients reach it, on the relay network only
  egress: [inference.tinfoil.sh, atc.tinfoil.sh, tuf-repo-cdn.sigstore.dev]   # exact outside hosts (local: [])
```

- It holds the provider credential. The credential never leaves the app.
- It serves the **relay** on `relay_port`, reachable only from the relay network (below), never from the tailnet, the shell or other apps.
- `attested-relay`: the relay listens on port 8090. It authenticates the client token, replaces it with the provider key upstream, and forwards ciphertext to the enclave named in `X-Tinfoil-Enclave-Url`. It passes `Ehbp-Encapsulated-Key` requests and `Ehbp-Response-Nonce` responses through and streams bodies without parsing, decrypting or logging them. It has no decryption key: the in-seal client encrypts each request body to the enclave's attested key ([Tinfoil EHBP](https://docs.tinfoil.sh/resources/ehbp), [proxy guide](https://docs.tinfoil.sh/guides/proxy-server)).
- Tinfoil's authenticated `GET /attestation` fetches a bundle with a fixed upstream `POST` to `https://atc.tinfoil.sh/attestation`, selecting `inference.tinfoil.sh` and `tinfoilsh/confidential-model-router`. It does not accept a caller-selected attestation target. The Sigstore TUF host in `egress` is needed by the app's Python credential-test path; it is not an extra client route.
- `local`: the relay is the model's OpenAI-compatible endpoint, or forwards to it. The provider app and model server stay inside the seal with no internet (see [Local providers](#local-providers)).
- It never logs or stores request or response bodies.
- It mints one **client token** per private agent through a box-only route the Agent Service calls (`POST /api/private-clients {agent}` → `{token, relay_url}`, `DELETE /api/private-clients/<agent>`). A token works only on the relay and is stored only as a SHA-256 hash in provider data, never logged. Repeating POST rotates it and revokes the old token; DELETE revokes it.
- `/api/connection` (wizard.ai-connection/2) lists its models. The Agent Service offers only those to the private agent. Tinfoil credential verification requires one successful authenticated inference; saving a key, attesting and listing models alone leave `credentialVerified: false`.

### 2. In-seal client (owned by Wizard OS, one per private agent)

A small sidecar in the private agent's own compose that does the provider-specific privacy work inside the seal. It presents a plain OpenAI-compatible endpoint to that agent's Hermes.

- Profile `tinfoil`: fetches the attestation bundle from the relay with its client token, then uses the official JavaScript SDK's public `Verifier.verifyBundle` and official EHBP transport. Verification is pinned to `inference.tinfoil.sh` and `tinfoilsh/confidential-model-router`; the report, code provenance, matching measurements and domain-bound certificate must verify before the attested key is used. Prompts are encrypted before they leave the sidecar. Attestation and inference both use only the relay; there is no direct internet fetch, patched verifier or plaintext retry.
- Profile `passthrough` (local providers): forwards to the relay unchanged. Kept as a sidecar so Hermes's view is the same for every provider and the agent network stays the same shape.
- Holds only its client token. It never holds the provider key.
- Image published from `wizard-app-store` like other system images, pinned by digest, updated only with the owner's yes.

### 3. Agent Service

- `agent.model.provider` names the provider **app id** (for example `wizard-tinfoil`), not a hardcoded provider. `TINFOIL` and `LOCAL` in `server/agents.mjs` become entries built from installed apps that declare `private-inference`.
- Confidentiality (§8 routing by model) comes from that declaration, not from a provider name list.
- On create, link and switch it mints the client token, writes the in-seal client's config, and asks the runtime driver to (re)start the agent compose. On delete or switch it revokes the old token.
- If the provider app is missing or stopped, the private agent fails visibly. It never falls back to another provider.

## Networks

The trusted agent runtime owns the private topology. The main agent runs in its
own container; provider apps never inherit its network or Runtipi's shared app
network. Use this topology (or an equivalently proven sealed implementation):

| Network | Properties | Members |
| --- | --- | --- |
| `agent-<id>-sandbox` | internal, no host bridge IP (`inhibit_ipv4=true`) | Hermes, its in-seal client, its scoped system edge |
| `agent-<id>-uplink` | normal | that agent's scoped system edge only |
| `wizard-relay-<app>` | internal, IPv4 /24 from `10.252.0.0/16`, no host bridge IP | linked in-seal clients and that provider app |
| `wizard-egress-<app>` | internal, IPv4 /24 from `10.253.0.0/16`, no host bridge IP | that provider app and its runtime-owned system edge |
| system-edge uplink | normal | provider's system edge only, never the provider process |

Hermes has no Internet route. It reaches its own client and the Wizard gateway
through its scoped edge; the Agent Service reaches Hermes through that edge's
host-loopback API relay. The client may initiate only to its selected provider
relay endpoint, and only Hermes may initiate to that client's API. Enforce these
flows with stateful FORWARD/INPUT policy before starting the containers: shared
bridge membership alone does not isolate peers. Require rootful Docker's verified
firewall hooks and bridge-netfilter support, or an equivalently proven enforcement
path. Internal bridges must have no host IP; internal:true alone does not deny
container-to-host access.

A provider process is attached only to its internal relay and internal egress
networks, apart from an explicitly checked local model-server sibling network
(see [Local providers](#local-providers)). Remove every ordinary app-network
interface; deny direct IPv4/IPv6,
arbitrary TCP/UDP, host destinations and external DNS. Drop all capabilities,
use no-new-privileges/read-only rootfs, and direct external DNS forwarding to the
provider's own loopback while preserving local Docker service-name resolution.
Never publish the relay port. Owner/box HTTP/MCP remains reachable only through
fixed incoming management routes, with existing app authentication/write guards;
republish only explicitly approved host-loopback ports, not a general outgoing
bridge or caller-selected forwarding target.

For nonempty `private_inference.egress`, one small runtime-owned system edge is the
only provider-side container with an external interface. It supplies an internal-
only HTTPS CONNECT proxy and may also carry those fixed incoming management
routes. Give the provider `HTTPS_PROXY`; prove that every real HTTP/SDK transport
honors it. The proxy accepts only exact declared canonical DNS hostnames on port
443, resolves them itself, rejects IP literals/nonpublic DNS answers and plain
HTTP, and binds TLS SNI to the CONNECT hostname. Do not replace hostname policy
with a one-time IP allowlist or suffix/wildcard rule. TLS remains end-to-end.

For `private_inference.egress: []`, provide no CONNECT proxy/listener and no direct
outbound route. The internal provider network may still support narrow incoming
owner management via an ingress-only system edge; this is not inference egress.
Provision local model files separately. A remote owner-machine model route needs
its own explicitly governed private-boundary contract, never an implicit empty-
egress exception.

Only linked clients and their selected provider join a relay network. Hermes,
unrelated providers and ordinary apps never join it. Other clients/provider
peers must not be able to initiate requests to an in-seal client's unauthenticated
API; the stateful client policy remains mandatory.

The runtime creates and reconciles provider networks/system edges when linking
and at startup. Stop the provider before replacing policy or removing interfaces;
validate network ownership and container settings, apply proxy/guards, verify exact
membership, then start. A failed or unsupported setup stays stopped visibly, never
falls back. Providers and private clients must not auto-restart before their
required policy is re-established. Install/update must use an internal bootstrap
and run reconciliation before exposure; restoring shared app networking is a
security defect.

## Local models

### Local providers

Decision owner: **Archimedes, 20 Oct 2026**. A sealed `kind: local` provider never has internet, including for model downloads. `egress: []` means no internet, not merely no cloud inference.

- Fetch weights in a separate one-shot provisioning step, using the pinned URL and SHA-256 declared in `wizard.md` under `private_inference.model_artifacts`. Verify the bytes before admitting them to the weights volume; mount that volume read-only into the sealed provider. Provisioning never gives the provider a temporary internet route.
- The provider app and model server both run inside the seal. Prefer one container; if a separate model-server container is needed, use a provider-owned internal sibling network with no host bridge IP or outside route. It is an explicitly checked part of the seal, not a shared app network.
- The runtime refuses to link a private agent until the declared weights are present and verified. Missing or mismatched weights leave the provider unavailable.
- Remote owner-machine (tailnet) local mode is deferred; empty egress does not authorize it.

The current local-model candidate failed admission on the test rig. Its provisioning network and separate model-server network did not meet this boundary; local inference and the six acceptance checks are not yet proven.

## Owner experience

- Agents → New agent → Private → **Model provider** lists every installed private provider by name. If none is installed: "Install a private provider" opens the Store filtered to `private-inference`.
- The private agent's page shows its provider and the one-line privacy promise for that kind: "Encrypted on this box; Tinfoil can't read it" or "Runs on this box".
- The model picker's Private group lists the private agent's models, as today (§8).

## What a provider app must pass before it is listed as private

1. `wam check --proposal` validates the `private_inference` block.
2. **Relay sees no plaintext** (`attested-relay`): a probe sends a codeword through the in-seal client; a capture on the relay network contains `Ehbp-Encapsulated-Key` and no codeword.
3. **No egress beyond declared hosts:** a connect attempt to any other host fails from the app container.
4. **No body logging:** the codeword appears in no app log or app-data file after the probe.
5. **Relay reachability:** the relay port answers on the relay network and refuses from the tailnet, the shell and another app.
6. Pinned image digest; the update goes through the owner's update approval.

## Acceptance

Run against a private agent created through the Agent Service on the fresh Runtipi test box. The six checks live in [`wizard-agent-service/ops/private-provider-rig`](https://github.com/humanitylabs-org/wizard-agent-service/tree/01967d0d53993151e1fc1d4677b3a684ed5b9653/ops/private-provider-rig) ([PR #65](https://github.com/humanitylabs-org/wizard-agent-service/pull/65)):

1. Relay capture contains `Ehbp-Encapsulated-Key` and never the probe codeword (`attested-relay`; EHBP is not promised for `local`).
2. Hermes cannot reach the internet and can reach its in-seal client.
3. The client can initiate only to the selected relay; internet, host and lateral probes fail.
4. The provider key exists only in provider data, not the agent home, `.env`, compose or runtime directory.
5. Stopping the provider makes the agent fail visibly with no fallback; restoring it permits a successful answer.
6. The codeword appears in no provider log or app-data file.

All six passed for Tinfoil on the Thales test box after integration repairs. The local provider was rejected before agent creation, so its checks remain blocked, not passed. This is test-rig evidence, not a published image or production rollout.

## Migration on an existing box

1. Install the Tinfoil provider app and paste the key there.
2. Switch the private agent to it: the per-agent `tinfoil-proxy` sidecar and the key copy in the agent's `home/.env` are removed, and the in-seal client takes their place. History, memory and files stay where they are.
3. The legacy host proxy route (`custom:tinfoil-operator`) stops serving chat. Voice transcription keeps its own route until the transcription slot moves to provider apps (separate work).

## Build order

| # | Slice | Owner | Done when |
| --- | --- | --- | --- |
| 1 | This spec, DECISIONS #66 | Archimedes | merged |
| 2 | In-seal client, `tinfoil` profile | Archimedes | a streamed completion goes through a stand-in relay that holds the key; relay capture shows no codeword |
| 3 | Agent Service: provider = app id, networks, tokens, Agents page provider list | Archimedes | fresh-box test on Thales: private agent on a stub provider app, sealed network checks pass |
| 4 | Relay mode in the Tinfoil app | Miguel (wizard-tinfoil) | acceptance list above passes |
| 5 | Local model provider app | Archimedes | private agent answers from a local model with its networks offline |
| 6 | Move the owner's box | Archimedes | private agent on the Tinfoil app; old sidecar and `tinfoil-operator` chat route gone |

## Open questions

- Prompt-cache scoping: `tinfoil-proxy` adds a per-user cache secret. Keep an equivalent per agent in the in-seal client.
