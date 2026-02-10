import os

# Define the project structure and content
project_structure = {
    "app.py": """from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from participants import participants

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///NRWCup2025.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
app.register_blueprint(participants, url_prefix='/participants')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
""",
    "participants.py": """from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from models import Teilnehmer

participants = Blueprint('participants', __name__, template_folder='templates/participants')

@participants.route('/')
def view_participants():
    participants = Teilnehmer.query.all()
    return render_template('view.html', participants=participants)

@participants.route('/add', methods=['GET', 'POST'])
def add_participant():
    if request.method == 'POST':
        new_participant = Teilnehmer(
            name=request.form['name'],
            email=request.form.get('email', ''),
            handy=request.form.get('handy', '')
        )
        db.session.add(new_participant)
        db.session.commit()
        return redirect(url_for('participants.view_participants'))
    return render_template('add.html')

@participants.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_participant(id):
    participant = Teilnehmer.query.get_or_404(id)
    if request.method == 'POST':
        participant.name = request.form['name']
        participant.email = request.form.get('email', '')
        participant.handy = request.form.get('handy', '')
        db.session.commit()
        return redirect(url_for('participants.view_participants'))
    return render_template('edit.html', participant=participant)

@participants.route('/delete/<int:id>', methods=['POST'])
def delete_participant(id):
    participant = Teilnehmer.query.get_or_404(id)
    db.session.delete(participant)
    db.session.commit()
    return redirect(url_for('participants.view_participants'))
""",
    "models.py": """from app import db

class Teilnehmer(db.Model):
    __tablename__ = 'teilnehmer'
    teilnehmer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), default="")
    handy = db.Column(db.String(20), default="")
""",
    "templates/participants/view.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>View Participants</title>
</head>
<body>
    <h1>Participants</h1>
    <a href="{{ url_for('participants.add_participant') }}">Add Participant</a>
    <table border="1">
        <thead>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Handy</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for participant in participants %}
            <tr>
                <td>{{ participant.teilnehmer_id }}</td>
                <td>{{ participant.name }}</td>
                <td>{{ participant.email }}</td>
                <td>{{ participant.handy }}</td>
                <td>
                    <a href="{{ url_for('participants.edit_participant', id=participant.teilnehmer_id) }}">Edit</a>
                    <form action="{{ url_for('participants.delete_participant', id=participant.teilnehmer_id) }}" method="post" style="display:inline;">
                        <button type="submit">Delete</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
""",
    "templates/participants/add.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Add Participant</title>
</head>
<body>
    <h1>Add Participant</h1>
    <form method="post">
        <label for="name">Name:</label>
        <input type="text" id="name" name="name" required><br>
        <label for="email">Email:</label>
        <input type="email" id="email" name="email"><br>
        <label for="handy">Handy:</label>
        <input type="text" id="handy" name="handy"><br>
        <button type="submit">Add</button>
    </form>
    <a href="{{ url_for('participants.view_participants') }}">Back</a>
</body>
</html>
""",
    "templates/participants/edit.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Edit Participant</title>
</head>
<body>
    <h1>Edit Participant</h1>
    <form method="post">
        <label for="name">Name:</label>
        <input type="text" id="name" name="name" value="{{ participant.name }}" required><br>
        <label for="email">Email:</label>
        <input type="email" id="email" name="email" value="{{ participant.email }}"><br>
        <label for="handy">Handy:</label>
        <input type="text" id="handy" name="handy" value="{{ participant.handy }}"><br>
        <button type="submit">Update</button>
    </form>
    <a href="{{ url_for('participants.view_participants') }}">Back</a>
</body>
</html>
""",
}

# Create files and folders, skipping existing files
for path, content in project_structure.items():
    if os.path.exists(path):
        print(f"Skipped: {path} (already exists)")
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            file.write(content)
        print(f"Created: {path}")

print("Project structure setup complete!")
