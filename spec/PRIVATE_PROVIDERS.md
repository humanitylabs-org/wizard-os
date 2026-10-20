# Private model providers

Status: **Direction approved by James (20 Oct 2026), details proposed**, DECISIONS #66. Extends [AGENTS.md](AGENTS.md) §2, §6 and §8 and [AI_CONNECTIONS.md](AI_CONNECTIONS.md). Written for the target Wizard OS box, where every agent, the main one included, runs in its own container.

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
  egress: [inference.tinfoil.sh, atc.tinfoil.sh]   # the only outside hosts it may reach (local: [])
```

- It holds the provider credential. The credential never leaves the app.
- It serves the **relay** on `relay_port`, reachable only from the relay network (below), never from the tailnet, the shell or other apps.
- `attested-relay`: the relay forwards ciphertext. It authenticates the client token, swaps in the provider key, and forwards to the enclave named in `X-Tinfoil-Enclave-Url`. It never decrypts and has no way to: the in-seal client encrypts each request body to the enclave's attested key ([Tinfoil EHBP](https://docs.tinfoil.sh/resources/ehbp), [proxy guide](https://docs.tinfoil.sh/guides/proxy-server)).
- `local`: the relay is the model's OpenAI-compatible endpoint, or forwards to it. The model runs in the app's own container on an `internal` network with no internet, or on another machine the owner names (see Local models).
- It never logs or stores request or response bodies.
- It mints one **client token** per private agent through a box-only route the Agent Service calls (`POST /api/private-clients {agent}` → `{token}`, `DELETE /api/private-clients/<agent>`). A token works only on the relay.
- `/api/connection` (wizard.ai-connection/2) lists its models. The Agent Service offers only those to the private agent.

### 2. In-seal client (owned by Wizard OS, one per private agent)

A small sidecar in the private agent's own compose that does the provider-specific privacy work inside the seal. It presents a plain OpenAI-compatible endpoint to that agent's Hermes.

- Profile `tinfoil`: the official Tinfoil SDK (JavaScript or Python, the ones that fetch attestation through a proxy). `base_url` and `attestation_bundle_url` both point at the provider app's relay, and the SDK verifies the enclave attestation itself. Prompts are encrypted before they leave the sidecar.
- Profile `passthrough` (local providers): forwards to the relay unchanged. Kept as a sidecar so Hermes's view is the same for every provider and the agent network stays the same shape.
- Holds only its client token. It never holds the provider key.
- Image published from `wizard-app-store` like other system images, pinned by digest, updated only with the owner's yes.

### 3. Agent Service

- `agent.model.provider` names the provider **app id** (for example `wizard-tinfoil`), not a hardcoded provider. `TINFOIL` and `LOCAL` in `server/agents.mjs` become entries built from installed apps that declare `private-inference`.
- Confidentiality (§8 routing by model) comes from that declaration, not from a provider name list.
- On create, link and switch it mints the client token, writes the in-seal client's config, and asks the runtime driver to (re)start the agent compose. On delete or switch it revokes the old token.
- If the provider app is missing or stopped, the private agent fails visibly. It never falls back to another provider.

## Networks

```
agent-<id>-net   internal: true   Hermes + in-seal client           no internet
relay-<app>-net  internal: true   in-seal clients + provider app    no internet
<app>-egress     normal           provider app only                 its declared egress hosts
```

- Hermes can reach only its in-seal client. The in-seal client can reach only the relay. Only the provider app can reach outside, and only to its declared hosts.
- A `local` provider has no egress network.
- Other agents and apps are never attached to a relay network.

## Local models

`kind: local` with one of:
- **On the box:** the app runs the model server (for example llama.cpp or Ollama) in its own container.
- **On another owner machine** (a Mac mini, a GPU box): the app's relay forwards over the tailnet to an address the owner sets. That machine is then inside the private boundary, and the Agents page says so in one line ("Runs on Thales"). The address is a setting, never source.

## Owner experience

- Agents → New agent → Private → **Model provider** lists every installed private provider by name. If none is installed: "Install a private provider" opens the Store filtered to `private-inference`.
- The private agent's page shows its provider and the one-line privacy promise for that kind: "Encrypted on this box; Tinfoil can't read it" or "Runs on this box / on Thales".
- The model picker's Private group lists the private agent's models, as today (§8).

## What a provider app must pass before it is listed as private

1. `wam check --proposal` validates the `private_inference` block.
2. **Relay sees no plaintext** (`attested-relay`): a probe sends a codeword through the in-seal client; a capture on the relay network contains `Ehbp-Encapsulated-Key` and no codeword.
3. **No egress beyond declared hosts:** a connect attempt to any other host fails from the app container.
4. **No body logging:** the codeword appears in no app log or app-data file after the probe.
5. **Relay reachability:** the relay port answers on the relay network and refuses from the tailnet, the shell and another app.
6. Pinned image digest; the update goes through the owner's update approval.

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

- Streaming: Tinfoil's JavaScript SDK streams encrypted responses; confirm Python does before choosing the client's language (slice 2).
- Prompt-cache scoping: `tinfoil-proxy` adds a per-user cache secret. Keep an equivalent per agent in the in-seal client.
