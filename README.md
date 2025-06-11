# Tilt Monitor

Tilt Monitor is a macOS menu bar application that provides real-time status monitoring for [Tilt](https://tilt.dev/). It replicates Tilt's favicon status colors, allows you basic control over Tilt's status (start/stop), and to quickly access the Tilt dashboard to view your resources' status.

## Features

- **Dynamic Menu Bar Icon**: Real-time status monitoring with a dynamically colored icon that reflects the state of your Tilt environment.
- **Graceful Process Management**: Starts and stops the Tilt daemon gracefully using `tilt up` and `tilt down`.
- **Easy Configuration**: Configure the app via a simple JSON file, with a menu option to open it directly.

## Installation

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

4. Run the build script:
   ```
   python build.py
   ```

   The packaged application will be available in the `package/Tilt Monitor.app` directory (it is recomended to move it to the `/Applications` directory).

## Usage

- The menu bar icon shows the current status of Tilt:
  - **Green**: All resources are healthy.
  - **Red**: One or more resources have errors.
  - **Gray**: Tilt is starting or in a pending state.
  - **Transparent**: Tilt is not running.

- Click on the icon to access the menu:
  - **Tilt Up / Tilt Down**: Start or stop the Tilt daemon.
  - **Open Tilt UI**: Open the Tilt web interface in your default browser.
  - **Edit Configuration**: Open the configuration file in your default editor.
  - **Reload**: Reload the application to apply configuration changes.
  - **Show Log**: Open the application's log file.
  - **About**: Display the application's version and description.

## Configuration

The configuration file is stored at `~/Library/Application Support/TiltMonitor/tilt_monitor_config.json` regardless of whether the app is run from source or as a packaged `.app` bundle.

Configuration options:
- `keepalive_interval`: Time interval in seconds for status checks when Tilt is running.
- `sleep_interval`: Time interval in seconds for status checks when Tilt is down.
- `tilt_base_url`: URL for the Tilt API.
- `tilt_file_path`: **(Required)** Path to your `Tiltfile` or the directory that contains it.
- `tilt_context`: Kubernetes context to use with Tilt.
- `tilt_cmd_args`: Additional command-line arguments for the `tilt up` command.

## License

See the [LICENSE](LICENSE) file for details.

## Disclaimer

[Tilt](https://tilt.dev/) is a trademark of its respective owner. [Tilt Monitor](https://github.com/tidharm/tilt-monitor) is an independent project and is not affiliated with, endorsed by, or sponsored by [Tilt](https://tilt.dev/) or the [Tilt.dev](https://github.com/tilt-dev) team.
The use of the **Tilt** name and associated branding elements (including iconography) is solely for identification and compatibility purposes, in accordance with nominative fair use principles. I make no claim to any rights in the **Tilt** name or logo.

If you are a rights holder and believe that any usage in this project violates your intellectual property or trademark rights, please contact me. I am committed to acting in good faith and will promptly address any concerns — including providing attribution, modifying the materials, or removing them if necessary.

 
