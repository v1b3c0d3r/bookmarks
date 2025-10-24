import sqlite3
import uvicorn
import logging
import os
import re
import requests

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from urllib.parse import urljoin, urlparse


# --- Configuration ---
DATABASE_FILE = "data/bookmarks.db" if os.path.exists('data') else 'bookmarks.db'
LOG_FMT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


# --- Database Setup ---
def init_db():
    """Initializes the database and creates tables if they don't exist."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        # Create folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                is_open BOOLEAN DEFAULT 0,
                position INTEGER,
                FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        """)
        # Create bookmarks tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                folder_id INTEGER,
                position INTEGER,
                FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favicons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_type TEXT NOT NULL,
                favicon BLOB,
                bookmark_id INTEGER,
                FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS bookmark_idx ON favicons(bookmark_id)")
        conn.commit()


# --- Pydantic Models (for data validation and serialization) ---
class Bookmark(BaseModel):
    id: int
    name: str
    url: str
    folderId: Optional[int] = Field(alias='folderId')
    position: Optional[int] = None


class Folder(BaseModel):
    id: int
    name: str
    parentId: Optional[int] = Field(alias='parentId')
    isOpen: bool = Field(alias='isOpen')
    position: Optional[int] = None


class AppData(BaseModel):
    bookmarks: List[Bookmark]
    folders: List[Folder]


class BookmarkCreate(BaseModel):
    name: str
    url: str
    folderId: int = Field(alias='folderId')


class FolderCreate(BaseModel):
    name: str
    parentId: Optional[int] = Field(alias='parentId')


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    parentId: Optional[int] = Field(alias='parentId', default=None)
    folderId: Optional[int] = Field(alias='folderId', default=None)
    isOpen: Optional[bool] = Field(alias='isOpen', default=None)


class ReorderRequest(BaseModel):
    ids: List[int]


def retrieve_favicon(url: str) -> Tuple[str, bytes]:
    if url is None: return None, None
    try:
        # Try retrieving the HTML
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        # Regex to find favicon URL from link rel attributes
        match = re.search(r'<link[^>]+rel=["\'](?:shortcut\s+icon|icon)["\'][^>]+>', response.text, re.IGNORECASE)
        if match:
            href_match = re.search(r'href=["\'](.*?)["\']', match.group(0), re.IGNORECASE)
            if href_match:
                favicon_href = href_match.group(1)
                favicon_url = urljoin(url, favicon_href)  # Handle relative URLs
                # Fetch favicon
                fav_resp = requests.get(favicon_url, timeout=5)
                fav_resp.raise_for_status()
                image_type = fav_resp.headers.get('content-type')
                logging.info(f'Retrieved favicon {image_type}: {url}')
                return image_type, fav_resp.content
    except Exception:
        pass  # If any step above fails, fall back to Google
    try:
        # Extract hostname for Google service
        hostname = urlparse(url).hostname
        google_favicon_url = f"https://www.google.com/s2/favicons?domain={hostname}&sz=48"
        fav_resp = requests.get(google_favicon_url, timeout=5, allow_redirects=True)
        fav_resp.raise_for_status()
        image_type = fav_resp.headers.get('content-type')
        logging.info(f'Retrieved favicon from Google: {hostname}')
        return image_type, fav_resp.content
    except Exception:
        return None, None
    pass


# --- FastAPI App Initialization ---
def config_access_log_to_show_time():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FMT))
    logger = logging.getLogger("uvicorn.access")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger = logging.getLogger("uvicorn.error")
    logger.handlers.clear()
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_access_log_to_show_time()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Helper function to convert tuple to dict ---
def dict_factory(cursor, row):
    """Converts database query results (tuples) into dictionaries."""
    d = {}
    for idx, col in enumerate(cursor.description):
        # Convert snake_case from DB to camelCase for JS
        camel_case_key = ''.join(word.capitalize() for word in col[0].split('_'))
        camel_case_key = camel_case_key[0].lower() + camel_case_key[1:]
        d[camel_case_key] = row[idx]
    return d


# --- API Endpoints ---
@app.get("/api/data", response_model=AppData)
def get_all_data():
    """Fetches all folders and bookmarks from the database."""
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, parent_id, is_open, position FROM folders ORDER BY position")
            folders = cursor.fetchall()
            cursor.execute("SELECT id, name, url, folder_id, position FROM bookmarks ORDER BY position")
            bookmarks = cursor.fetchall()
            return {"folders": folders, "bookmarks": bookmarks}
    except Exception as e:
        logging.error(f"Error fetching data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bookmarks", response_model=Bookmark, status_code=201)
