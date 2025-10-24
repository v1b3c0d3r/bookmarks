import sqlite3
import os

DATABASE_FILE = "data/bookmarks.db" if os.path.exists('data') else 'bookmarks.db'

def migrate():
    """
    Applies database schema changes.
    - Adds a 'position' column to 'folders' and 'bookmarks' tables for ordering.
    """
    print("Starting database migration...")
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()

            # --- Add 'position' to folders ---
            try:
                cursor.execute("ALTER TABLE folders ADD COLUMN position INTEGER")
                print("Added 'position' column to 'folders' table.")

                # --- Populate initial positions for folders ---
                print("Populating initial positions for existing folders...")
                cursor.execute("SELECT id, parent_id FROM folders ORDER BY id")
                folders = cursor.fetchall()

                # Group folders by parent_id
                folders_by_parent = {}
                for folder_id, parent_id in folders:
                    if parent_id not in folders_by_parent:
                        folders_by_parent[parent_id] = []
                    folders_by_parent[parent_id].append(folder_id)

                # Update positions within each group
                for parent_id, folder_ids in folders_by_parent.items():
                    for i, folder_id in enumerate(folder_ids):
                        cursor.execute("UPDATE folders SET position = ? WHERE id = ?", (i, folder_id))
                print("Folder positions populated.")

            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("'position' column already exists in 'folders' table. Skipping.")
                else:
                    raise

            # --- Add 'position' to bookmarks ---
            try:
                cursor.execute("ALTER TABLE bookmarks ADD COLUMN position INTEGER")
                print("Added 'position' column to 'bookmarks' table.")

                # --- Populate initial positions for bookmarks ---
                print("Populating initial positions for existing bookmarks...")
                cursor.execute("SELECT id, folder_id FROM bookmarks ORDER BY id")
                bookmarks = cursor.fetchall()

                # Group bookmarks by folder_id
                bookmarks_by_folder = {}
                for bookmark_id, folder_id in bookmarks:
                    if folder_id not in bookmarks_by_folder:
                        bookmarks_by_folder[folder_id] = []
                    bookmarks_by_folder[folder_id].append(bookmark_id)

                # Update positions within each group
                for folder_id, bookmark_ids in bookmarks_by_folder.items():
                    for i, bookmark_id in enumerate(bookmark_ids):
                        cursor.execute("UPDATE bookmarks SET position = ? WHERE id = ?", (i, bookmark_id))
                print("Bookmark positions populated.")

            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("'position' column already exists in 'bookmarks' table. Skipping.")
                else:
                    raise

            conn.commit()
            print("Migration completed successfully!")

    except Exception as e:
        print(f"An error occurred during migration: {e}")

if __name__ == "__main__":
    if os.path.exists(DATABASE_FILE):
        migrate()
    else:
        print("Database file not found. Skipping migration. The schema will be created on app startup.")
