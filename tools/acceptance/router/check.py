"""Judge one acceptance run: read evidence/<state>/*.json, print PASS/FAIL per expectation, write checks.json.

usage: python3 check.py <run dir>
Expectations come from the task brief (four box states) and spec/CONNECTION_ROUTER.md: a tested model that is
reachable routes as a match; swap: ask offers a named replacement and waits for one owner tap; swap: never offers only
Connect; nothing swaps silently; runs fail closed with an owner-readable reason.
"""
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
ev = run / "evidence"
results = []


def ok(state, cond, what, detail=None):
    results.append({"state": state, "pass": bool(cond), "check": what, **({} if cond else {"detail": detail})})
    print(("PASS " if cond else "FAIL ") + f"[{state}] {what}" + ("" if cond else f"  {json.dumps(detail)[:600]}"))


def load(state, name):
    p = ev / state / name
    return json.loads(p.read_text()) if p.exists() else None


def feats(needs):
    return {m["feature"]: m for m in (needs or {}).get("models", [])}


def rows(sheet, app, key="rows"):
    s = (sheet or {}).get("sheets", {}).get(app, {})
    src = s.get("after_approve", {}) if key == "after" else s
    return {r["feature"]: r for r in src.get("rows", [])}


def infers(state):
    p = ev / state / "provider-requests.jsonl"
    lines = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    return [(l["provider"], l["model"]) for l in lines if l["path"] == "/api/infer"]


def done(run_result):
    ev_ = (run_result or {}).get("events") or []
    return next((e for e in ev_ if isinstance(e, dict) and e.get("type") == "done"), None)


def run_ok(r, provider, model, chosen):
    d = done(r)
    return bool(r and r.get("ok", True) and d and d.get("provider") == provider and d.get("model") == model and d.get("chosen") == chosen)


def run_fail(r):
    """Fail closed: no done event, an error code, and a message plus a fix link the owner can follow."""
    if not r or done(r):
        return False
    if "fault" in r:
        f = r["fault"]
        return bool(f.get("code") and f.get("message") and f.get("fix_url", "").startswith("/"))
    body = r.get("body") if isinstance(r.get("body"), dict) else None
    if body is None and isinstance(r.get("events"), dict):
        body = r["events"]
    return bool(body and body.get("code") and body.get("message") and str(body.get("fix_url", "")).startswith("/")
                and r.get("http_status", 0) >= 400)


def common(state):
    pre = load(state, "pre.json")
    up = load(state, "up.json")
    ok(state, up and up["healthy"] == {"router": True, "wisdom": True}, "Router and Wisdom containers healthy", up)
    ok(state, pre and pre["needs_unknown_grant"][0] == 403, "an unknown app grant is refused (403)", pre and pre["needs_unknown_grant"])
    for phase in ("pre", "post"):
        r = load(state, f"runs-{phase}.json")
        if r:
            o = r["wisdom_opens"]
            ok(state, o["status"] == 200 and o["is_html"] and o["health"] == 200, f"Wisdom installs and opens ({phase})", o)
    return pre


def claude_only():
    s = "claude-only"
    pre, sheet, runs = common(s), load(s, "sheet-pre.json"), load(s, "runs-pre.json")
    w = feats(pre["needs"]["wisdom"])
    ok(s, all(w[f]["status"] == "ready" and w[f]["route"]["provider"] == "wizard-claude" and w[f]["route"]["model"] == w[f]["tested_on"]
              and w[f]["route"]["chosen"] == "match" for f in ("ask-ai", "look-up", "chapter-authoring")),
       "all three Wisdom features route to their tested Claude model (match)", w)
    sw = rows(sheet, "wisdom")
    ok(s, len(sw) == 3 and all(not r["buttons"] for r in sw.values()), "Wisdom sheet: three Ready rows, no swap or connect offered", sw)
    ok(s, "Every feature has a model" in sheet["sheets"]["wisdom"]["heading"], "Wisdom sheet heading: every feature has a model", sheet["sheets"]["wisdom"]["heading"])
    fx, sf = feats(pre["needs"]["router-fixture"]), rows(sheet, "router-fixture")
    ok(s, fx["summarize"]["status"] == "ready" and fx["summarize"]["route"]["chosen"] == "match", "fixture summarize (tested on Claude) routes", fx["summarize"])
    ok(s, fx["draft"]["status"] == "needs_owner" and fx["draft"]["offered"]["model"] == "claude-sonnet-5" and fx["draft"]["route"] is None,
       "fixture draft (tested on ChatGPT, swap: ask) asks: offers claude-sonnet-5, no route", fx["draft"])
    ok(s, sf["draft"]["buttons"] == ["Connect ChatGPT", "Approve swap to claude-sonnet-5"], "fixture sheet: draft shows Connect ChatGPT + Approve swap", sf.get("draft"))
    ok(s, all(run_ok(runs["wisdom"][f], "wizard-claude", w[f]["tested_on"], "match") for f in w),
       "one run per Wisdom feature answered by the tested Claude model", runs["wisdom"])
    ok(s, run_fail(runs["router-fixture"]["draft"]) and run_fail(runs["router-fixture"]["classify"]),
       "fixture swap-ask features without an approved route fail closed", runs["router-fixture"])
    ok(s, all(p == "wizard-claude" for p, _ in infers(s)) and ("wizard-claude", "claude-opus-5-5") in infers(s),
       "only Claude received inference calls", infers(s))


