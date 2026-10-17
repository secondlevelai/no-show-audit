#!/usr/bin/env python3
"""No-Show Audit audit: every number in the report comes from here.

Claude pulls raw HighLevel responses into files and passes the paths. This script
never trusts Claude with arithmetic: it dedupes, applies the eligibility rules,
does the money math and builds the breakdowns. Standard library only.

Usage:
  audit.py ids FILE...                      contact-ID batches (<=100) to fetch, as JSON lines
  audit.py paths                            where settings and reports live
  audit.py newrun [--client ID]             make today's report folder, print its path
  audit.py run [--config CFG] --client ID --out DIR FILE...
                [--recovery-rate 0.10] [--price N] [--close-rate R] [--days 90]
                [--booked-at-override MANIFEST]   (dev/test data only)
  audit.py selftest

FILEs are execute_operation results, raw or saved by Claude Code. Each one names
its own operation ("operationId"), so order doesn't matter. Recognised:
  get-calendar-events, search-contacts-advanced, get-pipelines,
  get-custom-fields, search-users, get-calendars.
Writes DIR/audit.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

HOME_DIR = Path.home() / ".no-show-audit"
DEFAULT_CONFIG = HOME_DIR / "config.json"
REPORTS_DIR = Path.home() / "Documents" / "no-show-audit"
HELD = {"showed", "completed"}
NOSHOW = {"noshow"}
UPCOMING_OK = {"confirmed", "new", "active", "showed", "completed"}  # counts as "rebooked"
UNMARKED = {"confirmed", "new", "active"}                              # in the past = never marked
DEFAULT_RECOVERY = 0.10
GAP_BUCKETS = [("same day", 0, 1), ("1-2 days out", 1, 3), ("3-6 days out", 3, 7), ("7+ days out", 7, 10**6)]
DAYPARTS = [("Morning (before 12pm)", 0, 12), ("Afternoon (12-5pm)", 12, 17), ("Evening (5pm+)", 17, 24)]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------------------------------------------------------------- reading files

def load_result(path: str) -> dict:
    """An execute_operation result: {"operationId":..., "data":{...}} (or bare data)."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("[") and '"type"' in text[:200]:      # MCP content blocks
        blocks = json.loads(text)
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    obj = json.loads(text)
    if "data" in obj and "operationId" in obj:
        if obj.get("success") is False:
            raise SystemExit(f"{path}: HighLevel returned an error for {obj['operationId']}: "
                             f"{json.dumps(obj.get('data'))[:300]}")
        return {"op": obj["operationId"], "data": obj["data"]}
    # bare API response: guess by shape
    for key, op in (("events", "get-calendar-events"), ("contacts", "search-contacts-advanced"),
                    ("pipelines", "get-pipelines"), ("customFields", "get-custom-fields"),
                    ("users", "search-users"), ("calendars", "get-calendars")):
        if key in obj:
            return {"op": op, "data": obj}
    raise SystemExit(f"{path}: not a HighLevel result this script knows")


LOOKUPS = ("get-pipelines", "get-custom-fields", "search-users")


def collect(files: list[str]) -> dict:
    out = defaultdict(list)
    for f in files:
        try:
            r = load_result(f)
        except (json.JSONDecodeError, ValueError) as err:
            # names and stage labels are nice-to-have; appointments and contacts are not
            if Path(f).stat().st_size < 50_000:
                print(f"WARNING: couldn't read {f} ({err}). Skipping it: closers or stages may show as IDs.",
                      file=sys.stderr)
                continue
            raise SystemExit(f"{f}: not valid JSON ({err})")
        d = r["data"]
        if r["op"] == "get-calendar-events":
            out["events"] += d.get("events", [])
        elif r["op"] in ("search-contacts-advanced", "search-contacts"):
            out["contacts"] += d.get("contacts", [])
        elif r["op"] == "get-pipelines":
            out["pipelines"] += d.get("pipelines", [])
        elif r["op"] == "get-custom-fields":
            out["fields"] += d.get("customFields", [])
        elif r["op"] == "search-users":
            out["users"] += d.get("users", [])
        elif r["op"] == "get-calendars":
            out["calendars"] += d.get("calendars", [])
    # the same event can arrive twice (overlapping pulls): keep one
    seen, events = set(), []
    for e in out["events"]:
        if e.get("id") not in seen and not e.get("deleted"):
            seen.add(e.get("id"))
            events.append(e)
    out["events"] = events
    out["contacts"] = list({c["id"]: c for c in out["contacts"]}.values())
    return out


def ts(s: str | None) -> datetime | None:
    if not s:
        return None
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s / 1000, timezone.utc)
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------- helpers

