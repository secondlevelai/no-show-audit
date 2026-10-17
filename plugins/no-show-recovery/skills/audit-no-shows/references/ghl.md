# HighLevel: how this plugin talks to it

Every skill in this plugin reads this file before calling HighLevel. It was written from live tests against a HighLevel account in October 2026. Use these exact operation IDs. Don't search for others unless one of these returns "operation not found".

## The connector

The plugin's MCP server is `highlevel` (in Claude Code it shows as `plugin:no-show-recovery:highlevel`). It exposes four tools, and together they reach HighLevel's whole public API:

| Tool | Use |
|---|---|
| `list_locations` | The sub-accounts (clients) this sign-in can use. Names and IDs only. |
| `search_operations` | Find an operation ID. Only needed if one below stops working. |
| `describe_operation` | Exact params for an operation. Only needed if one below errors on params. |
| `execute_operation` | Run an operation: `{operationId, locationId, params}`. |

**Always pass `locationId`** to `execute_operation`. A connection with one sub-account fills it in by itself. A connection with several requires it, and passing it is harmless either way.

**This plugin only reads.** Never call a write operation (`create-*`, `edit-*`, `update-*`, `delete-*`, `send-*`).

## Big results go to a file. Never read them.

One calendar's 90 days of appointments is about 170,000 characters (about 630 per appointment). Claude Code saves any MCP result that large to a file and returns a short message like:

> Error: result (168,491 characters …) exceeds maximum allowed tokens. Output has been saved to /…/tool-results/mcp-highlevel-execute_operation-1792262083563.txt

When that happens, **don't open or read the file.** Pass its path to the script the skill names. The scripts understand the raw response format.

If a result comes back inline (small accounts), save it to the run folder with the Write tool exactly as returned, then pass that path to the script. Don't summarize it, re-type parts of it or filter it first.

## Operations

| Need | operationId | Params | Notes |
|---|---|---|---|
| Sub-account details (name, timezone) | `get-location` | `{locationId}` | `location.timezone` is the account's timezone. |
| Calendars | `get-calendars` | none (locationId only) | Returns `calendars[]` with `id`, `name`, `calendarType`, `teamMembers`. Small. |
| Users / closers | `search-users` | `{companyId, locationId}` | `companyId` comes from `get-location` → `location.companyId`. May return `[]` on some accounts. If so, closers are shown by ID until a name is found on the appointment. |
| Appointments in a range | `get-calendar-events` | `{calendarId, startTime, endTime}` | `startTime`/`endTime` are **epoch milliseconds as strings**. One call per calendar. **No paging**: everything in the range comes back, so expect a file. |
| Contacts in bulk | `search-contacts-advanced` | body `{pageLimit: 100, searchAfter?, filters?}` | Cursor paging: pass the last result's `searchAfter` to get the next page. Stop when a page has fewer than 100. |
| One contact | `get-contact` | `{contactId}` | For spot checks only. Never loop it over hundreds of people. |
| A contact's deals | `search-opportunity` | `{contactId, limit: 100}` | Use per-contact lookups for the people in the no-show list. |
| Deals in bulk | `search-opportunity` | `{limit: 100, startAfter, startAfterId}` | **Page with the `meta.startAfter` + `meta.startAfterId` cursor.** Page-number paging (`page=2`) skips records. Search lags a few seconds behind brand-new deals. |
| Pipelines and stage names | `get-pipelines` | none | Maps `pipelineStageId` → stage name. |
| Custom field names | `get-custom-fields` | `{model: "contact"}` | Maps a contact's `customFields[].id` → the question it answers. |
| Conversations with a contact | `search-conversation` | `{contactId}` | HighLevel creates one conversation per contact automatically. |
| Messages in a conversation | `get-messages` | `{conversationId, type: "TYPE_SMS", limit: 50}` | Inbound replies. Use `lastMessageId` to page. |

If an operation ID above returns "not found", run `search_operations` with the "Need" column as the query, then `describe_operation`, and use what it says.

## Field gotchas (seen in real responses)

- **Appointment status:** read `appointmentStatus`. Values are `new`, `confirmed`, `cancelled`, `showed`, `noshow`, `invalid`, `completed` and `active`. The same object also carries a misspelled `appoinmentStatus`. Ignore it.
- **Booked date:** an appointment's `dateAdded` is when it was booked, and `startTime` is when the call was.
- **Closer:** `assignedUserId` on the appointment.
- **Opted out of texts:** `dndSettings.SMS.status == "active"`. The key can also be lowercase (`sms`), so check both. A top-level `dnd: true` means opted out of everything.
- **Phone:** E.164 (`+15551234567`) in `phone`. It can be missing.
- **Lead source:** `source` on the contact. It's free text and often blank. Blank shows as "Unknown".
- **Booking form answers:** `customFields[]` as `{id, value}`. The field names come from the custom-field definitions (`get-custom-fields` with `{model: "contact"}`).
- **Deal won:** an opportunity with `status == "won"`, on any pipeline.
- **Stages:** `pipelineStageId` → name via the pipelines call. Many teams have a "No Show" stage. Closers often forget to move cards, so the calendar status is the source of truth for who no-showed, and the board is only a cross-check.
