# Disposable release install failure evidence

The release acceptance harness keeps backend install diagnostics in its **private
worker log**, before each existing Wisdom baseline retry and before deleting a
failed guest. It records bounded Runtipi/container logs, image identities and the
Wisdom generated compose. It never collects container environments, app.env,
auth stores or content databases. Do not publish the raw diagnostic log.

The probes are read-only and best effort: they cannot turn a failed install into
a pass, replace its exception, prefetch images, change permissions, pin an older
app or add retries. Candidates still have one install attempt; old upgrade
baselines retain their existing single retry. A timeout is not retried.

A stock ARM public 0.3.40 diagnostic installation on 26 October 2026 installed
current public Wisdom `9ff0811e4287b5fb72251a03718f4914d453a352` on its first
Wisdom attempt. The unchanged baseline content/progress/SQLite-restore journey
passed. This does not support a deterministic incompatibility between current
Wisdom and that old release. An earlier public base-install attempt encountered
Docker Hub HTTP 429 responses for Traefik and Postgres; the supported public
installer succeeded when run again. This establishes registry throttling as a
real environmental failure, **not the proven cause of the historical Wisdom
failure**, whose guest/backend logs had already been deleted.

Do not change release pins or weaken acceptance based on that inference. Rerun
with these diagnostics and use the actual backend failure if it recurs. This
harness change is not a product install repair and is not release acceptance.