def status_of(e: dict) -> str:
    return (e.get("appointmentStatus") or e.get("appoinmentStatus") or e.get("status") or "").lower()


def sms_opted_out(c: dict) -> bool:
    if c.get("dnd") is True:
        return True
    ds = c.get("dndSettings") or {}
    for k in ("SMS", "sms"):
        if (ds.get(k) or {}).get("status") == "active":
            return True
    return False


def gap_bucket(days: float) -> str:
    if days < -0.01:   # "booked" after the call: imported or edited data, can't tell
        return "Unknown"
    for name, lo, hi in GAP_BUCKETS:
        if lo <= days < hi:
            return name
    return GAP_BUCKETS[-1][0]


def daypart(hour: int) -> str:
    for name, lo, hi in DAYPARTS:
        if lo <= hour < hi:
            return name
    return DAYPARTS[-1][0]


def rate_rows(counter_ns: Counter, counter_held: Counter, order: list[str] | None = None,
              min_calls: int = 1) -> list[dict]:
    keys = order or sorted(set(counter_ns) | set(counter_held),
                           key=lambda k: -(counter_ns[k] + counter_held[k]))
    rows = []
    for k in keys:
        n, h = counter_ns[k], counter_held[k]
        if n + h < min_calls:
            continue
        rows.append({"label": k, "calls": n + h, "no_shows": n,
                     "rate": round(n / (n + h), 4) if n + h else None})
    return rows


def worst_insight(rows: list[dict], what: str, overall: float, min_calls: int = 10) -> str | None:
    """One sentence about the worst segment, only when it's clearly worse and big enough."""
    ok = [r for r in rows if r["rate"] is not None and r["calls"] >= min_calls]
    if len(ok) < 2 or not overall:
        return None
    worst, best = max(ok, key=lambda r: r["rate"]), min(ok, key=lambda r: r["rate"])
    if worst["rate"] < overall * 1.2 or best["rate"] == 0:
        return None
    x = worst["rate"] / best["rate"]
    return (f"{what} {worst['label']} no-show {round(worst['rate'] * 100)}% of the time, "
            f"{x:.1f}x the {best['label']} rate ({round(best['rate'] * 100)}%).")


# ---------------------------------------------------------------- setters

SETTER_RE = ("setter", "set by", "booked by", "appointment setter", "sdr")


def setter_candidates(raw: dict, cal_ids: set) -> list[dict]:
    """Where this account records who set each call, with how often it's filled in.

    HighLevel has no standard setter field. Teams use the contact owner, the user
    who booked the appointment, or a custom field. Coverage is measured over the
    booked calls, so the best-filled option can be recommended.
    """
    ev = [e for e in raw["events"] if not cal_ids or e.get("calendarId") in cal_ids]
    contacts = {c["id"]: c for c in raw.get("contacts", [])}
    n = len(ev) or 1
    cands = []
    owner = sum(1 for e in ev if (contacts.get(e.get("contactId")) or {}).get("assignedTo"))
    cands.append({"source": "contact_owner", "label": "Contact owner (who the contact is assigned to)",
                  "coverage": round(owner / n, 3)})
    booked = sum(1 for e in ev if ((e.get("createdBy") or {}).get("userId"))
                 and (e.get("createdBy") or {}).get("userId") != e.get("assignedUserId"))
    cands.append({"source": "booked_by", "label": "Who booked the call in HighLevel",
                  "coverage": round(booked / n, 3)})
    for f in raw.get("fields", []):
        if any(w in (f.get("name") or "").lower() for w in SETTER_RE):
            filled = sum(1 for e in ev for cf in ((contacts.get(e.get("contactId")) or {}).get("customFields") or [])
                         if cf.get("id") == f["id"] and cf.get("value") not in (None, "", []))
            cands.append({"source": f"custom_field:{f['id']}", "label": f"Custom field \"{f['name']}\"",
                          "coverage": round(filled / n, 3)})
    return sorted(cands, key=lambda c: -c["coverage"])


