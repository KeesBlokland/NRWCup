"""
NRW Cup Scoring System - Database Viewer v1.1
Location: database_viewer.py
"""

from flask import Flask, render_template_string
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
import os

# Initialize Flask app
app = Flask(__name__)

# Ensure we're pointing to the correct database location
DB_PATH = os.path.join('instance', 'NRWCup2025.db')
if not os.path.exists(DB_PATH):
    raise FileNotFoundError(f"Database not found at {DB_PATH}. Please run setup_database.py first.")

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Define basic HTML template for displaying data
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NRW Cup Database Viewer</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin-bottom: 20px;
            font-size: 14px;
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        th { 
            background-color: #f2f2f2;
            position: sticky;
            top: 0;
        }
        tr:nth-child(even) { 
            background-color: #f9f9f9; 
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        h1 { 
            color: #333;
            margin-bottom: 20px;
        }
        .table-container {
            overflow-x: auto;
            margin-top: 20px;
        }
        .menu {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        .menu a {
            text-decoration: none;
            padding: 5px 10px;
            background-color: #f2f2f2;
            color: #333;
            border-radius: 4px;
        }
        .menu a:hover {
            background-color: #e0e0e0;
        }
        .error {
            color: red;
            padding: 10px;
            border: 1px solid red;
            background-color: #fff8f8;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <h1>NRW Cup Database Viewer</h1>
    <div class="menu">
        <a href="/">Home</a>
        {% for table in tables %}
            <a href="/view/{{ table }}">{{ table }}</a>
        {% endfor %}
    </div>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    {% if data %}
        <h2>Table: {{ table_name }}</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        {% for col in columns %}
                            <th>{{ col }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for row in data %}
                        <tr>
                            {% for cell in row %}
                                <td title="{{ cell }}">{{ cell }}</td>
                            {% endfor %}
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% if data|length == 0 %}
            <p>No data in this table.</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        return render_template_string(HTML_TEMPLATE, 
                                   tables=sorted(tables), 
                                   data=None, 
                                   error=None)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
                                    tables=[], 
                                    data=None, 
                                    error=f"Error accessing database: {str(e)}")

@app.route("/view/<table_name>")
def view_table(table_name):
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if table_name not in tables:
            return render_template_string(HTML_TEMPLATE, 
                                       tables=sorted(tables), 
                                       data=None, 
                                       error=f"Table '{table_name}' does not exist")
        
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        
        with db.engine.connect() as connection:
            result = connection.execute(text(f"SELECT * FROM {table_name}"))
            data = [row for row in result]
        
        return render_template_string(
            HTML_TEMPLATE,
            tables=sorted(tables),
            data=data,
            table_name=table_name,
            columns=columns,
            error=None
        )
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
                                    tables=sorted(tables), 
                                    data=None, 
                                    error=f"Error viewing table: {str(e)}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)