def chatgpt_only():
    s = "chatgpt-only"
    pre, sheet = common(s), load(s, "sheet-pre.json")
    rpre, rpost = load(s, "runs-pre.json"), load(s, "runs-post.json")
    w, sw = feats(pre["needs"]["wisdom"]), rows(sheet, "wisdom")
    ok(s, all(w[f]["route"] is None and w[f]["status"] != "ready" for f in w), "no Wisdom feature has a route: nothing swapped silently", w)
    ok(s, w["chapter-authoring"]["status"] == "blocked" and "offered" not in w["chapter-authoring"]
       and sw["chapter-authoring"]["buttons"] == ["Connect Claude"], "swap: never (chapter-authoring) offers Connect Claude only, stays off", (w["chapter-authoring"], sw.get("chapter-authoring")))
    ok(s, w["look-up"]["status"] == "needs_owner" and w["look-up"]["offered"]["model"] == "gpt-6-luna"
       and sw["look-up"]["buttons"] == ["Connect Claude", "Approve swap to gpt-6-luna"], "look-up (swap: ask) shows Connect Claude or Approve swap to gpt-6-luna", (w["look-up"], sw.get("look-up")))
    ok(s, w["ask-ai"]["status"] == "needs_owner" and "offered" not in w["ask-ai"] and sw["ask-ai"]["buttons"] == ["Connect Claude"],
       "ask-ai needs web search, which no ChatGPT model declares: Connect Claude only", (w["ask-ai"], sw.get("ask-ai")))
    ok(s, all(run_fail(rpre["wisdom"][f]) for f in w), "before approval every Wisdom run fails closed with a reason", rpre["wisdom"])
    after = rows(sheet, "wisdom", "after")
    posts = sheet["sheets"]["wisdom"].get("approve_posts", [])
    ok(s, len(posts) == 1 and json.loads(posts[0]).get("model") == "gpt-6-luna" and "approved swap" in after.get("look-up", {}).get("state", "").lower(),
       "one owner tap on Approve swap stores the swap (sheet shows Ready · approved swap)", (posts, after.get("look-up")))
    route = next((r for r in sheet["owner_routes"]["routes"] if r["app"] == "wisdom" and r["feature"] == "look-up"), None)
    ok(s, route and route["provider"] == "wizard-chatgpt" and route["model"] == "gpt-6-luna" and route["chosen"] == "owner-swap",
       "owner routes record look-up → gpt-6-luna as owner-swap", sheet["owner_routes"])
    ok(s, run_ok(rpost["wisdom"]["look-up"], "wizard-chatgpt", "gpt-6-luna", "owner-swap"),
       "after approval look-up runs on gpt-6-luna and Wisdom admits it as owner-swap", rpost["wisdom"]["look-up"])
    ok(s, run_fail(rpost["wisdom"]["ask-ai"]) and run_fail(rpost["wisdom"]["chapter-authoring"]),
       "after approval ask-ai and chapter-authoring still fail closed", rpost["wisdom"])
    fx = feats(pre["needs"]["router-fixture"])
    ok(s, fx["draft"]["status"] == "ready" and fx["draft"]["route"]["chosen"] == "match", "fixture draft (tested on ChatGPT) routes", fx["draft"])
    ok(s, all(p == "wizard-chatgpt" for p, _ in infers(s)) and ("wizard-chatgpt", "gpt-6-luna") in infers(s),
       "only ChatGPT received inference calls, and only after approval for Wisdom", infers(s))


