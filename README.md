# South Bay Title Rep Prospecting Assistant

A CLI tool for title representatives to track real estate agents, monitor market activity, and manage personalized outreach in the South Bay market (Torrance, Manhattan Beach, Redondo Beach, El Segundo, Playa Vista).

## Features

- **Agent Management**: Track agents with contact info, brokerage, and transaction history
- **Transaction Tracking**: Monitor listings and sales for outreach opportunities
- **Smart Outreach**: Follow repeat agent protocols with appropriate timing
- **Message Generation**: Draft personalized, value-first outreach messages
- **Follow-up Management**: Track interactions and schedule follow-ups
- **Hot Agent Alerts**: Identify high-volume agents for priority outreach

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Add a new agent
python -m southbay agent add "Jane Smith" --brokerage "Compass" --email "jane@example.com" --phone "310-555-1234"

# Record a transaction (listing or sale)
python -m southbay transaction add "Jane Smith" --address "123 Main St, Manhattan Beach" --type listing --price 2500000

# Check who needs outreach
python -m southbay outreach due

# Generate outreach message for an agent
python -m southbay outreach draft "Jane Smith"

# Log an outreach attempt
python -m southbay outreach log "Jane Smith" --method email --notes "Sent property profile"

# View hot agents (high recent activity)
python -m southbay report hot

# View agent details
python -m southbay agent view "Jane Smith"

# List all agents
python -m southbay agent list
```

## Target Cities

- Torrance
- Manhattan Beach
- Redondo Beach
- El Segundo
- Playa Vista

## Outreach Philosophy

- Lead with value, never generic messages
- No ask on first touch
- Respect timing: no outreach within 30 days of last contact
- Track responses and preferences
