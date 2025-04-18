# Cosmali Loader

Cosmali is a stealthy client management and control panel designed to deploy and manage PowerShell-based payloads across multiple machines. It provides real-time monitoring, scripting capabilities, and statistical insights for your agents.

## Features

- Secure HTTPS communication with self-signed certificates
- Automatic client registration and heartbeats
- Configurable ping intervals and timeout for payload jobs
- Global and per-client script execution with CodeMirror-powered editors
- Real-time dashboard displaying active clients, memory usage, and last activity
- Interactive world map for client geolocation using Leaflet and MarkerCluster
- Advanced statistics charts (user activity, country distribution, registration trends, script status) via Chart.js
- Payload builder to customize, download, or copy raw/Base64 PowerShell loaders
- WebSocket-driven live updates for dashboard and statistics
- Rate limiting and IP blacklist support
- SQLite database with async via aiosqlite
- System resource monitoring with psutil
- Full pagination, search, and sorting utilities

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Cosmali.git
   cd Cosmali
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Generate SSL certificates (in project root):
   ```bash
   python generate_certificates.py --certfile cert.pem --keyfile key.pem
   ```

5. (Optional) Populate test database:
   ```bash
   python generate_test_db.py
   ```

6. Configure server settings in `settings.py` (host, port, SSL paths, auto-load options).

## Usage

Start the Quart application using Hypercorn:
```bash
hypercorn main:app --bind 0.0.0.0:5000 --certfile cert.pem --keyfile key.pem
```
Open your browser and navigate to `https://localhost:5000` to access the UI.

### Key Sections

- **Dashboard**: View connected clients, memory/cpu stats, last ping times.
- **Payload Builder**: Generate custom PowerShell loaders and download or copy them.
- **Global Scripts**: Manage and execute scripts on one or multiple clients.
- **Client Scripts**: Assign scripts to individual clients from the dashboard.
- **Map**: Visualize client locations on an interactive map.
- **Statistics**: Explore charts for user activity, script execution statuses, and geographic distribution.

## Project Structure

```
├── main.py                # Application entry point
├── config.py              # App configuration and settings
├── routes/                # HTTP route handlers (dashboard, map, scripts, statistics, builder)
├── static/                # CSS and JS assets (base styles, components, dashboard logic)
├── templates/             # Jinja2 HTML templates for each page
├── util/                  # Helper modules (pagination, rate limiting, db queries, time formatting)
├── websocket/             # WebSocket server and real-time update logic
├── payload/               # PowerShell payload and modules
└── requirements.txt       # Python dependencies
```

## License

This project is licensed under the Apache License 2.0. See `LICENSE` for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for bug fixes or enhancements.
