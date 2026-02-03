"""Outreach logic and message generation for the prospecting assistant."""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from . import database as db


class OutreachStatus:
    """Outreach recommendation status."""
    SKIP_TOO_RECENT = "skip_too_recent"
    SKIP_NOT_INTERESTED = "skip_not_interested"
    SKIP_DNC = "skip_dnc"
    FIRST_CONTACT = "first_contact"
    FOLLOWUP_30_90 = "followup_30_90"
    FOLLOWUP_OVER_90 = "followup_over_90"
    HOT_AGENT = "hot_agent"


def days_since_outreach(agent_id: int) -> Optional[int]:
    """Calculate days since last outreach to an agent."""
    last_outreach = db.get_last_outreach(agent_id)
    if not last_outreach:
        return None

    last_date = datetime.strptime(last_outreach["outreach_date"], "%Y-%m-%d")
    return (datetime.now() - last_date).days


def get_outreach_recommendation(agent_id: int) -> Tuple[str, dict]:
    """
    Determine the appropriate outreach action for an agent.

    Returns:
        Tuple of (status, context_dict)
    """
    agent = db.get_agent_by_id(agent_id)
    if not agent:
        return (OutreachStatus.SKIP_DNC, {"reason": "Agent not found"})

    if agent["do_not_contact"]:
        return (OutreachStatus.SKIP_DNC, {"reason": "Marked as do not contact"})

    # Check last outreach
    last_outreach = db.get_last_outreach(agent_id)

    # Get recent transaction count
    recent_txn_count = db.count_agent_transactions(agent_id, days=30)
    recent_transactions = db.get_agent_transactions(agent_id, days=30)

    context = {
        "agent": dict(agent),
        "recent_txn_count": recent_txn_count,
        "recent_transactions": [dict(t) for t in recent_transactions],
    }

    # First-time contact
    if not last_outreach:
        # Hot agent check
        if recent_txn_count >= 3:
            return (OutreachStatus.HOT_AGENT, context)
        return (OutreachStatus.FIRST_CONTACT, context)

    # Check last response status
    if last_outreach["response_status"] == "not_interested":
        return (OutreachStatus.SKIP_NOT_INTERESTED, {
            "reason": "Agent previously indicated not interested"
        })

    days = days_since_outreach(agent_id)
    context["days_since_outreach"] = days
    context["last_outreach"] = dict(last_outreach)

    # Too recent - less than 30 days
    if days < 30:
        return (OutreachStatus.SKIP_TOO_RECENT, {
            "reason": f"Last contacted {days} days ago",
            "days_until_ok": 30 - days
        })

    # Hot agent with recent activity
    if recent_txn_count >= 3:
        return (OutreachStatus.HOT_AGENT, context)

    # 30-90 days - follow up
    if days <= 90:
        return (OutreachStatus.FOLLOWUP_30_90, context)

    # Over 90 days - treat as fresh opportunity
    return (OutreachStatus.FOLLOWUP_OVER_90, context)


def extract_city_from_address(address: str) -> str:
    """Extract city name from an address string."""
    from . import TARGET_CITIES

    address_lower = address.lower()
    for city in TARGET_CITIES:
        if city.lower() in address_lower:
            return city

    # Try to extract from comma-separated parts
    parts = address.split(",")
    if len(parts) >= 2:
        return parts[1].strip().split()[0]

    return "the South Bay"


def extract_street_from_address(address: str) -> str:
    """Extract just the street portion of an address."""
    parts = address.split(",")
    return parts[0].strip()