def make_setter_of(source: str | None, users: dict, contacts: dict):
    """Return (event -> setter name or None)."""
    if not source or source == "none":
        return lambda e: None
    if source == "contact_owner":
        def owner(e):
            uid = (contacts.get(e.get("contactId")) or {}).get("assignedTo")
            return (users.get(uid) or "Setter " + uid[:5]) if uid else None
        return owner
    if source == "booked_by":
        def f(e):
            uid = (e.get("createdBy") or {}).get("userId")
            if not uid or uid == e.get("assignedUserId"):
                return None
            return users.get(uid) or "Setter " + uid[:5]
        return f
    if source.startswith("custom_field:"):
        fid = source.split(":", 1)[1]

        def g(e):
            for cf in ((contacts.get(e.get("contactId")) or {}).get("customFields") or []):
                if cf.get("id") == fid and cf.get("value") not in (None, "", []):
                    v = cf["value"]
                    return users.get(v, v) if isinstance(v, str) else str(v)
            return None
        return g
    return lambda e: None


# ---------------------------------------------------------------- the audit

def run_audit(raw: dict, cfg: dict, now: datetime, days: int = 90, recovery_rate: float = DEFAULT_RECOVERY,
              price: float | None = None, close_rate: float | None = None,
              booked_override: dict | None = None, setter_source: str | None = None) -> dict:
    tzname = cfg.get("timezone") or "UTC"
    tz = ZoneInfo(tzname) if ZoneInfo else timezone.utc
    since = now - timedelta(days=days)
    cal_ids = {c["id"] for c in cfg.get("calendars", [])}
    buyer_tags = {t.lower() for t in cfg.get("buyer_tags", [])}
    exclude_tags = {t.lower() for t in cfg.get("exclude_tags", [])}

    users = {u["id"]: (u.get("name") or f"{u.get('firstName', '')} {u.get('lastName', '')}").strip()
             for u in raw.get("users", []) if u.get("id")}
    stages = {s["id"]: s["name"] for p in raw.get("pipelines", []) for s in p.get("stages", [])}
    fields = {f["id"]: f["name"] for f in raw.get("fields", [])}
    contacts = {c["id"]: c for c in raw.get("contacts", [])}

    cands = setter_candidates(raw, cal_ids)
    auto = setter_source is None
    if auto:   # nothing chosen yet: take the best-filled option if it covers most calls
        setter_source = cands[0]["source"] if cands and cands[0]["coverage"] >= 0.5 else "none"
    setter_of = make_setter_of(setter_source, users, contacts)
    chosen = next((c for c in cands if c["source"] == setter_source), None)

    ev = [e for e in raw["events"] if not cal_ids or e.get("calendarId") in cal_ids]
    for e in ev:
        e["_start"] = ts(e.get("startTime"))
        booked = (booked_override or {}).get(e.get("id")) or e.get("dateAdded")
        e["_booked"] = ts(booked)
        e["_status"] = status_of(e)

    past = [e for e in ev if e["_start"] and since <= e["_start"] <= now]
    by_contact = defaultdict(list)
    for e in ev:
        by_contact[e.get("contactId")].append(e)

    def closer_name(uid: str | None) -> str:
        if not uid:
            return "Unassigned"
        return users.get(uid) or f"Closer {uid[:5]}"

    def won_deals(c: dict) -> list[dict]:
        return [o for o in (c.get("opportunities") or []) if (o.get("status") or "").lower() == "won"]

    # --- breakdowns over every past call that was held or no-showed
    outcome = [e for e in past if e["_status"] in HELD | NOSHOW]
    ns = Counter(); held = Counter()
    by = {k: (Counter(), Counter()) for k in ("setter", "source", "gap", "daypart", "weekday")}
    for e in outcome:
        is_ns = e["_status"] in NOSHOW
        c = contacts.get(e.get("contactId"), {})
        local = e["_start"].astimezone(tz)
        keys = {
            "setter": setter_of(e) or "No setter recorded",
            "source": (c.get("source") or "").strip() or "Unknown",
            "gap": gap_bucket((e["_start"] - e["_booked"]).total_seconds() / 86400) if e["_booked"] else "Unknown",
            "daypart": daypart(local.hour),
            "weekday": WEEKDAYS[local.weekday()],
        }
        for k, v in keys.items():
            (by[k][0] if is_ns else by[k][1])[v] += 1
        (ns if is_ns else held)["all"] += 1
    total_calls = ns["all"] + held["all"]
    overall = ns["all"] / total_calls if total_calls else 0.0
    breakdowns = {
        "setter": rate_rows(*by["setter"]) if setter_source != "none" else [],
        "source": rate_rows(*by["source"]),
        "gap": rate_rows(*by["gap"], order=[b[0] for b in GAP_BUCKETS] + (["Unknown"] if by["gap"][0]["Unknown"] + by["gap"][1]["Unknown"] else [])),
        "daypart": rate_rows(*by["daypart"], order=[d[0] for d in DAYPARTS]),
        "weekday": rate_rows(*by["weekday"], order=WEEKDAYS),
    }
    labels = {"setter": "Leads set by", "source": "Leads from", "gap": "Calls booked", "daypart": "Calls in the",
              "weekday": "Calls on"}
    insights = []
    for k in ("gap", "setter", "source", "daypart"):
        s = worst_insight(breakdowns[k], labels[k], overall)
        if s:
            insights.append({"dimension": k, "text": s})

    # --- price and close rate from their own data
    showed_people = {e.get("contactId") for e in outcome if e["_status"] in HELD}
    buyers = {cid for cid, c in contacts.items() if won_deals(c) or ({t.lower() for t in c.get("tags", [])} & buyer_tags)}
    won_values = [o.get("monetaryValue") for c in contacts.values() for o in won_deals(c) if o.get("monetaryValue")]
    derived_price = round(statistics.median(won_values)) if won_values else None
    derived_close = round(len(showed_people & buyers) / len(showed_people), 4) if showed_people else None
    price_used = price if price is not None else (cfg.get("price") if cfg.get("price") is not None else derived_price)
    close_used = close_rate if close_rate is not None else (cfg.get("close_rate") if cfg.get("close_rate") is not None else derived_close)
    price_src = "given" if price is not None or cfg.get("price") is not None else ("from won deals" if derived_price else None)
    close_src = "given" if close_rate is not None or cfg.get("close_rate") is not None else ("from showed calls" if derived_close is not None else None)

    # --- the people: one row per person who no-showed in the window
    funnel = Counter()
    people, excluded = [], defaultdict(list)
    unmarked = [e for e in past if e["_status"] in UNMARKED]
    board_mismatch = Counter()
    ns_events = sorted((e for e in past if e["_status"] in NOSHOW), key=lambda e: e["_start"], reverse=True)
    funnel["no_show_calls"] = len(ns_events)
    done = set()
    for e in ns_events:
        cid = e.get("contactId")
        if cid in done:
            continue
        done.add(cid)
        c = contacts.get(cid, {})
        later = [x for x in by_contact[cid] if x["_start"] and x["_start"] > e["_start"] and x["_status"] in UPCOMING_OK]
        tags = {t.lower() for t in c.get("tags", [])}
        if later:
            reason = "rebooked"
        elif cid in buyers:
            reason = "bought"
        elif not c:
            reason = "contact_missing"
        elif sms_opted_out(c):
            reason = "opted_out"
        elif not c.get("phone"):
            reason = "no_phone"
        elif tags & exclude_tags:
            reason = "excluded_tag"
        else:
            reason = None
        open_deals = [o for o in (c.get("opportunities") or []) if (o.get("status") or "").lower() == "open"]
        stage = stages.get(open_deals[0].get("pipelineStageId"), "") if open_deals else ""
        # only people who are still no-shows: a rebooked lead in "Follow Up" is filed correctly
        if (not reason and open_deals and "no show" not in stage.lower()
                and "no-show" not in stage.lower() and "noshow" not in stage.lower()):
            board_mismatch[stage or "Unknown stage"] += 1
        row = {
            "contact_id": cid,
            "first_name": c.get("firstName") or "", "last_name": c.get("lastName") or "",
            "phone": c.get("phone") or "", "timezone": c.get("timezone") or tzname,
            "source": (c.get("source") or "").strip() or "Unknown",
            "setter": setter_of(e) or "", "closer": closer_name(e.get("assignedUserId")),
            "closer_id": e.get("assignedUserId"),
            "no_show_at": e["_start"].isoformat(), "appointment_id": e.get("id"),
            "days_since": (now - e["_start"]).days,
            "booked_gap_days": (round((e["_start"] - e["_booked"]).total_seconds() / 86400, 1)
                                if e["_booked"] and e["_booked"] <= e["_start"] else None),
            "deal_stage": stage,
            "form_answers": {fields.get(f.get("id"), f.get("id")): f.get("value")
                             for f in (c.get("customFields") or []) if f.get("value") not in (None, "", [])},
        }
        if reason:
            row["excluded_because"] = reason
            excluded[reason].append(row)
        else:
            people.append(row)
    funnel["no_show_people"] = len(done)
    for k in ("rebooked", "bought", "opted_out", "no_phone", "excluded_tag", "contact_missing"):
        funnel[k] = len(excluded[k])
    funnel["recoverable"] = len(people)

    money = None
    if price_used and close_used is not None:
        pipeline = len(people) * close_used * price_used
        money = {"recoverable": len(people), "recovery_rate": recovery_rate, "close_rate": close_used,
                 "price": price_used, "pipeline_value": round(pipeline),
                 "estimate": round(pipeline * recovery_rate),
                 "price_source": price_src, "close_rate_source": close_src}

    return {
        "generated_at": now.isoformat(), "client": cfg.get("name"), "timezone": tzname,
        "window": {"from": since.date().isoformat(), "to": now.date().isoformat(), "days": days},
        "calendars": [c["name"] for c in cfg.get("calendars", [])],
        "totals": {"calls_with_outcome": total_calls, "no_show_calls": ns["all"], "showed_calls": held["all"],
                   "no_show_rate": round(overall, 4), "unmarked_past_calls": len(unmarked),
                   "cancelled": sum(1 for e in past if e["_status"] == "cancelled")},
        "funnel": dict(funnel),
        "money": money,
        "derived": {"price": derived_price, "close_rate": derived_close, "won_deals": len(won_values),
                    "showed_people": len(showed_people)},
        "needs": [n for n, v in (("price", price_used), ("close_rate", close_used)) if v is None],
        "setter": {"source": setter_source, "label": chosen["label"] if chosen else "No setters",
                   "coverage": chosen["coverage"] if chosen else None, "auto_picked": auto, "candidates": cands},
        "breakdowns": breakdowns, "insights": insights,
        "board_mismatch": [{"stage": k, "people": v} for k, v in board_mismatch.most_common()],
        "recoverable": people,
        "excluded": {k: v for k, v in excluded.items()},
    }


