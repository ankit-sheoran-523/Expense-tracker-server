import os
from fastmcp import FastMCP
import sqlite3,tempfile
import json

# DB_path=os.path.join(os.path.dirname(__file__),"expenses.db")
DB_path = os.path.join(tempfile.gettempdir(), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp=FastMCP("expense Tracker")

def init_db():
    """
    Initialize the SQLite3 database.

    - Connects to the database file defined by DB_path.
    - Creates a table named 'expenses' if it does not already exist.
    - The 'expenses' table stores financial records with the following fields:
        * id          → INTEGER PRIMARY KEY AUTOINCREMENT
        * date        → TEXT (required)
        * amount      → REAL (required)
        * category    → TEXT (required)
        * subcategory → TEXT (optional, defaults to empty string)
        * note        → TEXT (optional, defaults to empty string)

    This function ensures the database schema is ready for use
    before any insert, update, or query operations are performed.
    """
    with sqlite3.connect(DB_path) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            );
        """)
init_db()

@mcp.tool
def add_expense(date:str, amount:float, category:str, subcategory:str="", note:str="")->dict:
    """
    Add a new expense entry to the database.

    Parameters:
        date (str)        : Date of the expense (e.g., '2026-09-27').
        amount (float)    : Expense amount.
        category (str)    : Main category (e.g., 'Food', 'Transport').
        subcategory (str) : Optional subcategory (default empty string).
        note (str)        : Optional note or description (default empty string).

    Returns:
        dict: {
            'status': 'Ok',       # Operation result
            'id': <int>           # Auto-generated row ID of the inserted expense
        }
    """
    with sqlite3.connect(DB_path) as c:
        cur=c.execute(
                'Insert into expenses(date , amount, category, subcategory, note) Values (?,?,?,?,?)',(date,amount,category,subcategory,note)
                )
        return {'status':'Ok','id':cur.lastrowid}

@mcp.tool
def list_expenses():
    """
    Retrieve all expense entries from the database.

    - Connects to the SQLite database defined by DB_path.
    - Executes a SELECT query on the 'expenses' table.
    - Orders results by 'id' in ascending order.
    - Converts each row into a dictionary keyed by column names.

    Returns:
        list[dict]: A list of expense records, where each record has:
            * id          → INTEGER (auto-increment primary key)
            * date        → TEXT
            * amount      → REAL
            * category    → TEXT
            * subcategory → TEXT
            * note        → TEXT
    """
    with sqlite3.connect(DB_path) as c:
        cur = c.execute("SELECT * FROM expenses ORDER BY id ASC")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool
def summarize(start_date:str,end_date:str, category:str=None):
    """summarize expenses by category within an inclusive date range.
        - Connects to the SQLite database defined by DB_path.
        - Executes a SELECT query on the 'expenses' table.
        - Orders results ascending order.
        - Converts each row into a dictionary keyed by column names.
    
        Returns:
            list[dict]: A list of expense records, where each record has:
                * category    → TEXT
                * amount      → REAL
        """
    
    with sqlite3.connect(DB_path) as c:
        query=("""
            select category, SUM(amount) as total_amount 
            from expenses
            where date between ? and ?
""")
        params=[start_date,end_date]

        if category:
            query+=" and category = ?"
            params.append(category)

        query+= " group by category order by category asc"

        cur=c.execute(query,params)
        cols=[d[0] for d in cur.description]
        return [dict(zip(cols,r)) for r in cur.fetchall()]

@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

@mcp.resource("info://server")
def server_info()->str:
    """Get the info about this server."""
    info={
        "name":"Simple Expense Tracker",
        "version":"1.0.0",
        "description":"A basic MCP server with Expense Tracking methods",
        "tools":["add_expense","list_expenses",'summarize'],
        "author":"ABC-tester"
    }

    return json.dumps(info,indent=2)

if __name__=='__main__':
    mcp.run(transport='sse',port=8000,host='0.0.0.0')