def both():
    s = "both"
    pre, rpre = common(s), load(s, "runs-pre.json")
    w = feats(pre["needs"]["wisdom"])
    ok(s, all(w[f]["status"] == "ready" and w[f]["route"]["provider"] == "wizard-claude" and w[f]["route"]["chosen"] == "match" for f in w),
       "Wisdom features route to their tested Claude models", w)
    ok(s, all(not r["buttons"] for r in rows(load(s, "sheet-pre.json"), "wisdom").values()), "Wisdom sheet offers nothing", None)
    fx = feats(pre["needs"]["router-fixture"])
    ok(s, fx["summarize"]["route"]["provider"] == "wizard-claude" and fx["draft"]["route"]["provider"] == "wizard-chatgpt",
       "fixture: each tested model routes to its own provider", fx)
    a, b = load(s, "order-claude-first.json"), load(s, "order-chatgpt-first.json")
    ok(s, a and b, "provider-order snapshots captured", None)
    if a and b:
        fa, fb = feats(a["owner_needs"]["router-fixture"]), feats(b["owner_needs"]["router-fixture"])
        ok(s, a["owner_routes"]["provider_order"] == ["wizard-claude", "wizard-chatgpt"]
           and b["owner_routes"]["provider_order"] == ["wizard-chatgpt", "wizard-claude"], "GET /v1/owner/routes reflects each POST provider-order", (a["owner_routes"], b["owner_routes"]))
        ok(s, fa["classify"]["offered"]["provider"] == "wizard-claude" and fb["classify"]["offered"]["provider"] == "wizard-chatgpt",
           "provider order pre-selects the swap for the untested feature", (fa["classify"].get("offered"), fb["classify"].get("offered")))
        strip = lambda r: sorted((x["app"], x["feature"], x["provider"], x["model"], x["chosen"]) for x in r["routes"])
        ok(s, strip(a["owner_routes"]) == strip(b["owner_routes"]), "changing the order never re-routes an existing route", (a["owner_routes"], b["owner_routes"]))
        sa, sb = rows(load(s, "sheet-claude-first.json"), "router-fixture"), rows(load(s, "sheet-chatgpt-first.json"), "router-fixture")
        ok(s, "Approve swap to claude-haiku-4-5" in sa.get("classify", {}).get("buttons", []) and "Approve swap to gpt-6-luna" in sb.get("classify", {}).get("buttons", []),
           "fixture sheet follows the order (claude-haiku-4-5, then gpt-6-luna)", (sa.get("classify"), sb.get("classify")))
    ok(s, all(run_ok(rpre["wisdom"][f], "wizard-claude", w[f]["tested_on"], "match") for f in w), "one run per Wisdom feature on Claude", rpre["wisdom"])
    ok(s, run_ok(rpre["router-fixture"]["draft"], "wizard-chatgpt", "gpt-6.1-sol", "match"), "fixture draft runs on ChatGPT", rpre["router-fixture"]["draft"])


def neither():
    s = "neither"
    pre, sheet, rpre = common(s), load(s, "sheet-pre.json"), load(s, "runs-pre.json")
    w = feats(pre["needs"]["wisdom"])
    ok(s, all(w[f]["route"] is None and "offered" not in w[f] for f in w), "no Wisdom route and no swap offered", w)
    allrows = list(rows(sheet, "wisdom").values()) + list(rows(sheet, "router-fixture").values())
    ok(s, len(allrows) == 6 and all(r["buttons"] and all(b.startswith("Connect") for b in r["buttons"]) for r in allrows),
       "both sheets show Connect actions only", allrows)
    ok(s, all(run_fail(rpre["wisdom"][f]) for f in w) and all(run_fail(rpre["router-fixture"][f]) for f in rpre["router-fixture"]),
       "every /v1/models/<feature>/run fails closed with code, message and fix link", rpre)
    ok(s, infers(s) == [], "no provider received an inference call", infers(s))
    ok(s, pre["owner_routes"]["routes"] == [], "Router stored no routes", pre["owner_routes"])


for name, fn in (("claude-only", claude_only), ("chatgpt-only", chatgpt_only), ("both", both), ("neither", neither)):
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - a crashed judge is a failed state, with the reason
        ok(name, False, "evidence complete and judgeable", repr(e))
passed = sum(r["pass"] for r in results)
(run / "checks.json").write_text(json.dumps({"passed": passed, "failed": len(results) - passed, "results": results}, indent=1))
print(f"{passed} passed, {len(results) - passed} failed")
sys.exit(0 if passed == len(results) else 1)