# ---------------------------------------------------------------- CLI

def cmd_ids(files: list[str]) -> None:
    raw = collect(files)
    ids = sorted({e.get("contactId") for e in raw["events"] if e.get("contactId")})
    for i in range(0, len(ids), 100):
        print(json.dumps(ids[i:i + 100]))
    print(f"# {len(ids)} contacts in {(len(ids) + 99) // 100} batch(es)", file=sys.stderr)


def cmd_paths() -> None:
    """Where settings and reports live: the same for every chat, in any folder."""
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"config": str(DEFAULT_CONFIG), "config_exists": DEFAULT_CONFIG.exists(),
                      "reports": str(REPORTS_DIR)}, indent=1))


def cmd_newrun(a) -> None:
    cfg_all = json.loads(Path(a.config).read_text())
    cid = a.client or cfg_all.get("default_client")
    name = cfg_all["clients"][cid].get("name") or cid
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")[:40] or "client"
    run = REPORTS_DIR / f"{slug}-{datetime.now().strftime('%Y-%m-%d')}"
    (run / "raw").mkdir(parents=True, exist_ok=True)
    print(run)


SAVABLE = {"setter_source": str, "price": float, "close_rate": float}


def cmd_save(a) -> None:
    """Save one client setting, so the skill never hand-edits the config."""
    path = Path(a.config)
    cfg_all = json.loads(path.read_text())
    cid = a.client or cfg_all.get("default_client")
    if a.key not in SAVABLE:
        raise SystemExit(f"can only save {', '.join(SAVABLE)}")
    value = None if a.value in ("null", "") else SAVABLE[a.key](a.value.rstrip("%"))
    if a.key == "close_rate" and value is not None and value > 1:
        value = value / 100          # "25" or "25%" means 0.25
    cfg_all["clients"][cid][a.key] = value
    path.write_text(json.dumps(cfg_all, indent=2))
    print(f"Saved {a.key} = {value} for {cfg_all['clients'][cid].get('name', cid)}")


