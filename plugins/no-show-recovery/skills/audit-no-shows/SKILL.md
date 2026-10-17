---
name: audit-no-shows
description: Audit a GoHighLevel account's no-shows, such as "audit my no-shows", "how many no-shows do we have", "what are our no-shows worth", "why are people not showing up", "no-show report", "audit {client}'s no-shows" or "show rate". Reads the last 90 days of sales-call appointments, works out who can still be won back and what that pipeline is worth at the client's own price and close rate, breaks no-shows down by setter, lead source, booking gap and time of day, and opens an interactive report. Read-only.
---

# Audit no-shows

Pull the client's sales-call appointments and the people behind them from HighLevel, let `scripts/audit.py` do **all** of the counting and math, and open the report from `scripts/build_report.py`. **Read-only: never create, edit or send anything in HighLevel from this skill.**

The reader is a growth operator or offer owner. Keep their attention cost low: no preamble, one short progress line per step, and ask only the questions below.

Before the first HighLevel call, read `references/ghl.md`. It has the exact operations, parameters and field quirks.

## 0. Rules that matter most

- **You never do arithmetic or count people.** Every number shown to the user comes from `audit.py` output or `audit.json`. If you need a number that isn't there, say so instead of working it out.
- **You never read raw HighLevel data.** Big results are saved to a file by Claude Code ("Output has been saved to …"). Pass that path to the script, and don't open it.
- **Appointments or contacts that come back inline** (small accounts): save them with the Write tool, exactly as returned, to `nsr-runs/<run>/raw/<name>.json`, then pass that path. Don't edit, summarize or filter them.
- **The three small lookups** (step 2.4) usually come back inline. Save only what the script needs, in this exact shape (see step 2.4).
- **Save files only with the Write tool**, never with shell tricks (`cat > file <<EOF`, `echo … >`). Claude Code's safety check blocks those and the user gets an extra prompt.
- **Write every path out in full in shell commands.** Don't use shell variables (`$T`, `$RUN`): Claude Code's safety check blocks commands it can't read.
- If a HighLevel call errors, retry once. If it fails again, tell the user in one plain sentence what didn't work and stop.

## 1. Config and client

1. Read `no-show-recovery.json` in the working folder. **Missing** → say "Let's connect GoHighLevel first, it takes about a minute," and follow the **setup** skill, then come back here.
2. Pick the client:
   - The user named one ("audit Sarah's no-shows") → match it against `clients[*].name`, loosely. No match → run setup Steps 2–4 for it, then continue.
   - Otherwise, one client → use it. Several → ask with AskUserQuestion, header "Client", default first.
3. Check the HighLevel tools respond (`list_locations`). If they don't, follow the setup skill's Step 1 to reconnect.
4. Make the run folder: `nsr-runs/<client-slug>-<YYYY-MM-DD>/raw/`. Keep its path as `RUN`.

Say one line: "Auditing **{client}**: last 90 days of {calendar names}. Read-only, nothing gets sent."

## 2. Pull the data (about 5–10 HighLevel calls)

Use `execute_operation` with the client's `locationId` every time. After each call, if Claude Code saved the result to a file, note the path. If it came back inline, write it to `RUN/raw/` as above.

1. **Appointments, one call per calendar in the config:** `get-calendar-events` with `calendarId`, `startTime` = now − 90 days and `endTime` = now + 60 days, both in **epoch milliseconds as strings**. The future window is how the audit knows who already rebooked. Get both values with `python3 ${CLAUDE_SKILL_DIR}/scripts/audit.py window`.
2. **Which contacts to fetch:** run
   `python3 ${CLAUDE_SKILL_DIR}/scripts/audit.py ids <every appointments file>`
   It prints one JSON array of up to 100 contact IDs per line.
3. **Contacts, one call per line from step 2:** `search-contacts-advanced` with body
   `{"pageLimit": 100, "filters": [{"field": "id", "operator": "eq", "value": <that array>}]}`.
   Each person comes back with their deals attached, so no separate deal lookup is needed.
4. **Lookups (small, usually inline):** `get-pipelines`, `get-custom-fields` with `{"model": "contact"}`, and `search-users` with `{"companyId": <client.company_id>}`. If one comes back inline, write a trimmed copy to `RUN/raw/` keeping only IDs and names:
   - `pipelines.json`: `{"operationId": "get-pipelines", "data": {"pipelines": [{"id": "…", "name": "…", "stages": [{"id": "…", "name": "…"}]}]}}`
   - `custom-fields.json`: `{"operationId": "get-custom-fields", "data": {"customFields": [{"id": "…", "name": "…"}]}}`
   - `users.json`: `{"operationId": "search-users", "data": {"users": [{"id": "…", "name": "…"}]}}`
   If a lookup fails or comes back empty, skip it. The audit still runs, just with IDs in place of names.

