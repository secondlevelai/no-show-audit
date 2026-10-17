# No-Show Audit

A free Claude plugin from Second Level AI for growth operators and offer owners on **GoHighLevel**.

Say **"audit my no-shows"** and get an interactive report of the last 90 days:

- **What your no-show list is worth:** everyone who no-showed and can still be won back, priced at your own close rate and offer price (worked out from your won deals).
- **Where no-shows come from:** by setter, lead source, how far out the call was booked, and time of day, each against your average.
- **Who's left:** people who already rebooked, bought, opted out of texts or have no phone are taken out, so the list is real.
- **Pipeline check:** no-shows still sitting in the wrong stage on your board.

It only reads your data. Nothing is sent, changed or stored on any server of ours. (HighLevel's sign-in page lists every permission it has, because Claude asks for all of them when it connects. The plugin itself only calls read operations.) It runs on your own Claude plan, with no API keys: you sign in to GoHighLevel once.

## Install

**Easiest:** open Claude Code (the Claude desktop app's **Code** tab, VS Code, Cursor or a terminal), paste this repo's link, and say **"set this up"**. Claude follows [INSTALL.md](INSTALL.md): it installs the plugin, opens the GoHighLevel sign-in in your browser, and gets you to your first audit. You never type a command.

**Or by hand:**

```bash
claude plugin marketplace add secondlevelai/no-show-audit
claude plugin install no-show-audit@secondlevelai-no-show-audit
```

Then open Claude Code in any folder and say **"set up No-Show Audit"**. It walks you through connecting GoHighLevel (about a minute) and runs your first audit.

**Needs:** a paid Claude plan and a GoHighLevel account with your sales calls on a calendar.

---

Free tool by Second Level AI
