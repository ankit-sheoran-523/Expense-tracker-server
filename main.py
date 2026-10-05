from fastmcp import FastMCP
import os
import aiosqlite
import tempfile
import json

# DB_path=os.path.join(os.path.dirname(__file__),"expenses.db")
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp=FastMCP("expense Tracker")

def init_db():
    """Initialize the SQLite3 database.
    
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
        before any insert, update, or query operations are performed."""
    try:
        import sqlite3
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            # Test write access
            c.execute("INSERT OR IGNORE INTO expenses(date, amount, category) VALUES ('2000-01-01', 0, 'test')")
            c.execute("DELETE FROM expenses WHERE category = 'test'")
            print("Database initialized successfully with write access")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

init_db()


@mcp.tool()
async def add_expense(date:str, amount:float, category:str, subcategory:str="", note:str="")->dict:
    '''Add a new expense entry to the database.
    
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
            }'''
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute( 
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)
            )
            expense_id = cur.lastrowid
            await c.commit()
            return {"status": "success", "id": expense_id, "message": "Expense added successfully"}
    except Exception as e:
        if "readonly" in str(e).lower():
            return {"status": "error", "message": "Database is in read-only mode. Check file permissions."}
        return {"status": "error", "message": f"Database error: {str(e)}"}


@mcp.tool()
async def list_expenses(start_date, end_date):
    '''Retrieve all expense entries from the database.
    
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
                * note        → TEXT'''
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {str(e)}"}

@mcp.tool()
async def summarize(start_date:str,end_date:str, category:str=None):
    '''summarize expenses by category within an inclusive date range.
        - Connects to the SQLite database defined by DB_path.
        - Executes a SELECT query on the 'expenses' table.
        - Orders results ascending order.
        - Converts each row into a dictionary keyed by column names.
    
        Returns:
            list[dict]: A list of expense records, where each record has:
                * category    → TEXT
                * amount      → REAL'''
    try:
        async with aiosqlite.connect(DB_PATH) as c:  # Changed: added async
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cur = await c.execute(query, params)  # Changed: added await
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]  # Changed: added await
    except Exception as e:
        return {"status": "error", "message": f"Error summarizing expenses: {str(e)}"}


@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    try:
        default_categories = {
            "categories": [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Bills & Utilities",
                "Healthcare",
                "Travel",
                "Education",
                "Business",
                "Other"
            ]
        }
        
        try:
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            import json
            return json.dumps(default_categories, indent=2)
    except Exception as e:
        return f'{{"error": "Could not load categories: {str(e)}"}}'

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
    mcp.run(transport='streamable-http',port=8000,host='0.0.0.0')