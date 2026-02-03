"""CLI interface for the South Bay Prospecting Assistant."""

import click
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from . import database as db
from . import outreach
from . import TARGET_CITIES, PRIORITY_BROKERAGES

console = Console()


@click.group()
def cli():
    """South Bay Title Rep Prospecting Assistant.

    Track agents, monitor market activity, and manage personalized outreach
    in Torrance, Manhattan Beach, Redondo Beach, El Segundo, and Playa Vista.
    """
    pass


# === Agent Commands ===

@cli.group()
def agent():
    """Manage agent records."""
    pass


@agent.command("add")
@click.argument("name")
@click.option("--brokerage", "-b", help="Agent's brokerage")
@click.option("--email", "-e", help="Email address")
@click.option("--phone", "-p", help="Phone number")
@click.option("--instagram", "-i", help="Instagram handle")
@click.option("--linkedin", "-l", help="LinkedIn URL")
@click.option("--notes", "-n", help="Notes about the agent")
@click.option("--team", is_flag=True, help="Mark as team agent")
@click.option("--priority", type=click.Choice(["low", "normal", "high"]), default="normal")
def add_agent(name, brokerage, email, phone, instagram, linkedin, notes, team, priority):
    """Add a new agent to track."""
    try:
        agent_id = db.add_agent(
            name=name,
            brokerage=brokerage,
            email=email,
            phone=phone,
            instagram=instagram,
            linkedin=linkedin,
            notes=notes,
            is_team_agent=team,
            priority=priority
        )
        console.print(f"[green]Added agent:[/green] {name} (ID: {agent_id})")

        if brokerage and brokerage in PRIORITY_BROKERAGES:
            console.print(f"[yellow]Note:[/yellow] {brokerage} is a priority brokerage")

    except Exception as e:
        if "UNIQUE constraint" in str(e):
            console.print(f"[red]Error:[/red] Agent '{name}' already exists")
        else:
            console.print(f"[red]Error:[/red] {e}")


@agent.command("view")
@click.argument("name")
def view_agent(name):
    """View detailed agent profile."""
    agent = db.get_agent_by_name(name)
    if not agent:
        console.print(f"[red]Agent not found:[/red] {name}")
        return

    # Agent info panel
    info_text = Text()
    info_text.append(f"ID: {agent['id']}\n", style="dim")
    info_text.append(f"Brokerage: {agent['brokerage'] or 'Unknown'}\n")
    info_text.append(f"Email: {agent['email'] or 'Not set'}\n")
    info_text.append(f"Phone: {agent['phone'] or 'Not set'}\n")
    if agent['instagram']:
        info_text.append(f"Instagram: @{agent['instagram']}\n")
    if agent['linkedin']:
        info_text.append(f"LinkedIn: {agent['linkedin']}\n")
    info_text.append(f"\nPriority: {agent['priority']}")
    if agent['is_team_agent']:
        info_text.append(" | Team Agent", style="cyan")
    if agent['do_not_contact']:
        info_text.append("\n[DO NOT CONTACT]", style="red bold")

    console.print(Panel(info_text, title=f"[bold]{agent['name']}[/bold]", border_style="blue"))

    # Stats
    stats = db.get_agent_stats(agent['id'])
    stats_table = Table(show_header=False, box=box.SIMPLE)
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Value", style="bold")
    stats_table.add_row("Transactions (30 days)", str(stats['transactions_30d']))
    stats_table.add_row("Transactions (12 months)", str(stats['transactions_yearly']))
    stats_table.add_row("Total transactions", str(stats['total_transactions']))
    stats_table.add_row("Total outreach attempts", str(stats['total_outreach']))
    if stats['last_outreach_date']:
        stats_table.add_row("Last outreach", f"{stats['last_outreach_date']} ({stats['last_outreach_status']})")

    console.print(Panel(stats_table, title="Activity Stats", border_style="green"))

    # Recent transactions
    transactions = db.get_agent_transactions(agent['id'], days=90)
    if transactions:
        txn_table = Table(title="Recent Transactions (90 days)", box=box.ROUNDED)
        txn_table.add_column("Date", style="dim")
        txn_table.add_column("Type")
        txn_table.add_column("Address")
        txn_table.add_column("Price", justify="right")

        for txn in transactions[:10]:
            price = f"${txn['price']:,}" if txn['price'] else "-"
            txn_table.add_row(
                txn['transaction_date'],
                txn['transaction_type'],
                txn['address'],
                price
            )
        console.print(txn_table)

    # Outreach recommendation
    timing = outreach.suggest_outreach_timing(agent['id'])
    console.print(f"\n[bold]Outreach timing:[/bold] {timing}")

    if agent['notes']:
        console.print(f"\n[dim]Notes:[/dim] {agent['notes']}")