def create_bookmark(bookmark: BookmarkCreate):
    favicon_type, favicon_data = retrieve_favicon(bookmark.url)
    """Creates a new bookmark."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM bookmarks WHERE folder_id = ?", (bookmark.folderId,))
        count = cursor.fetchone()
        position = count['count'] if count else 0
        cursor.execute(
            "INSERT INTO bookmarks (name, url, folder_id, position) VALUES (?, ?, ?, ?)",
            (bookmark.name, bookmark.url, bookmark.folderId, position)
        )
        new_id = cursor.lastrowid
        if favicon_type is not None:
            cursor.execute(
                "INSERT INTO favicons (content_type, favicon, bookmark_id) VALUES (?, ?, ?)",
                (favicon_type, favicon_data, new_id)
            )
        conn.commit()
        cursor.execute("SELECT id, name, url, folder_id, position FROM bookmarks WHERE id = ?", (new_id,))
        return cursor.fetchone()


@app.post("/api/folders", response_model=Folder, status_code=201)
def create_folder(folder: FolderCreate):
    """Creates a new folder."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        if folder.parentId is None:
            cursor.execute("SELECT COUNT(*) as count FROM folders WHERE parent_id IS NULL")
        else:
            cursor.execute("SELECT COUNT(*) as count FROM folders WHERE parent_id = ?", (folder.parentId,))
        count = cursor.fetchone()
        position = count['count'] if count else 0
        cursor.execute(
            "INSERT INTO folders (name, parent_id, is_open, position) VALUES (?, ?, 0, ?)",
            (folder.name, folder.parentId, position)
        )
        new_id = cursor.lastrowid
        conn.commit()
        cursor.execute("SELECT id, name, parent_id, is_open, position FROM folders WHERE id = ?", (new_id,))
        return cursor.fetchone()


@app.post("/api/items/{item_type}/reorder", status_code=200)
def reorder_items(item_type: str, reorder: ReorderRequest):
    """Reorders items within a container."""
    if item_type not in ["folders", "bookmarks"]:
        raise HTTPException(status_code=400, detail="Invalid item type")
    table = "folders" if item_type == "folders" else "bookmarks"
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        for i, item_id in enumerate(reorder.ids):
            cursor.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (i, item_id))
        conn.commit()
        return {"status": "success"}


@app.put("/api/items/{item_type}/{item_id}")
def update_item(item_type: str, item_id: int, item: ItemUpdate):
    """Updates a folder or a bookmark. Handles renaming, moving, and opening/closing."""
    if item_type not in ["folders", "bookmarks"]:
        raise HTTPException(status_code=400, detail="Invalid item type")
    table = "folders" if item_type == "folders" else "bookmarks"
    parent_column = "parent_id" if item_type == "folders" else "folder_id"
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        if item_type == "folders":
            # For moving a folder, we update parent_id. For renaming, we update name.
            if item.name is not None:
                cursor.execute("UPDATE folders SET name = ? WHERE id = ?", (item.name, item_id))
            if item.parentId is not None or item.parentId == 0: # 0 will be used to move to root
                if not item.parentId:
                    cursor.execute("SELECT COUNT(*) as count FROM folders WHERE parent_id IS NULL")
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM folders WHERE parent_id = ?", (item.parentId,))
                count = cursor.fetchone()
                position = count['count'] if count else 0
                actual_parent_id = item.parentId if item.parentId != 0 else None
                cursor.execute("UPDATE folders SET parent_id = ?, position = ? WHERE id = ?", (actual_parent_id, position, item_id))
            if item.isOpen is not None:
                cursor.execute("UPDATE folders SET is_open = ? WHERE id = ?", (item.isOpen, item_id))
        elif item_type == "bookmarks":
            favicon_type, favicon_data = retrieve_favicon(item.url)
            # For moving a bookmark, we update folder_id. For renaming, we update name/url.
            if item.name is not None:
                cursor.execute("UPDATE bookmarks SET name = ? WHERE id = ?", (item.name, item_id))
            if item.url is not None:
                cursor.execute("UPDATE bookmarks SET url = ? WHERE id = ?", (item.url, item_id))
                if favicon_type is not None:
                    cursor.execute(
                        "INSERT OR REPLACE INTO favicons (content_type, favicon, bookmark_id) VALUES (?, ?, ?)",
                        (favicon_type, favicon_data, item_id)
                    )
            if item.folderId is not None:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table} WHERE {parent_column} = ?", (item.folderId,))
                count = cursor.fetchone()
                position = count['count'] if count else 0
                cursor.execute("UPDATE bookmarks SET folder_id = ?, position = ? WHERE id = ?", (item.folderId, position, item_id))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"status": "success", "id": item_id}


@app.delete("/api/items/{item_type}/{item_id}", status_code=204)
def delete_item(item_type: str, item_id: int):
    """Deletes a folder or bookmark. Deleting a folder also deletes its contents."""
    if item_type not in ["folders", "bookmarks"]:
        raise HTTPException(status_code=400, detail="Invalid item type")
        
    with sqlite3.connect(DATABASE_FILE) as conn:
        # Enable foreign key support for cascading deletes
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        table = "folders" if item_type == "folders" else "bookmarks"
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        return


@app.get("/api/favicon/{bookmark_id}", response_class=Response)
def get_favicon(bookmark_id: int):        
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content_type, favicon FROM favicons WHERE bookmark_id = ? LIMIT 1", (bookmark_id,))
        row = cursor.fetchone()
        if row:  # Found in DB
            content_type, favicon_bytes = row
            return Response(content=favicon_bytes, media_type=content_type)
        else:  # Not found, serve default file
            return FileResponse("static/weblink.png", media_type="image/png")
    pass


# --- Static Frontend Serving ---
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the main index.html file."""
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/sw.js", response_class=FileResponse)
async def read_service_worker():
    return FileResponse("static/sw.js", media_type="text/javascript")


# --- Main Execution ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOG_FMT)
    logger = logging.getLogger(__name__)
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting server at http://0.0.0.0:8000")
    # To run this app, use the command: uvicorn main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)