Progress line after pulling, from the `ids` output: "Pulled appointments for {N} people across {calendars}. Crunching the numbers…"

## 3. Run the audit

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/audit.py run --config no-show-recovery.json --client <locationId> --out RUN <every file from step 2>
```

It prints a short summary and writes `RUN/audit.json`.

**If it prints `NEEDS: price` or `NEEDS: close_rate`** (no won deals to learn from), ask once with AskUserQuestion:
- header "Price": "What's the offer's price?" Options: **$2,000**, **$3,000**, **$5,000**, **$10,000** (they type others in "Other").
- header "Close rate": "Roughly what share of people who show up end up buying?" Options: **15%**, **20%**, **30%**, **Not sure (use 20%)**.

Save each answer with `python3 ${CLAUDE_SKILL_DIR}/scripts/audit.py save --config no-show-recovery.json --client <locationId> price 3000` (or `close_rate 20`), then re-run step 3. The report will say these numbers were given, not derived.

**Setters (first audit for a client only):** the summary prints a `Setters:` line. If it ends with `[auto-picked: confirm with the user]`, the client has no `setter_source` saved yet. Read `setter.candidates` from `RUN/audit.json` and ask once with AskUserQuestion, header "Setters":

"Where do you record who set each call? (I'll compare no-shows by setter, since they're the ones confirming and prepping leads.)"

Options:
- Every candidate with coverage of 20% or more, best first, labelled with its `label` and coverage. Example: **Contact owner (who the contact is assigned to)**, description "filled in on 100% of booked calls". Add "(Recommended)" to the one the script picked.
- **We don't use setters**, description "Leads book themselves. Skip the setter breakdown."

Save the answer with `python3 ${CLAUDE_SKILL_DIR}/scripts/audit.py save --config no-show-recovery.json --client <locationId> setter_source <source>`, using the candidate's `source` value or `none`. If it differs from what was auto-picked, re-run step 3 so the report uses it. If no candidate has 20% coverage, don't ask: save `none` the same way and say in one line, "I couldn't find setters recorded on these calls, so the report skips the setter breakdown."

## 4. Build and open the report

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_report.py RUN/audit.json --open
```

## 5. Tell them what it found (short)

Read `RUN/audit.json` (the summary fields, not the `recoverable` list) and reply in about 6 lines. Skip any line whose condition isn't met. Don't report that something is zero:

1. The headline: "**${pipeline_value}** of pipeline is sitting in your no-show list: **{recoverable}** people you can still win back (at your {close_rate} close rate and ${price} price)."
2. The `insights` sentences as bullets, copied word for word.
3. If `board_mismatch` isn't empty: "{n} no-shows are still sitting in **{stage}** on your pipeline."
4. Only if `totals.unmarked_past_calls` is above 0: "{n} past calls were never marked showed or no-show, so they're not in these numbers."
5. "The report's open in your browser."

If `money` is null, lead with the people count instead.

**Zero no-shows in 90 days:** check `totals.unmarked_past_calls` first. If it's high, the team isn't marking appointments, so say: "I found {n} past calls that were never marked showed or no-show. Until closers mark them, I can't tell who no-showed. In HighLevel, open each past appointment and set its status." Otherwise: "No no-shows in the last 90 days. Nice."

## Follow-ups

- **Never edit `no-show-recovery.json` by hand or with inline code.** Use `audit.py save`. It's one plain command the user can approve once.
- "Change the recovery rate to 15%" → re-run step 3 with `--recovery-rate 0.15` and rebuild the report.
- "Use $5k as the price" / "our close rate is 25%" → `audit.py save … price 5000` / `close_rate 25`, re-run step 3 and rebuild.
- "Show me Jake's no-shows" → answer from `audit.json` `recoverable` filtered by setter, as a short list (name, missed date, source). The report has the same filter.
- "Our setters are in the {X} field" / "we don't use setters" → `audit.py save … setter_source <source or none>` (sources are in `setter.candidates`), re-run step 3 and rebuild.

<sub>Free tool by Second Level AI</sub>