def generate_message(agent_id: int) -> Tuple[str, str, str]:
    """
    Generate an appropriate outreach message for an agent.

    Returns:
        Tuple of (message, message_type, recommendation_notes)
    """
    status, context = get_outreach_recommendation(agent_id)

    if status in [OutreachStatus.SKIP_TOO_RECENT, OutreachStatus.SKIP_NOT_INTERESTED, OutreachStatus.SKIP_DNC]:
        reason = context.get("reason", "Cannot contact at this time")
        return ("", "skip", reason)

    agent = context["agent"]
    name = agent["name"].split()[0]  # First name only
    recent_txns = context.get("recent_transactions", [])

    # Get the most recent transaction for context
    latest_txn = recent_txns[0] if recent_txns else None

    if status == OutreachStatus.FIRST_CONTACT:
        return _generate_first_contact(name, agent, latest_txn)

    elif status == OutreachStatus.HOT_AGENT:
        txn_count = context["recent_txn_count"]
        return _generate_hot_agent_message(name, agent, latest_txn, txn_count)

    elif status == OutreachStatus.FOLLOWUP_30_90:
        return _generate_followup_30_90(name, agent, latest_txn, context.get("days_since_outreach", 30))

    elif status == OutreachStatus.FOLLOWUP_OVER_90:
        return _generate_followup_over_90(name, agent, recent_txns)

    return ("", "unknown", "Could not determine appropriate message")


def _generate_first_contact(name: str, agent: dict, latest_txn: Optional[dict]) -> Tuple[str, str, str]:
    """Generate first contact message."""
    if latest_txn:
        address = extract_street_from_address(latest_txn["address"])
        city = latest_txn.get("city") or extract_city_from_address(latest_txn["address"])
        txn_type = latest_txn["transaction_type"]

        if txn_type == "listing":
            message = (
                f"Hi {name}, saw your new listing on {address} in {city}. "
                f"Would you like me to pull a property profile with title history and recent comps? "
                f"No strings attached."
            )
            return (message, "first_contact_listing", f"New listing at {address}")

        else:  # sale/closed
            message = (
                f"Hi {name}, congrats on closing {address}! "
                f"That's a great comp for {city}. Noticed you're active in the area."
            )
            return (message, "first_contact_sale", f"Recent sale at {address}")

    # No transaction info - generic but still personal
    brokerage = agent.get("brokerage") or "your brokerage"
    message = (
        f"Hi {name}, I've been tracking agent activity in the South Bay and noticed "
        f"your presence with {brokerage}. Always looking to connect with active agents in the area."
    )
    return (message, "first_contact_generic", "No recent transaction data")


def _generate_hot_agent_message(name: str, agent: dict, latest_txn: Optional[dict], txn_count: int) -> Tuple[str, str, str]:
    """Generate message for hot agents (3+ transactions in 30 days)."""
    if latest_txn:
        city = latest_txn.get("city") or extract_city_from_address(latest_txn["address"])
    else:
        city = "the South Bay"

    message = (
        f"{name}, you're absolutely crushing it - I count {txn_count} transactions this month in {city}! "
        f"With that kind of volume, title turnaround time must be critical. "
        f"Happy to be a backup resource if you ever need one."
    )
    return (message, "hot_agent", f"{txn_count} transactions in 30 days")


def _generate_followup_30_90(name: str, agent: dict, latest_txn: Optional[dict], days_since: int) -> Tuple[str, str, str]:
    """Generate follow-up message for 30-90 days since last contact."""
    if latest_txn:
        address = extract_street_from_address(latest_txn["address"])
        city = latest_txn.get("city") or extract_city_from_address(latest_txn["address"])
        txn_type = latest_txn["transaction_type"]

        if txn_type == "listing":
            message = (
                f"Hi {name}, saw you just listed {address} in {city}. "
                f"The market's been interesting there lately - would you like me to pull "
                f"a quick property profile showing recent comps and title history? No strings attached."
            )
            return (message, "followup_new_listing", f"New listing at {address}, {days_since} days since last contact")

        else:  # sale
            message = (
                f"Hi {name}, congrats on closing {address} - you're staying busy in {city}! "
                f"That's a great comp for the area."
            )
            return (message, "followup_sale", f"Closed {address}, {days_since} days since last contact")

    message = (
        f"Hi {name}, hope you're well! I've been tracking the {city if latest_txn else 'South Bay'} market "
        f"and seeing some interesting trends. Would love to share what I'm seeing if you're interested in market intel."
    )
    return (message, "followup_generic", f"{days_since} days since last contact, no new transaction")


