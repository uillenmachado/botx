
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from ..models import User, db
from werkzeug.security import generate_password_hash
bp=Blueprint('auth',__name__)

@bp.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=request.form['username'];p=request.form['password']
        user=User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user);return redirect(url_for('core.index'))
        flash('Login inválido')
    return render_template('login.html')

@bp.route('/register',methods=['POST'])
def register():
    u=request.form['username'];p=request.form['password']
    user=User(username=u);user.set_password(p)
    db.session.add(user);db.session.commit()
    return redirect(url_for('auth.login'))

@bp.route('/logout')
@login_required
def logout():
    logout_user();return redirect(url_for('core.index'))
