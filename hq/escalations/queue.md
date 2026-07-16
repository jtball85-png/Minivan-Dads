# Escalation Queue

Open items needing CEO judgment. Resolved items move to `resolved.md` —
never delete an item from here, only move it.

Format per entry (urgent items are sorted first by `hq.py`, not by their
position in this file):

```
## ESC-{NNN}
- Raised: YYYY-MM-DD
- Raised by: {department}
- Urgency: urgent | normal
- Summary: ...
```

<!-- new escalations are appended below this line -->


## ESC-002
- Raised: 2026-07-16
- Raised by: market_intel
- Urgency: normal
- Summary: Marketplace prior-use of "minivan dad" and "swagger wagon" phrasing (multiple small Etsy/Amazon sellers, longstanding) is diffuse but real — worth a check that the pending Class 25 word-mark strategy accounts for this generic use before/at next filing milestone; also confirm current USPTO docket status, which this department cannot verify directly.

## ESC-003
- Raised: 2026-07-16
- Raised by: brain (on CEO instruction)
- Urgency: normal
- Summary: Verify the first scheduled market_intel run fired Thursday night: check the GitHub Actions tab (market-intel-agent workflow) Friday morning and confirm a fresh weekly report was committed to hq/reports/market_intel/ before running brain ingest. Resolve this once confirmed.
