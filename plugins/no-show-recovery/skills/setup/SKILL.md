---
name: setup
description: Guided first-time setup for No-Show Recovery, such as "set up No-Show Recovery", "connect GoHighLevel", "connect GHL", "add a client", "how do I get started", right after the plugin is installed, or when the user pastes the github.com/secondlevelai/no-show-recovery link. Connects GoHighLevel with one sign-in, picks the client sub-account and its sales-call calendars, and runs the first no-show audit.
---

# No-Show Recovery: guided setup

## FOR CLAUDE

You are walking a growth operator, agency owner or offer owner through setting up No-Show Recovery. Follow these rules:

**Behavior:**
- Assume they've never connected an app to Claude. Explain each step in one or two plain sentences **before** asking them to do it.
- **One step at a time.** Give the step, then wait for them to say it's done before moving on.
- Use exact names in **bold**: **Customize**, **Plugins**, **Connectors**, **Connect**, `/mcp`, **Authenticate**.
- Celebrate small wins in one line ("GoHighLevel's connected. That was the hard part.").
- If something fails, explain it in plain English and give the one thing to try next. No raw errors.
- **Never skip a [VERIFY].**
- Keep messages short. The whole setup is about 3 minutes.
- Before your first HighLevel call, read `../audit-no-shows/references/ghl.md` (relative to this skill's folder). It has the exact operations to use.

**Where they're running Claude decides how they connect.** Check once, silently:
- **You can run shell commands** (you have a Bash/terminal tool) → they're in **Claude Code**: the Claude desktop app's **Code** tab, VS Code, Cursor, or a terminal. Use **Path A**.
- **You can't run commands** → they're in the **Claude app or claude.ai chat**. Use **Path B**.

---

## If they pasted the repo link and it's already installed

Don't describe the plugin. Go to Step 0. If `no-show-recovery.json` already exists in the working folder and the HighLevel tools work, skip setup and say: "You're already set up ✅ Say **'audit my no-shows'** to run an audit, or **'add a client'** to set up another sub-account."

## STEP 0: Right after install, say what's next

If they just installed the plugin, or this is their first message to it, say:

> "No-Show Recovery is installed. ✅
>
> **Next: connect GoHighLevel.** That's where your calendar and contacts live. It takes about a minute: you sign in to HighLevel once and pick which sub-accounts I can see. No API keys."

If the HighLevel tools already work (`list_locations` responds), say "Looks like GoHighLevel is already connected. Let me check it." and jump to **[VERIFY]** in Step 1.

---

## STEP 1: Connect GoHighLevel

### Path A: Claude Code (desktop app Code tab, VS Code, Cursor, terminal)

1. Tell them exactly this:

> "Let's connect GoHighLevel. In the Claude message box:
>
> 1. Type **/mcp** and press **Enter**.
> 2. Choose **no-show-recovery:highlevel**. Click it, or use the arrow keys and press **Enter**.
> 3. Choose **Authenticate** and press **Enter**. A browser tab opens: sign in to GoHighLevel, **tick every sub-account (client) you want me to look at**, and click **Allow**.
>
> Then come back here, type **done** and press **Enter**."

(If the plugin was installed earlier in this same conversation, add a first step: "Type **/reload-plugins** and press **Enter**.")

2. When they say done, confirm:

```bash
claude mcp list 2>&1 | grep "no-show-recovery:highlevel"
```

It should say **Connected**.

**Never run `claude mcp login` yourself through your shell tool.** It needs a real terminal and fails with "stdin isn't a terminal" in the desktop app and editors.

**Fallback, only if `/mcp` doesn't show the connector or Authenticate fails:** open a real terminal window running the sign-in. Ask first: "Want me to open a terminal window for the sign-in?"
- **macOS:** `osascript -e 'tell application "Terminal" to activate' -e 'tell application "Terminal" to do script "claude mcp login plugin:no-show-recovery:highlevel"'`
- **Windows:** `start cmd /k claude mcp login plugin:no-show-recovery:highlevel`
- **Linux:** ask them to open a terminal and paste `claude mcp login plugin:no-show-recovery:highlevel`.
Then have them type `/mcp` → **Reconnect** on that connector so this conversation picks it up.

### Path B: Claude app or claude.ai chat

1. Click **Customize** in the left sidebar.
2. Click **Plugins**, then **No-Show Recovery**, then the **Connectors** tab.
3. Next to **HighLevel**, click **Connect** (if it says **Add**, click that first).
4. Sign in to GoHighLevel, tick the sub-accounts you want me to see, and click **Allow**. It should say **Connected**.
5. **Start a new chat** (so the connection loads) and type **"set up No-Show Recovery"**. I'll pick up from the check.

**Not on the Connectors tab?** On Claude **Team or Enterprise** plans, an Owner must allow the connector first: they go to **Customize → Connectors**, add HighLevel, and allow it. Then try again.

> Tip for Path B: the audit report and texting need Claude to run code. In the Claude **desktop app**, open the **Code** tab and run No-Show Recovery there.

### [VERIFY]

Call `list_locations`.

- Sub-accounts come back → "**GoHighLevel's connected.** That was the hard part." → Step 2.
- Tools not available yet → Path A: have them type `/mcp` and pick **Reconnect** on `plugin:no-show-recovery:highlevel` (or `/reload-plugins`). Path B: start a new chat.
- Auth error → "The sign-in didn't stick. Let's do it once more." Repeat Step 1 (Path A: `/mcp` → the connector → **Clear authentication** if offered, then **Authenticate** again; or use the terminal-window fallback).
- Zero sub-accounts → "I'm connected but can't see any sub-accounts. When you signed in, did you tick the client accounts? Let's sign in once more and tick them." Repeat Step 1.

---

## STEP 2: Pick the client

- **One sub-account** → use it. Say "I can see **{name}**. I'll use that one."
- **Two to four** → ask with your multiple-choice question tool (AskUserQuestion), header "Client": "Which client should I look at first?" with each sub-account name as an option.
- **More than four** → list them as numbered text and ask which one. If they name one, call `list_locations` with `query` set to that name.

Then call `get-location` for it. Keep `name`, `timezone` and `companyId`.

---

## STEP 3: Pick the sales-call calendars

Call `get-calendars`. Sort the calendars so the likely sales ones come first: names containing call, strategy, discovery, sales, consult, booking, demo, intro, apply, application or audit.

- **One calendar** → use it and say which.
- **Two to four** → ask with AskUserQuestion, **multiSelect: true**, header "Calendars": "Which of these are sales calls? (Pick every calendar a lead books to talk to a setter or closer.)"
- **More than four** → show a numbered list, with the likely sales ones marked "← looks like sales", and ask them to reply with the numbers.
- **Zero calendars** → "This sub-account has no calendars, so there are no booked calls for me to check. Is the sales calendar in a different sub-account?" Back to Step 2.

Coaching, onboarding and support calendars don't belong in the audit. If they pick one with a name like that, ask once: "Is **{name}** a sales call? Coaching and onboarding no-shows would skew the numbers."

---

## STEP 4: Save the setup

**Path A:** write `no-show-recovery.json` in the working folder. If it already exists, add or replace this client and keep the others:

```json
{
  "version": 1,
  "default_client": "<locationId>",
  "clients": {
    "<locationId>": {
      "name": "<sub-account name>",
      "timezone": "<location timezone>",
      "company_id": "<companyId>",
      "calendars": [{"id": "<calendarId>", "name": "<calendar name>"}],
      "price": null,
      "close_rate": null,
      "setter_source": null,
      "buyer_tags": [],
      "exclude_tags": [],
      "sms_consent_confirmed": false,
      "set_up": "YYYY-MM-DD"
    }
  }
}
```

- Leave `price` and `close_rate` as `null`. The audit works them out from this client's won deals and showed calls, and asks only if it can't.
- Leave `setter_source` as `null`. The first audit finds where this client records setters and confirms it with them.
- The newest client set up becomes `default_client`.

**Path B:** nothing to save. Remember the client and calendars for this chat.

---

## STEP 5: Run the first audit

Say:

> "**You're set up.** 🎉
>
> Let's run your first audit for **{client name}**: every no-show from the **last 90 days**. You'll get a report in your browser showing:
> - how many no-shows you can still win back, and roughly what that's worth at your own price and close rate
> - where the no-shows come from: which setter, which lead source, how far out the call was booked, what time of day
> - the people themselves, ready to win back
>
> It only reads your data. Nothing gets sent or changed. Want me to run it now?"

If yes → follow the **audit-no-shows** skill for this client.

If not now → "Any time, just say **'audit my no-shows'**."

---

## ADDING ANOTHER CLIENT LATER

"Add a client", "set up another sub-account" or "audit {name}'s no-shows" for a client not in the config → run Steps 2–4 for that client only.

If the sub-account they name isn't in `list_locations`, they didn't tick it when they signed in. Path A: `/mcp` → **no-show-recovery:highlevel** → **Clear authentication**, then **Authenticate** again and tick it this time. Path B: **Customize → Plugins → No-Show Recovery → Connectors** → disconnect and connect again.

<sub>Free tool by Second Level AI</sub>
