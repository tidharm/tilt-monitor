# Tilt Monitor

Tilt Monitor is a macOS menu bar application that provides real-time status monitoring for [Tilt](https://tilt.dev/), a development environment tool. It allows you to quickly see the status of your Tilt resources and perform common operations like starting and stopping Tilt.

## Installation

### From Source

1. Clone the repository:
   ```
   git clone https://github.com/tidharm/tilt-monitor.git
   cd tilt-monitor
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install the package in development mode:
   ```
   pip install -e .
   ```

4. Run the application:
   ```
   tilt-monitor
   ```

### Build macOS App

To build a standalone macOS application:

1. Clone the repository and set up the virtual environment as described above.

2. Run the build script:
   ```
   python build.py
   ```

3. The packaged application will be available in the `package/Tilt Monitor.app` directory.

## Usage

- The menu bar icon shows the current status of Tilt:
  - Green: All resources are healthy
  - Red: One or more resources have errors
  - Gray: Tilt is starting or in a pending state
  - Transparent: Tilt is not running

- Click on the icon to access the menu:
  - Start/Stop Tilt
  - Open Tilt UI in browser
  - Edit configuration
  - View logs

## Configuration

The configuration file is stored at:
- When run as a packaged app: `~/Library/Application Support/TiltMonitor/tilt_monitor_config.json`
- When run from source: In the project directory

Configuration options:
- `keepalive_interval`: Time interval in seconds for status checks when Tilt is running
- `sleep_interval`: Time interval in seconds for status checks when Tilt is down
- `tilt_base_url`: URL for the Tilt API
- `tilt_file_path`: **(Required)** Path to your `Tiltfile` or the directory that contains it
- `tilt_context`: Kubernetes context to use
- `tilt_cmd_args`: Additional command-line arguments for Tilt

## License

See the [LICENSE](LICENSE) file for details.

## Disclaimer

[Tilt](https://tilt.dev/) is a trademark of its respective owner. [Tilt Monitor](https://github.com/tidharm/tilt-monitor) is an independent project and is not affiliated with, endorsed by, or sponsored by [Tilt](https://tilt.dev/) or the [Tilt.dev](https://github.com/tilt-dev) team.  
The use of the **Tilt** name and associated branding elements (including iconography) is solely for identification and compatibility purposes, in accordance with nominative fair use principles. I make no claim to any rights in the **Tilt** name or logo.

If you are a rights holder and believe that any usage in this project violates your intellectual property or trademark rights, please contact me. I am committed to acting in good faith and will promptly address any concerns — including providing attribution, modifying the materials, or removing them if necessary.

 
