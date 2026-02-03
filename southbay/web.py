"""Flask web dashboard for South Bay Prospecting Assistant."""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from . import database as db
from . import outreach
from . import TARGET_CITIES, PRIORITY_BROKERAGES

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
app.secret_key = 'southbay-prospecting-2024'


@app.route('/')
def dashboard():
    """Main dashboard with overview stats."""
    # Get key metrics
    agents = db.list_agents()
    hot_agents = db.get_hot_agents(min_transactions=3, days=30)
    recent_transactions = db.get_recent_transactions(days=30)
    due_followups = db.get_due_followups()
    queue = outreach.get_outreach_queue(limit=5)

    # Calculate stats
    stats = {
        'total_agents': len(agents),
        'hot_agents': len(hot_agents),
        'transactions_30d': len(recent_transactions),
        'followups_due': len(due_followups),
        'listings': len([t for t in recent_transactions if t['transaction_type'] == 'listing']),
        'sales': len([t for t in recent_transactions if t['transaction_type'] == 'sale']),
    }

    # City breakdown
    city_stats = {}
    for city in TARGET_CITIES:
        city_stats[city] = len([t for t in recent_transactions if t['city'] == city])

    return render_template('dashboard.html',
                         stats=stats,
                         hot_agents=hot_agents,
                         queue=queue,
                         city_stats=city_stats,
                         due_followups=due_followups[:5])


@app.route('/agents')
def agents_list():
    """List all agents."""
    brokerage_filter = request.args.get('brokerage')
    priority_filter = request.args.get('priority')

    agents = db.list_agents(brokerage=brokerage_filter, priority=priority_filter, include_dnc=True)

    # Add stats for each agent
    agents_with_stats = []
    for agent in agents:
        stats = db.get_agent_stats(agent['id'])
        agents_with_stats.append({
            **dict(agent),
            'stats': stats
        })

    return render_template('agents.html',
                         agents=agents_with_stats,
                         brokerages=PRIORITY_BROKERAGES)


@app.route('/agents/add', methods=['GET', 'POST'])
def add_agent():
    """Add a new agent."""
    if request.method == 'POST':
        try:
            agent_id = db.add_agent(
                name=request.form['name'],
                brokerage=request.form.get('brokerage') or None,
                email=request.form.get('email') or None,
                phone=request.form.get('phone') or None,
                instagram=request.form.get('instagram') or None,
                linkedin=request.form.get('linkedin') or None,
                notes=request.form.get('notes') or None,
                is_team_agent='is_team_agent' in request.form,
                priority=request.form.get('priority', 'normal')
            )
            flash(f'Agent added successfully!', 'success')
            return redirect(url_for('agent_detail', agent_id=agent_id))
        except Exception as e:
            if 'UNIQUE' in str(e):
                flash('An agent with this name already exists.', 'error')
            else:
                flash(f'Error adding agent: {e}', 'error')

    return render_template('agent_form.html',
                         agent=None,
                         brokerages=PRIORITY_BROKERAGES)


@app.route('/agents/<int:agent_id>')
def agent_detail(agent_id):
    """View agent details."""
    agent = db.get_agent_by_id(agent_id)
    if not agent:
        flash('Agent not found', 'error')
        return redirect(url_for('agents_list'))

    stats = db.get_agent_stats(agent_id)
    transactions = db.get_agent_transactions(agent_id, days=365)
    outreach_history = db.get_agent_outreach_history(agent_id)

    # Get outreach recommendation
    status, context = outreach.get_outreach_recommendation(agent_id)
    timing = outreach.suggest_outreach_timing(agent_id)

    # Generate draft message
    message, msg_type, notes = outreach.generate_message(agent_id)

    return render_template('agent_detail.html',
                         agent=dict(agent),
                         stats=stats,
                         transactions=transactions,
                         outreach_history=outreach_history,
                         timing=timing,
                         draft_message=message,
                         message_type=msg_type,
                         outreach_status=status)


@app.route('/agents/<int:agent_id>/edit', methods=['GET', 'POST'])
def edit_agent(agent_id):
    """Edit an agent."""
    agent = db.get_agent_by_id(agent_id)
    if not agent:
        flash('Agent not found', 'error')
        return redirect(url_for('agents_list'))

    if request.method == 'POST':
        db.update_agent(
            agent_id,
            name=request.form['name'],
            brokerage=request.form.get('brokerage') or None,
            email=request.form.get('email') or None,
            phone=request.form.get('phone') or None,
            instagram=request.form.get('instagram') or None,
            linkedin=request.form.get('linkedin') or None,
            notes=request.form.get('notes') or None,
            is_team_agent='is_team_agent' in request.form,
            priority=request.form.get('priority', 'normal'),
            do_not_contact='do_not_contact' in request.form
        )
        flash('Agent updated successfully!', 'success')
        return redirect(url_for('agent_detail', agent_id=agent_id))

    return render_template('agent_form.html',
                         agent=dict(agent),
                         brokerages=PRIORITY_BROKERAGES)