@agent.command("list")
@click.option("--brokerage", "-b", help="Filter by brokerage")
@click.option("--priority", type=click.Choice(["low", "normal", "high"]), help="Filter by priority")
@click.option("--all", "include_all", is_flag=True, help="Include do-not-contact agents")
def list_agents(brokerage, priority, include_all):
    """List all tracked agents."""
    agents = db.list_agents(brokerage=brokerage, priority=priority, include_dnc=include_all)

    if not agents:
        console.print("[yellow]No agents found[/yellow]")
        return

    table = Table(title="Tracked Agents", box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Brokerage")
    table.add_column("Email")
    table.add_column("Priority")
    table.add_column("Status")

    for agent in agents:
        status = ""
        if agent['do_not_contact']:
            status = "[red]DNC[/red]"
        elif agent['is_team_agent']:
            status = "[cyan]Team[/cyan]"

        table.add_row(
            str(agent['id']),
            agent['name'],
            agent['brokerage'] or "-",
            agent['email'] or "-",
            agent['priority'],
            status
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(agents)} agents[/dim]")


@agent.command("update")
@click.argument("name")
@click.option("--brokerage", "-b", help="Update brokerage")
@click.option("--email", "-e", help="Update email")
@click.option("--phone", "-p", help="Update phone")
@click.option("--instagram", "-i", help="Update Instagram")
@click.option("--linkedin", "-l", help="Update LinkedIn")
@click.option("--notes", "-n", help="Update notes")
@click.option("--priority", type=click.Choice(["low", "normal", "high"]))
@click.option("--dnc/--no-dnc", default=None, help="Set do-not-contact status")
def update_agent(name, brokerage, email, phone, instagram, linkedin, notes, priority, dnc):
    """Update an agent's information."""
    agent = db.get_agent_by_name(name)
    if not agent:
        console.print(f"[red]Agent not found:[/red] {name}")
        return

    updates = {}
    if brokerage is not None:
        updates['brokerage'] = brokerage
    if email is not None:
        updates['email'] = email
    if phone is not None:
        updates['phone'] = phone
    if instagram is not None:
        updates['instagram'] = instagram
    if linkedin is not None:
        updates['linkedin'] = linkedin
    if notes is not None:
        updates['notes'] = notes
    if priority is not None:
        updates['priority'] = priority
    if dnc is not None:
        updates['do_not_contact'] = dnc

    if not updates:
        console.print("[yellow]No updates specified[/yellow]")
        return

    if db.update_agent(agent['id'], **updates):
        console.print(f"[green]Updated agent:[/green] {agent['name']}")
    else:
        console.print("[red]Failed to update agent[/red]")


# === Transaction Commands ===

@cli.group()
def transaction():
    """Track listings and sales."""
    pass


@transaction.command("add")
@click.argument("agent_name")
@click.option("--address", "-a", required=True, help="Property address")
@click.option("--type", "txn_type", type=click.Choice(["listing", "sale"]), required=True)
@click.option("--city", "-c", type=click.Choice(TARGET_CITIES), help="City")
@click.option("--price", "-p", type=int, help="Price")
@click.option("--date", "-d", help="Transaction date (YYYY-MM-DD)")
@click.option("--notes", "-n", help="Notes")
def add_transaction(agent_name, address, txn_type, city, price, date, notes):
    """Record a new listing or sale for an agent."""
    agent = db.get_agent_by_name(agent_name)
    if not agent:
        console.print(f"[red]Agent not found:[/red] {agent_name}")
        return

    txn_id = db.add_transaction(
        agent_id=agent['id'],
        address=address,
        transaction_type=txn_type,
        city=city,
        price=price,
        transaction_date=date,
        notes=notes
    )

    console.print(f"[green]Recorded {txn_type}:[/green] {address}")
    console.print(f"[dim]Agent: {agent['name']} | ID: {txn_id}[/dim]")

    # Show outreach suggestion
    timing = outreach.suggest_outreach_timing(agent['id'])
    console.print(f"\n[bold]Outreach:[/bold] {timing}")


@transaction.command("list")
@click.option("--days", "-d", type=int, default=30, help="Show transactions from last N days")
@click.option("--city", "-c", type=click.Choice(TARGET_CITIES), help="Filter by city")
def list_transactions(days, city):
    """View recent transactions."""
    transactions = db.get_recent_transactions(days=days, city=city)

    if not transactions:
        console.print(f"[yellow]No transactions in the last {days} days[/yellow]")
        return

    table = Table(title=f"Transactions (Last {days} Days)", box=box.ROUNDED)
    table.add_column("Date", style="dim")
    table.add_column("Type")
    table.add_column("Agent", style="bold")
    table.add_column("Brokerage")
    table.add_column("Address")
    table.add_column("City")
    table.add_column("Price", justify="right")

    for txn in transactions:
        price = f"${txn['price']:,}" if txn['price'] else "-"
        table.add_row(
            txn['transaction_date'],
            txn['transaction_type'],
            txn['agent_name'],
            txn['brokerage'] or "-",
            txn['address'],
            txn['city'] or "-",
            price
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(transactions)} transactions[/dim]")


# === Outreach Commands ===

@cli.group()
def outreach_cmd():
    """Manage outreach and follow-ups."""
    pass


# Rename to avoid shadowing the imported module
@cli.group(name="outreach")
def outreach_group():
    """Manage outreach and follow-ups."""
    pass


@outreach_group.command("draft")
@click.argument("agent_name")
def draft_outreach(agent_name):
    """Generate a personalized outreach message for an agent."""
    agent = db.get_agent_by_name(agent_name)
    if not agent:
        console.print(f"[red]Agent not found:[/red] {agent_name}")
        return

    message, msg_type, notes = outreach.generate_message(agent['id'])

    if msg_type == "skip":
        console.print(f"[yellow]Skip outreach:[/yellow] {notes}")
        return

    console.print(Panel(
        message,
        title=f"[bold]Message for {agent['name']}[/bold]",
        subtitle=f"Type: {msg_type}",
        border_style="green"
    ))
    console.print(f"\n[dim]Context: {notes}[/dim]")


@outreach_group.command("log")
@click.argument("agent_name")
@click.option("--method", "-m", type=click.Choice(["email", "text", "call", "dm", "in_person"]), required=True)
@click.option("--notes", "-n", help="Notes about the outreach")
@click.option("--response", "-r", type=click.Choice(["no_response", "positive", "neutral", "not_interested"]),
              default="no_response")
@click.option("--followup", "-f", help="Follow-up date (YYYY-MM-DD)")
def log_outreach(agent_name, method, notes, response, followup):
    """Log an outreach attempt."""
    agent = db.get_agent_by_name(agent_name)
    if not agent:
        console.print(f"[red]Agent not found:[/red] {agent_name}")
        return

    # Get message type from most recent draft context
    _, msg_type, _ = outreach.generate_message(agent['id'])

    outreach_id = db.log_outreach(
        agent_id=agent['id'],
        method=method,
        message_type=msg_type if msg_type != "skip" else "manual",
        notes=notes,
        response_status=response,
        follow_up_date=followup
    )

    console.print(f"[green]Logged outreach:[/green] {method} to {agent['name']}")
    console.print(f"[dim]Outreach ID: {outreach_id}[/dim]")

    if response == "not_interested":
        console.print("[yellow]Agent marked as not interested - will skip future outreach[/yellow]")

    if followup:
        console.print(f"[cyan]Follow-up scheduled:[/cyan] {followup}")


@outreach_group.command("due")
def due_followups():
    """Show agents with follow-ups due."""
    due = db.get_due_followups()

    if not due:
        console.print("[green]No follow-ups due today![/green]")
        return

    table = Table(title="Follow-ups Due", box=box.ROUNDED)
    table.add_column("Due Date", style="dim")
    table.add_column("Agent", style="bold")
    table.add_column("Brokerage")
    table.add_column("Last Method")
    table.add_column("Last Status")
    table.add_column("Contact")

    for item in due:
        contact = item['email'] or item['phone'] or "-"
        table.add_row(
            item['follow_up_date'],
            item['agent_name'],
            item['brokerage'] or "-",
            item['method'],
            item['response_status'],
            contact
        )

    console.print(table)


@outreach_group.command("queue")
@click.option("--limit", "-l", type=int, default=10, help="Number of agents to show")
def outreach_queue(limit):
    """Show prioritized outreach queue."""
    queue = outreach.get_outreach_queue(limit=limit)

    if not queue:
        console.print("[yellow]No agents in outreach queue[/yellow]")
        return

    table = Table(title="Outreach Queue (Prioritized)", box=box.ROUNDED)
    table.add_column("Priority", justify="center")
    table.add_column("Agent", style="bold")
    table.add_column("Brokerage")
    table.add_column("Status")
    table.add_column("Recent Txns")
    table.add_column("Action")

    for item in queue:
        agent = item['agent']
        status = item['status']

        # Format priority indicator
        score = item['priority_score']
        if score >= 100:
            priority = "[red bold]HOT[/red bold]"
        elif score >= 50:
            priority = "[yellow]HIGH[/yellow]"
        else:
            priority = "[dim]NORMAL[/dim]"

        # Format status
        status_display = status.replace("_", " ").title()

        # Get recent txn count
        recent_txns = item['context'].get('recent_txn_count', 0)

        # Action suggestion
        if status == outreach.OutreachStatus.HOT_AGENT:
            action = "Reach out NOW"
        elif status == outreach.OutreachStatus.FIRST_CONTACT:
            action = "First contact"
        elif status == outreach.OutreachStatus.FOLLOWUP_30_90:
            action = "Follow up"
        else:
            action = "Re-engage"

        table.add_row(
            priority,
            agent['name'],
            agent.get('brokerage') or "-",
            status_display,
            str(recent_txns),
            action
        )

    console.print(table)
    console.print(f"\n[dim]Use 'outreach draft <name>' to generate a message[/dim]")


@outreach_group.command("response")
@click.argument("agent_name")
@click.option("--status", "-s", type=click.Choice(["positive", "neutral", "not_interested"]), required=True)
@click.option("--notes", "-n", help="Notes about the response")
def record_response(agent_name, status, notes):
    """Record a response from an agent."""
    agent = db.get_agent_by_name(agent_name)
    if not agent:
        console.print(f"[red]Agent not found:[/red] {agent_name}")
        return

    last_outreach = db.get_last_outreach(agent['id'])
    if not last_outreach:
        console.print("[yellow]No outreach history found for this agent[/yellow]")
        return

    db.update_outreach_response(last_outreach['id'], status, notes)
    console.print(f"[green]Recorded response:[/green] {status} from {agent['name']}")

    if status == "not_interested":
        console.print("[yellow]Agent will be excluded from future outreach[/yellow]")
    elif status == "positive":
        console.print("[green]Great! Consider scheduling a follow-up meeting.[/green]")


# === Report Commands ===

@cli.group()
def report():
    """View reports and analytics."""
    pass


@report.command("hot")
@click.option("--min-txns", "-m", type=int, default=3, help="Minimum transactions to qualify")
@click.option("--days", "-d", type=int, default=30, help="Look-back period in days")
def hot_agents(min_txns, days):
    """Show high-volume agents (hot leads)."""
    agents = db.get_hot_agents(min_transactions=min_txns, days=days)

    if not agents:
        console.print(f"[yellow]No agents with {min_txns}+ transactions in {days} days[/yellow]")
        return

    table = Table(title=f"Hot Agents ({min_txns}+ transactions in {days} days)", box=box.ROUNDED)
    table.add_column("Agent", style="bold")
    table.add_column("Brokerage")
    table.add_column("Transactions", justify="center", style="red bold")
    table.add_column("Latest Activity")
    table.add_column("Priority")

    for agent in agents:
        table.add_row(
            agent['name'],
            agent['brokerage'] or "-",
            str(agent['transaction_count']),
            agent['latest_transaction'],
            agent['priority']
        )

    console.print(table)
    console.print(f"\n[bold red]These agents are on fire - prioritize outreach![/bold red]")


@report.command("activity")
@click.option("--days", "-d", type=int, default=30, help="Look-back period")
def activity_report(days):
    """Show market activity summary."""
    transactions = db.get_recent_transactions(days=days)

    if not transactions:
        console.print(f"[yellow]No activity in the last {days} days[/yellow]")
        return

    # Count by city
    city_counts = {}
    type_counts = {"listing": 0, "sale": 0}
    agent_counts = {}

    for txn in transactions:
        city = txn['city'] or "Unknown"
        city_counts[city] = city_counts.get(city, 0) + 1
        type_counts[txn['transaction_type']] = type_counts.get(txn['transaction_type'], 0) + 1
        agent_counts[txn['agent_name']] = agent_counts.get(txn['agent_name'], 0) + 1

    console.print(f"\n[bold]Market Activity - Last {days} Days[/bold]\n")

    # Summary
    console.print(f"Total Transactions: [bold]{len(transactions)}[/bold]")
    console.print(f"  Listings: {type_counts.get('listing', 0)}")
    console.print(f"  Sales: {type_counts.get('sale', 0)}")

    # By city
    console.print("\n[bold]By City:[/bold]")
    for city in TARGET_CITIES:
        count = city_counts.get(city, 0)
        if count > 0:
            console.print(f"  {city}: {count}")

    # Top agents
    console.print("\n[bold]Most Active Agents:[/bold]")
    top_agents = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    for agent_name, count in top_agents:
        console.print(f"  {agent_name}: {count} transactions")


@report.command("pipeline")
def pipeline_report():
    """Show outreach pipeline status."""
    # Get agents needing outreach
    queue = outreach.get_outreach_queue(limit=100)

    # Categorize
    hot = [q for q in queue if q['priority_score'] >= 100]
    high = [q for q in queue if 50 <= q['priority_score'] < 100]
    normal = [q for q in queue if q['priority_score'] < 50]

    # Get follow-ups
    due = db.get_due_followups()

    console.print("\n[bold]Outreach Pipeline[/bold]\n")
    console.print(f"[red bold]Hot agents (3+ txns):[/red bold] {len(hot)}")
    console.print(f"[yellow]High priority (first contact):[/yellow] {len(high)}")
    console.print(f"[dim]Normal (follow-ups):[/dim] {len(normal)}")
    console.print(f"\n[cyan]Follow-ups due today:[/cyan] {len(due)}")

    total = len(hot) + len(high) + len(normal)
    console.print(f"\n[bold]Total in pipeline:[/bold] {total} agents")

    if hot:
        console.print("\n[red bold]Act now - Hot agents:[/red bold]")
        for item in hot[:3]:
            console.print(f"  - {item['agent']['name']} ({item['context'].get('recent_txn_count', 0)} recent txns)")


# === Quick Commands ===

@cli.command()
@click.argument("agent_name")
@click.argument("address")
@click.option("--type", "txn_type", type=click.Choice(["listing", "sale"]), default="listing")
@click.option("--city", "-c", type=click.Choice(TARGET_CITIES))
@click.option("--price", "-p", type=int)
def quick(agent_name, address, txn_type, city, price):
    """Quick add: Record a transaction and get outreach suggestion.

    Example: southbay quick "Jane Smith" "123 Main St" --type listing --city "Manhattan Beach"
    """
    # Check if agent exists, create if not
    agent = db.get_agent_by_name(agent_name)
    if not agent:
        console.print(f"[yellow]Agent not found, creating:[/yellow] {agent_name}")
        agent_id = db.add_agent(name=agent_name)
        agent = db.get_agent_by_id(agent_id)

    # Add transaction
    db.add_transaction(
        agent_id=agent['id'],
        address=address,
        transaction_type=txn_type,
        city=city,
        price=price
    )
    console.print(f"[green]Recorded {txn_type}:[/green] {address}")

    # Generate outreach message
    message, msg_type, notes = outreach.generate_message(agent['id'])

    if msg_type == "skip":
        console.print(f"\n[yellow]Outreach:[/yellow] {notes}")
    else:
        console.print(Panel(
            message,
            title=f"[bold]Suggested outreach for {agent['name']}[/bold]",
            border_style="green"
        ))


# === Web Server Command ===

@cli.command()
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=5000, type=int, help="Port to bind to")
@click.option("--debug/--no-debug", default=True, help="Enable debug mode")
def web(host, port, debug):
    """Launch the web dashboard.

    Example: python -m southbay web --port 8080
    """
    from .web import run_server
    console.print(f"[bold green]Starting South Bay Prospecting Dashboard[/bold green]")
    console.print(f"[dim]Open http://{host}:{port} in your browser[/dim]\n")
    run_server(host=host, port=port, debug=debug)


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