def cmd_window() -> None:
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    print(json.dumps({"startTime": str(now - 90 * 86400000), "endTime": str(now + 60 * 86400000)}))


def cmd_setters(a) -> None:
    cfg_all = json.loads(Path(a.config).read_text())
    cfg = cfg_all["clients"][a.client or cfg_all.get("default_client")]
    raw = collect(a.files)
    cands = setter_candidates(raw, {c["id"] for c in cfg.get("calendars", [])})
    print(json.dumps(cands, indent=1))


def cmd_run(a) -> None:
    cfg_all = json.loads(Path(a.config).read_text())
    cid = a.client or cfg_all.get("default_client")
    cfg = cfg_all["clients"][cid]
    override = None
    if a.booked_at_override:
        m = json.loads(Path(a.booked_at_override).read_text())
        override = {x["id"]: x["booked_at"] for x in m.get("appointments", []) if x.get("id")}
    raw = collect(a.files)
    now = datetime.now(timezone.utc)
    result = run_audit(raw, cfg, now, days=a.days, recovery_rate=a.recovery_rate,
                       price=a.price, close_rate=a.close_rate, booked_override=override,
                       setter_source=a.setter_source or cfg.get("setter_source"))
    result["client_id"] = cid
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    f, m = result["funnel"], result["money"]
    print(f"Calls with an outcome: {result['totals']['calls_with_outcome']} · no-show rate "
          f"{round(result['totals']['no_show_rate'] * 100)}%")
    print(f"No-show people: {f['no_show_people']} → recoverable {f['recoverable']} "
          f"(rebooked {f['rebooked']}, bought {f['bought']}, opted out {f['opted_out']}, no phone {f['no_phone']})")
    if m:
        print(f"Pipeline: {m['recoverable']} × {m['close_rate']:.0%} close × ${m['price']:,} = ${m['pipeline_value']:,}"
              f" · win back {m['recovery_rate']:.0%} ≈ ${m['estimate']:,}")
    st = result["setter"]
    print(f"Setters: {st['label']}" + (f" ({st['coverage']:.0%} of calls)" if st["coverage"] is not None else "")
          + (" [auto-picked: confirm with the user]" if st["auto_picked"] else ""))
    if result["needs"]:
        print("NEEDS: " + ", ".join(result["needs"]) + " (ask the user, then re-run with --price / --close-rate)")
    print(f"Wrote {out / 'audit.json'}")


