#!/usr/bin/env python3
"""
Flask UI for Coffee Manager
Pages: Transactions (with filters), placeholders for Invoicing and Scan Mode
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import sys

# Allow importing database manager
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from database_manager import CoffeeDatabaseManager


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')

    db = CoffeeDatabaseManager()

    # Ensure normal mode is the default: initialize scan_mode to '0' if unset
    try:
        current_scan_mode = db.get_setting('scan_mode')
        if current_scan_mode is None:
            db.set_setting('scan_mode', '0')
    except Exception:
        pass

    @app.route('/')
    def index():
        return transactions()

    @app.route('/transactions')
    def transactions():
        # Read filters from query string
        filters = {
            'token_id': request.args.get('token_id') or '',
            'user_name': request.args.get('user_name') or '',
            'name': request.args.get('name') or '',
            'email_address': request.args.get('email_address') or '',
            'start_date': request.args.get('start_date') or '',
            'end_date': request.args.get('end_date') or '',
            'start_time': request.args.get('start_time') or '',
            'end_time': request.args.get('end_time') or '',
        }

        # Build query: join usage_log with users and apply filters
        # Note: simple LIKE filters with %term% and optional date/time ranges
        query = (
            "SELECT ul.id, ul.timestamp, u.token_id, u.user_name, u.name, u.email_address "
            "FROM usage_log ul "
            "JOIN users u ON ul.token_id = u.token_id "
            "WHERE 1=1 "
        )
        params = []

        if filters['token_id']:
            query += "AND u.token_id LIKE ? "
            params.append(f"%{filters['token_id']}%")
        if filters['user_name']:
            query += "AND u.user_name LIKE ? "
            params.append(f"%{filters['user_name']}%")
        if filters['name']:
            query += "AND u.name LIKE ? "
            params.append(f"%{filters['name']}%")
        if filters['email_address']:
            query += "AND u.email_address LIKE ? "
            params.append(f"%{filters['email_address']}%")
        # Date range filters (expects YYYY-MM-DD)
        if filters['start_date']:
            query += "AND date(ul.timestamp) >= date(?) "
            params.append(filters['start_date'])
        if filters['end_date']:
            query += "AND date(ul.timestamp) <= date(?) "
            params.append(filters['end_date'])

        # Time-of-day range filters (expects HH:MM)
        if filters['start_time']:
            query += "AND time(ul.timestamp) >= time(?) "
            params.append(filters['start_time'])
        if filters['end_time']:
            query += "AND time(ul.timestamp) <= time(?) "
            params.append(filters['end_time'])

        query += "ORDER BY ul.timestamp DESC LIMIT 500"

        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            records = [dict(row) for row in rows]

        return render_template('transactions.html', records=records, filters=filters)

    @app.route('/invoicing')
    def invoicing():
        # List users with counts of uninvoiced usage
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT u.token_id, u.user_name, u.name, u.email_address,
                       (SELECT COUNT(*) FROM usage_log ul
                        LEFT JOIN invoice_items ii ON ii.usage_id = ul.id
                        WHERE ii.id IS NULL AND ul.token_id = u.token_id) AS uninvoiced
                FROM users u
                ORDER BY uninvoiced DESC, u.created_at DESC
                """
            )
            users = [dict(r) for r in cur.fetchall()]
        invoices = db.list_invoices()
        return render_template('invoicing.html', users=users, invoices=invoices)

    @app.route('/invoicing/create/<token_id>', methods=['POST'])
    def create_invoice(token_id):
        # Determine period: from last invoice end (or first usage) to now
        last_end = db.get_last_invoice_end(token_id)
        with db.get_connection() as conn:
            cur = conn.cursor()
            if last_end is None:
                cur.execute("SELECT MIN(timestamp) FROM usage_log WHERE token_id=?", (token_id,))
                start = cur.fetchone()[0]
            else:
                start = last_end
        if not start:
            return render_template('message.html', title='No Usage', message='No uninvoiced usage found for this user.')
        from_ts = start
        to_ts = request.form.get('to_ts') or None
        if not to_ts:
            from datetime import datetime
            to_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        invoice_id = db.create_invoice_for_user(token_id, from_ts, to_ts)
        if not invoice_id:
            return render_template('message.html', title='No Items', message='No uninvoiced usage in selected period.')
        inv = db.get_invoice(invoice_id)
        return render_template('invoice_detail.html', invoice=inv, mailto=_build_mailto(inv))

    def _build_mailto(inv):
        # Build a mailto link with subject/body from configurable templates and price
        to = inv.get('email_address') or ''
        # Fetch templates and price (defaults)
        subject_tpl = db.get_setting('invoice_subject') or 'Coffee Invoice {period_start} - {period_end}'
        body_tpl = (
            db.get_setting('invoice_body') or
            'Dear {user_display}, this is your invoice for the billing period {period_start} until {period_end}. Total coffees: {total_items}, price per coffee: {price_per_coffee}, total price: {total_price}. Thank you!'
        )
        try:
            price_per_coffee = float(db.get_setting('price_per_coffee') or '0')
        except Exception:
            price_per_coffee = 0.0
        total_items = inv.get('total_items') or 0
        total_price = round(price_per_coffee * float(total_items), 2)
        user_display = inv.get('name') or inv.get('user_name') or inv['token_id']
        subject = subject_tpl.format(period_start=inv['period_start'], period_end=inv['period_end'])
        body = body_tpl.format(
            user_display=user_display,
            period_start=inv['period_start'],
            period_end=inv['period_end'],
            total_items=total_items,
            price_per_coffee=price_per_coffee,
            total_price=total_price,
        )
        import urllib.parse
        return f"mailto:{urllib.parse.quote(to)}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

    @app.post('/invoicing/<int:invoice_id>/toggle')
    def toggle_invoice(invoice_id: int):
        inv = db.get_invoice(invoice_id)
        if not inv:
            return render_template('message.html', title='Not Found', message='Invoice not found')
        db.set_invoice_paid(invoice_id, not bool(inv['paid']))
        inv = db.get_invoice(invoice_id)
        return render_template('invoice_detail.html', invoice=inv, mailto=_build_mailto(inv))

    # ---- Settings page ----
    @app.get('/settings')
    def settings():
        subject = db.get_setting('invoice_subject') or 'Coffee Invoice {period_start} - {period_end}'
        body = db.get_setting('invoice_body') or 'Dear {user_display}, this is your invoice for the billing period {period_start} until {period_end}. Total coffees: {total_items}, price per coffee: {price_per_coffee}, total price: {total_price}. Thank you!'
        price = db.get_setting('price_per_coffee') or '0.00'
        from datetime import datetime
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return render_template('settings.html', subject=subject, body=body, price=price, current_time=current_time)

    @app.post('/settings')
    def save_settings():
        subject = request.form.get('subject') or ''
        body = request.form.get('body') or ''
        price = request.form.get('price') or '0'
        new_time = (request.form.get('system_time') or '').strip()
        try:
            _ = float(price)
        except ValueError:
            return render_template('message.html', title='Invalid Price', message='Please enter a valid number for price.'), 400
        db.set_setting('invoice_subject', subject)
        db.set_setting('invoice_body', body)
        db.set_setting('price_per_coffee', price)
        # Handle optional system time update
        if new_time:
            from datetime import datetime
            import subprocess
            # Validate format strictly as 'YYYY-MM-DD HH:MM:SS'
            try:
                _ = datetime.strptime(new_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return render_template('message.html', title='Invalid Time', message='Time must be in format YYYY-MM-DD HH:MM:SS.'), 400
            # Try to set time using date -s (works on Linux); if not permitted, attempt sudo -n
            commands_to_try = [
                ['date', '-s', new_time],
                ['sudo', '-n', 'date', '-s', new_time],
            ]
            set_ok = False
            error_msg = ''
            for cmd in commands_to_try:
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        set_ok = True
                        break
                    else:
                        error_msg = (res.stderr or res.stdout or '').strip()
                except Exception as e:
                    error_msg = str(e)
            if not set_ok:
                return render_template('message.html', title='Time Not Set', message=f'Failed to set system time. {error_msg or "Insufficient privileges."}'), 500
        return render_template('message.html', title='Saved', message='Settings saved successfully.')

    # ---- Scan Mode: settings helpers ----
    def _get_scan_mode_enabled() -> bool:
        val = db.get_setting('scan_mode')
        return str(val) == '1'

    def _set_scan_mode_enabled(enabled: bool) -> None:
        db.set_setting('scan_mode', '1' if enabled else '0')

    # ---- Scan Mode pages and APIs ----
    # Backward compatibility: keep route but redirect to Administration
    @app.get('/scan-mode')
    def scan_mode():
        from flask import redirect, url_for
        return redirect(url_for('administration'))

    @app.get('/administration')
    def administration():
        # list all users, editable
        users = db.get_all_users()
        return render_template('administration.html', scan_enabled=_get_scan_mode_enabled(), users=users)

    @app.post('/scan-mode/toggle')
    def toggle_scan_mode():
        enabled = request.form.get('enabled')
        if enabled is None:
            # allow JSON too
            try:
                data = request.get_json(silent=True) or {}
                enabled = data.get('enabled')
            except Exception:
                enabled = None
        new_state = str(enabled) in ['1', 'true', 'True', 'on']
        _set_scan_mode_enabled(new_state)
        # When enabling scan mode, ensure new tokens are barred by default (handled in controller/db write)
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({"scan_mode": new_state})
        return redirect(url_for('scan_mode'))

    @app.get('/api/scan-mode/status')
    def api_scan_status():
        return jsonify({"scan_mode": _get_scan_mode_enabled()})

    @app.get('/api/scan-mode/last')
    def api_scan_last():
        # Return only a fresh scan event while scan mode is enabled; ignore historical values
        from datetime import datetime, timedelta
        # If scan mode is disabled, never surface a token
        if str(db.get_setting('scan_mode')) != '1':
            return jsonify({"token": "", "timestamp": ""})
        token = db.get_setting('last_scanned_token') or ''
        ts = db.get_setting('last_scanned_at') or ''
        # Freshness window: only consider scans from the last 5 seconds
        FRESH_WINDOW_SECONDS = 5
        is_fresh = False
        if ts:
            try:
                scanned_at = None
                # Try ISO format first
                try:
                    scanned_at = datetime.fromisoformat(str(ts))
                except Exception:
                    scanned_at = None
                # Fallbacks for common SQLite string formats
                if scanned_at is None:
                    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                        try:
                            scanned_at = datetime.strptime(str(ts), fmt)
                            break
                        except Exception:
                            continue
                if scanned_at is not None:
                    is_fresh = datetime.now() - scanned_at <= timedelta(seconds=FRESH_WINDOW_SECONDS)
            except Exception:
                is_fresh = False
        # If not fresh, do not surface any token
        if not is_fresh:
            return jsonify({"token": "", "timestamp": ""})
        return jsonify({"token": token, "timestamp": ts})

    @app.get('/api/scan-mode/pending')
    def api_scan_pending():
        # kept for compatibility; return users with missing essentials
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT token_id, user_name, name, email_address, phone_number, barred, active, created_at
                FROM users
                WHERE (user_name IS NULL OR user_name = '' OR name IS NULL OR name = '')
                ORDER BY created_at DESC
                """
            )
            return jsonify([dict(r) for r in cur.fetchall()])

    @app.get('/api/admin/users')
    def api_admin_users():
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT token_id, user_name, name, email_address, phone_number, barred, active, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            return jsonify([dict(r) for r in cur.fetchall()])

    @app.post('/api/admin/user')
    def api_admin_add_user():
        payload = request.get_json(force=True, silent=True) or {}
        token_id = (payload.get('token_id') or '').strip()
        if not token_id:
            return jsonify({"ok": False, "error": "token_id required"}), 400
        # Ensure user exists (pending), then update allowed fields if provided
        db.add_pending_user(token_id)
        allowed = {k: v for k, v in payload.items() if k in ['user_name','name','email_address','phone_number','barred','active']}
        # If both key fields provided, default to active and unbarred unless specified
        if (allowed.get('user_name') or '').strip() and (allowed.get('name') or '').strip():
            allowed.setdefault('active', 1)
            allowed.setdefault('barred', 0)
        if allowed:
            db.update_user(token_id, **allowed)
        user = db.get_user(token_id) or {}
        return jsonify({"ok": True, "user": user})

    @app.post('/api/scan-mode/user/<token_id>')
    def api_update_user(token_id: str):
        payload = request.get_json(force=True, silent=True) or {}
        # Only allow specific fields
        allowed = {k: v for k, v in payload.items() if k in ['user_name', 'name', 'email_address', 'phone_number', 'barred', 'active']}
        # If user_name and name are both provided and non-empty, automatically set active=1 and barred=0 unless explicitly set
        if 'user_name' in allowed and 'name' in allowed and allowed.get('user_name') and allowed.get('name'):
            allowed.setdefault('active', 1)
            allowed.setdefault('barred', 0)
        updated = db.update_user(token_id, **allowed)
        if not updated:
            return jsonify({"ok": False}), 400
        user = db.get_user(token_id) or {}
        return jsonify({"ok": True, "user": user})

    return app


if __name__ == '__main__':
    app = create_app()
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host=host, port=port, debug=debug)


