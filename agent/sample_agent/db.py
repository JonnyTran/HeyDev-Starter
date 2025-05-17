"""
Database setup script for the DevRel publisher agent.
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """
    Create and return a database connection using environment variables.
    """
    db_url = os.getenv("POSTGRESQL_URL")
    if not db_url:
        raise ValueError("POSTGRESQL_URL environment variable not set")
    
    return psycopg2.connect(db_url)

def setup_database():
    """
    Create the necessary database tables if they don't exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create the content table based on the schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                channel TEXT,
                title TEXT,
                summary TEXT,
                content TEXT,
                type TEXT
            )
        """)
        
        conn.commit()
        print("Database tables created successfully.")
    except Exception as e:
        print(f"Database setup error: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def insert_content(content_record):
    """
    Insert a content record into the database.
    
    Args:
        content_record (dict): Dictionary with keys matching the content table columns
    
    Returns:
        int: ID of the inserted record
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = """
            INSERT INTO content (channel, title, summary, content, type)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        
        cursor.execute(
            query, 
            (
                content_record["channel"],
                content_record["title"],
                content_record["summary"],
                content_record["content"],
                content_record["type"]
            )
        )
        
        content_id = cursor.fetchone()[0]
        conn.commit()
        
        return content_id
    except Exception as e:
        print(f"Database insertion error: {str(e)}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def get_content(content_id=None, content_type=None, limit=10):
    """
    Retrieve content records from the database.
    
    Args:
        content_id (int, optional): Specific content ID to retrieve
        content_type (str, optional): Filter by content type
        limit (int, optional): Maximum number of records to retrieve
    
    Returns:
        list: List of content records
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if content_id:
            query = "SELECT * FROM content WHERE id = %s"
            cursor.execute(query, (content_id,))
        elif content_type:
            query = "SELECT * FROM content WHERE type = %s ORDER BY id DESC LIMIT %s"
            cursor.execute(query, (content_type, limit))
        else:
            query = "SELECT * FROM content ORDER BY id DESC LIMIT %s"
            cursor.execute(query, (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        return results
    except Exception as e:
        print(f"Database query error: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Run database setup when script is executed directly
    setup_database() 