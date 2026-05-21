from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from functions.database import User
from functions.base import get_db_session
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide username and password.', 'danger')
            return render_template('auth/login.html')

        db = get_db_session()
        try:
            user = db.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()

            if not user or not user.check_password(password):
                flash('Invalid username or password.', 'danger')
                return render_template('auth/login.html')

            if not user.is_active:
                flash('Your account has been deactivated.', 'danger')
                return render_template('auth/login.html')

            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()

            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))

        except Exception as e:
            db.rollback()
            flash(f'Login error: {str(e)}', 'danger')
            return render_template('auth/login.html')
        finally:
            db.close()

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