def _generate_followup_over_90(name: str, agent: dict, recent_txns: list) -> Tuple[str, str, str]:
    """Generate follow-up message for 90+ days since last contact."""
    if recent_txns:
        city = recent_txns[0].get("city") or extract_city_from_address(recent_txns[0]["address"])
        txn_count = len(recent_txns)

        if txn_count > 1:
            message = (
                f"{name}, I've been watching your consistent activity in {city} over the past few months - "
                f"really impressive market presence. I work with several agents in your area and "
                f"always looking to connect with the top producers. Coffee sometime?"
            )
            return (message, "followup_long_term", f"{txn_count} recent transactions, 90+ days since contact")

        address = extract_street_from_address(recent_txns[0]["address"])
        message = (
            f"Hi {name}, noticed you're still active in {city} - saw your recent activity on {address}. "
            f"It's been a while - would love to reconnect if you're open to it."
        )
        return (message, "followup_long_term_single", "Single recent transaction, 90+ days since contact")

    message = (
        f"{name}, it's been a while since we connected. I'm still here in the South Bay "
        f"and always happy to be a resource. Let me know if I can ever help with anything."
    )
    return (message, "followup_long_term_no_txn", "No recent transactions, 90+ days since contact")


def suggest_outreach_timing(agent_id: int) -> str:
    """Suggest when to reach out to an agent."""
    status, context = get_outreach_recommendation(agent_id)

    if status == OutreachStatus.SKIP_TOO_RECENT:
        days_until = context.get("days_until_ok", 30)
        return f"Wait {days_until} more days before reaching out"

    if status == OutreachStatus.SKIP_NOT_INTERESTED:
        return "Agent marked as not interested - skip future outreach"

    if status == OutreachStatus.SKIP_DNC:
        return "Agent marked as do not contact"

    if status == OutreachStatus.HOT_AGENT:
        return "PRIORITY: High-volume agent - reach out immediately!"

    if status == OutreachStatus.FIRST_CONTACT:
        return "Good to go: First contact opportunity"

    if status == OutreachStatus.FOLLOWUP_30_90:
        return "Good to go: Follow-up window (30-90 days)"

    if status == OutreachStatus.FOLLOWUP_OVER_90:
        return "Good to go: Fresh opportunity (90+ days)"

    return "Ready for outreach"


def get_outreach_queue(limit: int = 20) -> list:
    """
    Get prioritized list of agents to reach out to.

    Returns agents sorted by priority:
    1. Hot agents (3+ transactions in 30 days)
    2. Agents with new activity who haven't been contacted
    3. Agents due for follow-up (30-90 days)
    4. Agents ready for re-engagement (90+ days)
    """
    agents = db.get_agents_needing_outreach(min_days_since_contact=30)
    queue = []

    for agent in agents:
        status, context = get_outreach_recommendation(agent["id"])

        if status in [OutreachStatus.SKIP_TOO_RECENT, OutreachStatus.SKIP_NOT_INTERESTED, OutreachStatus.SKIP_DNC]:
            continue

        priority_score = 0
        if status == OutreachStatus.HOT_AGENT:
            priority_score = 100 + context.get("recent_txn_count", 0)
        elif status == OutreachStatus.FIRST_CONTACT:
            priority_score = 50 + context.get("recent_txn_count", 0)
        elif status == OutreachStatus.FOLLOWUP_30_90:
            priority_score = 30
        elif status == OutreachStatus.FOLLOWUP_OVER_90:
            priority_score = 10

        queue.append({
            "agent": dict(agent),
            "status": status,
            "priority_score": priority_score,
            "context": context
        })

    # Sort by priority score descending
    queue.sort(key=lambda x: x["priority_score"], reverse=True)
    return queue[:limit]
