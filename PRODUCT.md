# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two internal user populations, both staff of Webook.com or its RSL (Roshan Saudi League) club partners — never public/consumer end users:

- **Club coordinators** — a `Club Manager`-group user tied to exactly one club via `Club.owner`. Prepares that club's own home matches: uploads key visuals, sets ticket types/prices/allocations, assigns gate admins, confirms teams, and pushes the match to CMS. Works match-by-match, mostly in the run-up to kickoff.
- **Operations managers / Super Admins** — `Operations Manager`/`Super Admin` group. Oversee every match across every club and competition: monitor prep-window alerts, missing-requirements and workload reports, and administer clubs/venues/competitions/users/checklist templates via the Control Panel.
- **SPL viewer role** — a read-mostly monitoring role (the Roshan League/SPL side) scoped to the Roshan League competition specifically: browses the schedule by team/round, watches ticketing-plan/KV/Webook-readiness status per match, and exports the schedule to Excel. Does not edit checklist items.

All three roles work inside the same operations dashboard/report surfaces (`operations/` app), scoped differently by `operations/permissions.py`.

## Product Purpose

Replaces the spreadsheets and group chats that used to be the only record of match-day prep. Webook Match Tracker gives one live, shared source of truth for whether a match is on track to go live on the CMS in time — showing at a glance which matches are live, upcoming, ready for ticket sale, or falling behind on their prep window, and keeping an audit trail of who did what.

Success is a match that reaches Published (or a completed post-match report) without anyone having missed a required step or a deadline, and without anyone having to ask "where are we on this match?" outside the system.

## Positioning

The mechanism competitors/spreadsheets don't have: `Match.cms_status` is never typed in by hand — it's computed automatically from real checklist completion (`refresh_checklist_status()`), so the status shown on every dashboard is always literally true, not something someone forgot to update. Paired with role-scoped visibility (a coordinator only ever sees their own club's matches) and a full activity log, it's the only place where "is this match actually ready" has one unambiguous, current answer.

## Operating Context

- A Roshan Saudi League (RSL) season: 18 clubs, matches organized into rounds/matchweeks, each match needing a defined set of pre-match prep plus a post-match report.
- The checklist has 7 categories (Event settings, Tickets, Ticket allocations, Gates & admins, Manage teams, KVs, CMS submission) plus a separate "Post Match" category whose items can only genuinely be completed after the match has been played.
- CMS status lifecycle: Draft → In Progress → Ready for CMS → Sent to CMS → Published, driven by required-checklist completion; frozen once Sent to CMS/Published until a manager changes it explicitly.
- Bilingual operation is a daily reality, not an edge case: staff switch between English and Arabic (full RTL layout) routinely; every UI string in `operations/` templates already runs through Django i18n with a maintained `locale/ar` translation.
- Both light and dark mode are actively used and switch automatically via `prefers-color-scheme` — no page should regress in either.
- Used on desktop during admin/office work and also checked on mobile/tablet by coordinators and managers away from a desk (match day, on-site).

## Capabilities and Constraints

- Django 6.0 + HTMX (partial-page swaps, no SPA framework); SQLite database.
- Match visibility, checklist/CMS actions, and report scope are all centrally gated through `operations/permissions.py` (`MatchScopedQuerysetMixin`, `can_view_all_matches`, `get_visible_matches`) — no separate ad hoc permission checks per view.
- "Ready for CMS"/readiness percentages are computed only from *required*, non-"Post Match" checklist items; Post Match items are tracked and reported separately since they can't be done before the match is played.
- Colors are sourced from Figma-exported design tokens (`static/design_tokens.css`) consumed through a semantic layer (`static/operations/styles.css`) — light and dark variants both defined, switched by `prefers-color-scheme`.
- Terminology note: the Control Panel UI labels `Club`/`Venue`/`Competition` as "Teams"/"Stadiums"/"Sections" respectively — the models don't literally match the nav labels.

## Brand Commitments

Must match Webook.com's public brand identity precisely — this is an internal tool, but it is not free to diverge stylistically from the consumer-facing webook.com site. Confirmed brand elements already in place:

- Webook logo assets (`static/images/Webook_logo.png`, `static/images/webook-logo.svg`) used in the sidebar and footer.
- Brand color tokens exported directly from Figma (`static/design_tokens.css`), both light and dark palettes — these are the canonical brand colors, not an internal reinterpretation.
- Typeface: **Gellix** (all Latin text) with **Cairo** as the Arabic fallback in the same font stack (`"Gellix", "Cairo", Arial, sans-serif`) — Gellix has no Arabic glyphs, so Cairo renders Arabic text per-glyph automatically.
- Footer byline crediting the build team (Mohamed Gamal, Mohamed Akram, Ayman Al-Basha, Ahmed Othman) and "Made with love in KSA · Webook.com" — an existing, confirmed piece of brand voice/attribution, not to be removed casually.

## Evidence on Hand

- `README.md` at the project root documents the full architecture, data model, roles/permissions, CMS lifecycle, and checklist categories in detail — treat it as authoritative product documentation, not marketing copy.
- No customer testimonials, case studies, or external marketing claims exist or are needed — this is an internal operations tool, not a persuasion surface.

## Product Principles

1. The checklist and CMS status are always the single source of truth — no UI should let a status look more "done" than the underlying required items actually are (this project has already hit real bugs from percentages/labels implying completeness that wasn't there yet, e.g. pre-match "ready" being confused with post-match report completion).
2. Every user only ever sees what their role scopes them to — coordinators their own club's matches, SPL viewers the Roshan League only, managers everything.
3. English and Arabic (full RTL) are equally first-class in every surface, not an afterthought bolted onto an English-first layout.
4. Visual identity must trace back to Webook.com's actual public brand (Figma tokens, Gellix/Cairo typography, logo) — this tool represents the Webook brand to partner clubs' staff, even though it's internal.
5. Clarity and speed of "what needs attention right now" beats visual novelty — coordinators and managers use this operationally, often under time pressure near a match's kickoff.

## Accessibility & Inclusion

No formally mandated standard (e.g. WCAG level) has been specified. Existing practice to preserve: readable contrast in both light/dark themes via the semantic color-token layer, full RTL mirroring for Arabic, and keyboard-operable form controls (native `<select>`/`<button>` elements throughout rather than custom widgets).
