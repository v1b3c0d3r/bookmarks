# Bookmark Manager

A simple, self-hosted bookmark manager built with Python, FastAPI, and a static HTML/JS frontend.

## Functionality

*   **Organize bookmarks:** Create and manage bookmarks and folders.
*   **Drag-and-drop interface:** Easily reorder bookmarks and folders.
*   **Favicon support:** Automatically fetches and displays favicons for your bookmarks.
*   **SQLite database:** All data is stored in a simple SQLite database file.
*   **Dockerized:** Ready for easy deployment with Docker.

## Building and Deploying with Docker

This application is designed to be deployed using Docker.

### Prerequisites

*   [Docker](https://docs.docker.com/get-docker/) installed on your machine.

### Building the Docker Image

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Build the Docker image:**
    ```bash
    docker build -t bookmark-manager .
    ```

### Running the Docker Container

1.  **Create a data directory:**
    This directory will be used to persist the SQLite database file.
    ```bash
    mkdir -p data
    ```

2.  **Run the Docker container:**
    ```bash
    docker run -d \
      -p 8000:8000 \
      -v $(pwd)/data:/data \
      --name bookmark-manager \
      bookmark-manager
    ```

    This command will:
    *   Run the container in detached mode (`-d`).
    *   Map port 8000 of the host to port 8000 of the container (`-p 8000:8000`).
    *   Mount the `data` directory on the host to the `/data` directory in the container (`-v $(pwd)/data:/data`).
    *   Name the container `bookmark-manager` for easy reference.

3.  **Access the application:**
    Open your web browser and navigate to `http://localhost:8000`.

### Initializing the Database

The first time you run the application, you need to initialize the database.

1.  **Find the container ID:**
    ```bash
    docker ps
    ```

2.  **Execute the `init_db` function:**
    ```bash
    docker exec -it <container-id> python3 -c "from main import init_db; init_db()"
    ```

    Alternatively, you can run the `main.py` script directly, which will also initialize the database:
    ```bash
    docker exec -it <container-id> python3 main.py
    ```

    After initializing the database, you can stop the container and restart it using the `docker run` command above.
