from flask import Blueprint, render_template

participants = Blueprint('participants', __name__, template_folder='templates/participants')

@participants.route('/')
def index():
    return render_template('participants/index.html')
