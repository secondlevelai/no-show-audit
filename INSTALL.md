# No-Show Recovery: Guided Installer

> A free Claude plugin from Second Level AI. Finds every no-show in GoHighLevel, shows what they're worth at your own price and close rate, where they come from (setter, lead source, booking gap, time of day), and who you can still win back. Read-only.

<!-- MODULE METADATA
module: no-show-recovery
version: v0.5.1
status: RELEASED
requires: [claude-paid-plan, gohighlevel]
category: Sales
complexity: simple
api_keys: 0
setup_time: 3-5 minutes
-->

---

## FOR CLAUDE

You are helping someone install and set up No-Show Recovery. They pasted this repo's link (or this file) and asked you to set it up. Follow these rules:

**Behavior:**
- Assume they have never installed a Claude plugin or connected an app before.
- Explain each step in plain English **before** doing it. One step at a time, and wait for "done" before the next.
- **Do every technical part yourself.** Their only jobs: sign in to GoHighLevel in the browser, and answer questions. **Never ask them to run a command, open a terminal, or use `/mcp`.** (`/mcp` doesn't work in the Claude desktop app.)
- Use exact names in **bold**: **Allow**, **Customize**, **Plugins**, **Connectors**.
- Celebrate small wins in one line.
- If something fails, don't dump error output. Explain it simply and fix it.
- Never skip a **[VERIFY]**.

**Where they're running Claude:**
- **You can run shell commands** → Claude Code: the Claude **desktop app's Code tab**, **VS Code**, **Cursor**, or a **terminal**. Use **Path A**.
- **You can't run commands** → the **Claude app or claude.ai chat**. Use **Path B**.

---

## OVERVIEW

Read this to the user before starting:

We're setting up **No-Show Recovery**. When we're done, you'll say "audit my no-shows" and get an interactive report in your browser with:

- **What your no-show list is worth:** the people who no-showed and can still be won back, at your own close rate and price (worked out from your won deals).
- **Where no-shows come from:** by setter, lead source, how far out the call was booked, and time of day, each against your average.
- **Who's really left:** anyone who already rebooked, bought, opted out of texts or has no phone number is taken out.
- **Pipeline check:** no-shows still sitting in the wrong stage on your board.

**Setup time:** 3–5 minutes.
**Cost:** Free. It runs on your Claude plan. No API keys.
**How it works:** GoHighLevel's official connector lets Claude read your calendar, contacts and deals with your own sign-in. A script does all the counting, and the report is built on your computer. It only reads: nothing is sent, changed or stored anywhere else.

---

## PREREQUISITES

- **A paid Claude plan** (Pro, Max, Team or Enterprise).
- **GoHighLevel**, with sales calls booked on a calendar.
- **Path A:** `claude --version` works.

Don't stop to ask about these. Mention them only if something fails.

---

## INSTALL (Path A: Claude Code: desktop app Code tab, VS Code, Cursor, terminal)

### Step 1: Install

Say "Installing No-Show Recovery…" and run this yourself:

```bash
if claude plugin list 2>/dev/null | grep -q "no-show-recovery"; then
  claude plugin marketplace update secondlevelai-no-show-recovery && claude plugin update no-show-recovery@secondlevelai-no-show-recovery
else
  claude plugin marketplace add secondlevelai/no-show-recovery && claude plugin install no-show-recovery@secondlevelai-no-show-recovery
fi
```

[VERIFY] `claude plugin list` shows `no-show-recovery@secondlevelai-no-show-recovery` enabled → "**No-Show Recovery is installed ✅**"

### Step 2: Connect GoHighLevel (you open the sign-in)

If `claude mcp list 2>&1 | grep "no-show-recovery:highlevel"` already says **Connected**, skip to Step 3.

Otherwise say one line, "Opening the GoHighLevel sign-in in your browser now…", and start the sign-in in the background. Pick the command for their system (`uname` if unsure):

- **macOS:** `(script -q /tmp/nsr-login.log claude mcp login plugin:no-show-recovery:highlevel </dev/null >/dev/null 2>&1 &)`
- **Linux:** `(script -qc "claude mcp login plugin:no-show-recovery:highlevel" /tmp/nsr-login.log </dev/null >/dev/null 2>&1 &)`
- **Windows:** `cmd.exe /c start "" /min cmd /c "claude mcp login plugin:no-show-recovery:highlevel"`

Never run `claude mcp login` in the foreground: it needs a terminal and fails with "stdin isn't a terminal". The wrappers above give it one.

Then say exactly this:

> "A **GoHighLevel** tab just opened in your browser. In it:
>
> 1. Sign in.
> 2. **Tick every sub-account (client)** you want me to look at.
> 3. Click **Allow**.
>
> **About the long permissions list:** HighLevel shows every permission it has, because that's how Claude connects to HighLevel for any tool. This plugin only **reads** your calendar, contacts and deals. It never sends, edits or deletes anything, and you can disconnect it any time.
>
> Then come back here and type **done**. (Do it now, because the sign-in page expires after a few minutes.)"

**No tab opened?** On macOS/Linux, read `/tmp/nsr-login.log`, find the `https://services.leadconnectorhq.com/mcp/anthropic/authorize?…` link and give it to them as a clickable link. On Windows, the link is in the small command window that opened.

[VERIFY] When they say done:

```bash
claude mcp list 2>&1 | grep "no-show-recovery:highlevel"
```

- **Connected** → "**GoHighLevel's connected.** That was the hard part." → Step 3.
- **Needs authentication** → the page probably expired. "That sign-in timed out. Opening a fresh one…" Run the sign-in command again and repeat the message. Never ask them to run anything.

### Step 3: One next step

This chat started before the plugin was installed, so it can't use the plugin's tools yet. End with exactly this, and nothing after it:

> "**You're all set ✅**
>
> **Last step:** open a **new chat in this same folder** and type **"set up No-Show Recovery"**.
>
> I'll ask which client and which calendar your sales calls are on, then run your first audit: a report in your browser showing what your no-shows are worth, where they come from, and who you can still win back."

The **setup** skill takes over in the new chat. It finds GoHighLevel already connected and goes straight to picking the client and calendars.

---

## INSTALL (Path B: Claude app or claude.ai chat)

You can't install from a chat message. Give the clicks:

1. **Customize** → **Plugins** → **Add** → **Add marketplace** → paste **`secondlevelai/no-show-recovery`** → install **No-Show Recovery**.
2. Open its **Connectors** tab → **Connect** on **HighLevel** → sign in, tick your sub-accounts → **Allow**. On Claude Team or Enterprise, an Owner may need to allow the connector first under **Customize → Connectors**.
3. Open the Claude **desktop app's Code tab** (the report needs Claude to run code), start a new chat and say **"set up No-Show Recovery."**

---

## AFTER SETUP

- **Any time:** "Audit my no-shows." A fresh 90-day report each time, saved in `nsr-runs/`.
- **Another client:** "Audit {client}'s no-shows" or "add a client". It asks which calendar, then runs.
- **Change the numbers:** "Use $5k as the price", "our close rate is 25%", "show me Jake's no-shows".

---

> Free tool by Second Level AI · MIT license