def selftest() -> None:
    now = datetime(2026, 10, 17, 18, tzinfo=timezone.utc)
    iso = lambda d, h=15: (now - timedelta(days=d)).replace(hour=h).isoformat()
    ev = [
        {"id": "a1", "contactId": "c1", "calendarId": "K", "appointmentStatus": "noshow", "startTime": iso(10), "dateAdded": iso(20), "assignedUserId": "u1"},
        {"id": "a2", "contactId": "c2", "calendarId": "K", "appointmentStatus": "noshow", "startTime": iso(5), "dateAdded": iso(5, 9), "assignedUserId": "u1"},
        {"id": "a3", "contactId": "c2", "calendarId": "K", "appointmentStatus": "confirmed", "startTime": (now + timedelta(days=2)).isoformat(), "dateAdded": iso(1)},
        {"id": "a4", "contactId": "c3", "calendarId": "K", "appointmentStatus": "showed", "startTime": iso(8), "dateAdded": iso(9), "assignedUserId": "u2"},
        {"id": "a5", "contactId": "c4", "calendarId": "K", "appointmentStatus": "noshow", "startTime": iso(3), "dateAdded": iso(4), "assignedUserId": "u2"},
        {"id": "a6", "contactId": "c5", "calendarId": "K", "appointmentStatus": "noshow", "startTime": iso(2), "dateAdded": iso(3)},
        {"id": "a7", "contactId": "c6", "calendarId": "OTHER", "appointmentStatus": "noshow", "startTime": iso(2), "dateAdded": iso(3)},
        {"id": "a8", "contactId": "c1", "calendarId": "K", "appointmentStatus": "noshow", "startTime": iso(30), "dateAdded": iso(31)},
    ]
    contacts = [
        {"id": "c1", "firstName": "A", "phone": "+15550000001", "source": "IG DM", "assignedTo": "s1"},
        {"id": "c2", "firstName": "B", "phone": "+15550000002"},
        {"id": "c3", "firstName": "C", "phone": "+15550000003", "opportunities": [{"status": "won", "monetaryValue": 3000}]},
        {"id": "c4", "firstName": "D", "phone": "+15550000004", "dndSettings": {"sms": {"status": "active"}}},
        {"id": "c5", "firstName": "E"},
    ]
    raw = {"events": ev, "contacts": contacts, "users": [{"id": "u1", "name": "Marcus"}, {"id": "s1", "name": "Jake"}],
           "pipelines": [], "fields": [{"id": "f1", "name": "Setter"}]}
    cfg = {"name": "T", "timezone": "America/New_York", "calendars": [{"id": "K", "name": "Strategy"}]}
    r = run_audit(raw, cfg, now)
    f = r["funnel"]
    assert f["no_show_calls"] == 5, f              # a7 is on another calendar
    assert f["no_show_people"] == 4, f             # c1 counted once
    assert f["rebooked"] == 1 and f["opted_out"] == 1 and f["no_phone"] == 1, f
    assert f["recoverable"] == 1 and r["recoverable"][0]["contact_id"] == "c1", r["recoverable"]
    assert r["recoverable"][0]["no_show_at"].startswith((now - timedelta(days=10)).date().isoformat())
    assert r["derived"]["price"] == 3000 and r["derived"]["close_rate"] == 1.0, r["derived"]
    assert r["money"]["pipeline_value"] == 3000 and r["money"]["estimate"] == 300, r["money"]
    assert r["totals"]["no_show_rate"] == round(5 / 6, 4), r["totals"]
    assert r["recoverable"][0]["closer"] == "Marcus"
    assert r["setter"]["source"] == "none" and r["setter"]["auto_picked"], r["setter"]   # 2 of 7 calls < 50%
    assert r["breakdowns"]["setter"] == [] and r["recoverable"][0]["setter"] == ""
    r2 = run_audit(raw, cfg, now, setter_source="contact_owner")
    assert r2["recoverable"][0]["setter"] == "Jake", r2["recoverable"][0]
    assert {x["label"] for x in r2["breakdowns"]["setter"]} == {"Jake", "No setter recorded"}, r2["breakdowns"]["setter"]
    assert any(c["source"] == "custom_field:f1" for c in r2["setter"]["candidates"])
    print("selftest ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ids"); p.add_argument("files", nargs="+")
    p = sub.add_parser("save"); p.add_argument("--config", default=str(DEFAULT_CONFIG)); p.add_argument("--client")
    p.add_argument("key"); p.add_argument("value")
    sub.add_parser("window")
    sub.add_parser("paths")
    p = sub.add_parser("newrun"); p.add_argument("--config", default=str(DEFAULT_CONFIG)); p.add_argument("--client")
    p = sub.add_parser("setters"); p.add_argument("--config", default=str(DEFAULT_CONFIG)); p.add_argument("--client")
    p.add_argument("files", nargs="+")
    p = sub.add_parser("run")
    p.add_argument("--config", default=str(DEFAULT_CONFIG)); p.add_argument("--client")
    p.add_argument("--out", required=True); p.add_argument("--days", type=int, default=90)
    p.add_argument("--recovery-rate", type=float, default=DEFAULT_RECOVERY)
    p.add_argument("--price", type=float); p.add_argument("--close-rate", type=float)
    p.add_argument("--booked-at-override"); p.add_argument("--setter-source")
    p.add_argument("files", nargs="+")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "ids":
        cmd_ids(a.files)
    elif a.cmd == "save":
        cmd_save(a)
    elif a.cmd == "window":
        cmd_window()
    elif a.cmd == "paths":
        cmd_paths()
    elif a.cmd == "newrun":
        cmd_newrun(a)
    elif a.cmd == "setters":
        cmd_setters(a)
    elif a.cmd == "run":
        cmd_run(a)
    else:
        selftest()


if __name__ == "__main__":
    main()