@app.route('/transactions')
def transactions_list():
    """List all transactions."""
    days = request.args.get('days', 30, type=int)
    city_filter = request.args.get('city')

    transactions = db.get_recent_transactions(days=days, city=city_filter)

    return render_template('transactions.html',
                         transactions=transactions,
                         days=days,
                         cities=TARGET_CITIES,
                         selected_city=city_filter)


@app.route('/transactions/add', methods=['GET', 'POST'])
def add_transaction():
    """Add a new transaction."""
    if request.method == 'POST':
        agent_name = request.form['agent_name']
        agent = db.get_agent_by_name(agent_name)

        if not agent:
            # Create agent if doesn't exist
            agent_id = db.add_agent(name=agent_name)
            flash(f'Created new agent: {agent_name}', 'info')
        else:
            agent_id = agent['id']

        db.add_transaction(
            agent_id=agent_id,
            address=request.form['address'],
            transaction_type=request.form['transaction_type'],
            city=request.form.get('city') or None,
            price=int(request.form['price']) if request.form.get('price') else None,
            transaction_date=request.form.get('transaction_date') or None,
            notes=request.form.get('notes') or None
        )

        flash('Transaction recorded!', 'success')

        # Show outreach suggestion
        timing = outreach.suggest_outreach_timing(agent_id)
        if 'PRIORITY' in timing or 'Good to go' in timing:
            flash(f'Outreach: {timing}', 'info')

        return redirect(url_for('transactions_list'))

    agents = db.list_agents()
    return render_template('transaction_form.html',
                         agents=agents,
                         cities=TARGET_CITIES)


@app.route('/outreach')
def outreach_queue():
    """View outreach queue."""
    queue = outreach.get_outreach_queue(limit=50)
    due_followups = db.get_due_followups()

    return render_template('outreach.html',
                         queue=queue,
                         due_followups=due_followups,
                         OutreachStatus=outreach.OutreachStatus)


@app.route('/outreach/log/<int:agent_id>', methods=['GET', 'POST'])
def log_outreach(agent_id):
    """Log outreach to an agent."""
    agent = db.get_agent_by_id(agent_id)
    if not agent:
        flash('Agent not found', 'error')
        return redirect(url_for('outreach_queue'))

    if request.method == 'POST':
        db.log_outreach(
            agent_id=agent_id,
            method=request.form['method'],
            message_type=request.form.get('message_type', 'manual'),
            notes=request.form.get('notes') or None,
            response_status=request.form.get('response_status', 'no_response'),
            follow_up_date=request.form.get('follow_up_date') or None
        )

        flash('Outreach logged!', 'success')
        return redirect(url_for('agent_detail', agent_id=agent_id))

    # Get draft message
    message, msg_type, notes = outreach.generate_message(agent_id)

    return render_template('outreach_form.html',
                         agent=dict(agent),
                         draft_message=message,
                         message_type=msg_type)


@app.route('/outreach/response/<int:agent_id>', methods=['POST'])
def record_response(agent_id):
    """Record a response from an agent."""
    last_outreach = db.get_last_outreach(agent_id)
    if last_outreach:
        db.update_outreach_response(
            last_outreach['id'],
            request.form['response_status'],
            request.form.get('notes')
        )
        flash('Response recorded!', 'success')
    else:
        flash('No outreach history found', 'error')

    return redirect(url_for('agent_detail', agent_id=agent_id))


@app.route('/api/draft-message/<int:agent_id>')
def api_draft_message(agent_id):
    """API endpoint to get draft message for an agent."""
    message, msg_type, notes = outreach.generate_message(agent_id)
    return jsonify({
        'message': message,
        'type': msg_type,
        'notes': notes
    })


@app.route('/quick', methods=['GET', 'POST'])
def quick_add():
    """Quick add: agent + transaction + outreach suggestion."""
    if request.method == 'POST':
        agent_name = request.form['agent_name']
        agent = db.get_agent_by_name(agent_name)

        if not agent:
            agent_id = db.add_agent(
                name=agent_name,
                brokerage=request.form.get('brokerage') or None
            )
            flash(f'Created new agent: {agent_name}', 'info')
        else:
            agent_id = agent['id']

        db.add_transaction(
            agent_id=agent_id,
            address=request.form['address'],
            transaction_type=request.form['transaction_type'],
            city=request.form.get('city') or None,
            price=int(request.form['price']) if request.form.get('price') else None
        )

        flash('Transaction recorded!', 'success')
        return redirect(url_for('agent_detail', agent_id=agent_id))

    return render_template('quick_add.html',
                         cities=TARGET_CITIES,
                         brokerages=PRIORITY_BROKERAGES)


def run_server(host='127.0.0.1', port=5000, debug=True):
    """Run the Flask development server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server()
