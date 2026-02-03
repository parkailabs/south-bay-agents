# South Bay Title Rep Prospecting Assistant

## Project Overview

A CLI tool for title representatives to track real estate agents, monitor market activity, and manage personalized outreach in the South Bay market of Los Angeles County.

### Target Cities
- Torrance
- Manhattan Beach
- Redondo Beach
- El Segundo
- Playa Vista

### Priority Brokerages
- Compass
- Keller Williams
- Vista Sotheby's
- RE/MAX Estate Properties

## Architecture

```
southbay/
├── __init__.py       # Package config, constants (TARGET_CITIES, PRIORITY_BROKERAGES)
├── __main__.py       # Entry point for `python -m southbay`
├── database.py       # SQLite storage layer (~/.southbay_agents.db)
├── outreach.py       # Message generation & repeat agent protocols
└── cli.py            # Click-based command interface with Rich formatting
```

### Database Schema

**agents** - Contact info, brokerage, priority, do_not_contact flag
**transactions** - Listings and sales linked to agents
**outreach** - Outreach history with response status and follow-up dates

### Outreach Protocol Logic

| Days Since Last Contact | Action |
|------------------------|--------|
| Never contacted | First contact with value-first message |
| < 30 days | Skip (too recent) |
| 30-90 days | Follow-up referencing new activity |
| > 90 days | Treat as fresh opportunity |
| 3+ transactions in 30 days | HOT AGENT - prioritize immediately |

## Key Commands

```bash
# Agent management
python -m southbay agent add "Name" -b "Brokerage" -e "email"
python -m southbay agent view "Name"
python -m southbay agent list

# Transaction tracking
python -m southbay transaction add "Name" -a "Address" --type listing -c "City"
python -m southbay transaction list --days 30

# Outreach
python -m southbay outreach draft "Name"    # Generate message
python -m southbay outreach log "Name" -m email
python -m southbay outreach queue           # Prioritized list
python -m southbay outreach due             # Follow-ups due

# Reports
python -m southbay report hot               # High-volume agents
python -m southbay report activity          # Market summary
python -m southbay report pipeline          # Outreach status
```

## Dependencies

- click >= 8.1.0 (CLI framework)
- rich >= 13.0.0 (Terminal formatting)
- python-dateutil >= 2.8.0 (Date handling)
- SQLite3 (built-in, no install needed)

---

# Error Log

## Database Errors

_No errors logged yet._

## CLI Errors

_No errors logged yet._

## Import/Module Errors

_No errors logged yet._

## Build Errors

_No errors logged yet._

## API Errors

_No errors logged yet._

## Type Errors

_No errors logged yet._

---

# Session Notes

_Use this section for session-specific context and reminders._
