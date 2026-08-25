import psycopg2
from psycopg2 import Error

def query_user(username, db_config):
    """
    Queries PostgreSQL for a user by username.
    Returns user tuple or None.
    """
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s;", (username,))
        result = cursor.fetchone()
        conn.close()
        return result  # return the user tuple directly
    except Error as e:
        print("Database error:", e)
        return None
