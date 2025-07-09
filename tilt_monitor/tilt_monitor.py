import argparse
from datetime import datetime
import glob
import json
import os
from pathlib import Path
import rumps
import requests
import shutil
import subprocess
import sys
import traceback
import webbrowser

import Foundation


bundle = Foundation.NSBundle.mainBundle()
bundle_path = bundle.bundlePath()
info = bundle.infoDictionary() or {}
APP_NAME = info.get('CFBundleDisplayName', 'Tilt Monitor')
APP_VERSION = info.get('CFBundleShortVersionString', 'dev')
APP_DESCRIPTION = info.get('ASApplicationDescription', '')
APP_URL = info.get('ApplicationHomepageURL', '')

HOME = str(Path.home())
SHELL = os.environ.get('SHELL', '/bin/zsh')

# Config defaults
DEFAULT_CONFIG = {
    'tilt_file_path': '',  # supports both file path and parent dir (with or without '/Tiltfile')
    'tilt_base_url': 'http://localhost:10350',
    'tilt_context': 'docker-desktop',
    'keepalive_interval': 3,  # Interval for tilt status checks
    'sleep_interval': 30,  # Interval for status checks when tilt is down
    'tilt_cmd_args': '',  # For any other args other than -f and --context
    'env_vars': {}
}

# Paths
script_name = os.path.splitext(os.path.basename(__file__))[0]
int_app_name = APP_NAME.replace(' ', '')

main_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(HOME, 'Library', 'Application Support', f'{int_app_name}')  # Store config in a user-accessible location
os.chdir(main_dir)

# Paths - Directories
assets_dir = os.path.join(main_dir, 'assets')
log_dir = os.path.join(HOME, 'Library', 'Logs', int_app_name)

os.makedirs(config_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)

# Paths - Files
config_file = os.path.join(config_dir, f'{script_name}_config.json')
log_file = os.path.join(log_dir, f'{script_name}.log')
tmp_file_pfx = '/tmp/tilt_monitor_'

# Resources
gray_icon = os.path.join(assets_dir, 'gray.png')
green_icon = os.path.join(assets_dir, 'green.png')
red_icon = os.path.join(assets_dir, 'red.png')
transparent_icon = os.path.join(assets_dir, 'transparent.png')
default_icon = gray_icon

# Environment
_env = os.environ.copy()
os.environ.update({k: v for k, v in _env.items() if k.startswith('TMB_')})
terminal_env = None


def load_config():
    """Load configuration from file or create with defaults if it doesn't exist"""
    if not os.path.exists(config_file):
        # Create default config file
        cfg_json = json.dumps(DEFAULT_CONFIG, indent=4)
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(cfg_json)
        return DEFAULT_CONFIG
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        # Ensure all keys exist (in case config file is outdated)
        for key, value in DEFAULT_CONFIG.items():
            if key not in cfg:
                cfg[key] = value
                log(f'Key "{key}" not found in config file; Using default value: {value}', 'WARN')

        return cfg
    except Exception as load_err:
        log(f'Error loading config: {load_err}', 'ERROR', traceback.format_exc())
        return DEFAULT_CONFIG

# Load configuration
config = load_config()
keepalive_interval = config['keepalive_interval']
sleep_interval = config['sleep_interval']
tilt_base_url = config['tilt_base_url']
tilt_file_path = config['tilt_file_path']
tilt_context = config['tilt_context']
tilt_cmd_args = config['tilt_cmd_args']
custom_env_vars = config['env_vars']

# Variables
if tilt_file_path.endswith('Tiltfile'):
    tilt_file_path = os.path.dirname(tilt_file_path)

if tilt_context:
    tilt_cmd_args += f' --context {tilt_context}'

# App Settings
tilt_status_url = f'{tilt_base_url}/api/view?log=true'
tilt_ui_url = f'{tilt_base_url}/overview'

MENU_OPT_STATUS_SUMMARY = 'Status Summary'
MENU_OPT_OPEN_UI = 'Open Tilt UI'
MENU_OPT_TILT_UP = 'Tilt Up'
MENU_OPT_TILT_STARTING = 'Tilt Starting...'
MENU_OPT_TILT_DOWN = 'Tilt Down'
MENU_OPT_EDIT_CONFIG = 'Edit Configuration'
MENU_OPT_RELOAD = 'Reload'
MENU_OPT_SHOW_LOG = 'Show Log'
MENU_OPT_ABOUT = f'About {APP_NAME}'

parser = argparse.ArgumentParser(description='Tilt Status Menu Bar App')
parser.add_argument('-t', '--time-interval', type=int, default=None, help=f'Time interval in seconds for status check (default: {keepalive_interval})')
parser.add_argument('-u', '--up', action='store_true', help=f'Run `tilt up` command on startup')
parser.add_argument('--reloaded', action='store_true', help=argparse.SUPPRESS)

app = sys.modules[__name__]
app.tilt_healthy = None
app.tilt_running = None
app.tilt = 'tilt'  # default; will not work until environment variables are added


def ex(e):
    tb = traceback.extract_tb(e.__traceback__)
    frame = next((f for f in reversed(tb) if os.path.basename(f.filename) == f'{script_name}.py'), tb[-1])
    return f'{e.__class__.__name__}][{frame.name}:{frame.lineno}'


def log(value, log_level='INFO', exception=None):  # ToDo - replace with proper logging
    ts = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]'
    lvl = f'[{log_level.upper()}]'.ljust(7)
    log_line = f'{value}'
    if exception:
        log_line = f'[{ex(exception)}] {log_line}\n{traceback.format_exc()}'
    with open(log_file, 'a+') as f:
        f.write(f'{ts} {lvl} {log_line}\n')


def rotate_logs():
    if os.path.exists(log_file):
        timestamp = datetime.now().strftime('%Y%m%d%H%M')
        os.rename(log_file, f'{log_file}.{timestamp}')

    log_pattern = f'{log_file}.*'
    existing_logs = sorted([f for f in glob.glob(log_pattern)], reverse=True)
    for old_log in existing_logs[4:]:
        os.remove(old_log)


def get_terminal_environ():
    """Obtain a clean environment from a terminal to be used for tilt commands (instead of using this app's sanitized env"""
    global terminal_env
    if terminal_env is not None:
        return terminal_env

    base_env = {}
    for key in ['HOME', 'USER', 'LOGNAME', 'LANG']:
        val = os.environ.get(key)
        if val:
            base_env[key] = val
    env_output = subprocess.check_output([SHELL, '-l', '-c', 'env'], text=True, env=base_env).strip()
    # log('[DEBUG] Terminal env:\n' + "\n".join(f"\t{p}" for p in env_output.splitlines()))
    terminal_env = dict(line.split('=', 1) for line in env_output.splitlines() if '=' in line)
    if custom_env_vars:
        log(f'Updating custom environment variables:\n' + "\n".join(f"\t{k}={v}" for k, v in custom_env_vars.items()))
        for k, v in custom_env_vars.items():
            terminal_env[k] = v
    return terminal_env


def update_environ():
    try:
        ev_path = subprocess.check_output([SHELL, '-l', '-c', 'echo $PATH'], text=True).strip()
        # log('[DEBUG] Existing $PATH:\n' + "\n".join(f"\t{p}" for p in ev_path.split(os.pathsep)))
        for p in ev_path.split(os.pathsep):
            if p not in os.environ['PATH']:
                os.environ['PATH'] += os.pathsep + p
                # log(f'[DEBUG] Added to $PATH: {p}')
        log(f'Updated PATH environment variable from {SHELL} shell')
    except Exception as e:
        log(f'Error updating PATH environment variable: {e}', 'ERROR', e)


def rumps_alert(title, message, ok='OK', other=None, cancel=None, callback=None):
    if not hasattr(sys, 'frozen') and not sys.argv[0].endswith('.app/Contents/MacOS/'):
        return 0
    return rumps.alert(title, message, ok, other, cancel, callback)


def api_get_tilt_status(timeout=None):
    res = requests.get(tilt_status_url, timeout=timeout)
    res.raise_for_status()
    return res.json()


def get_tilt_status():
    data = api_get_tilt_status()

    resources = data.get('uiResources', [])
    result_list = []

    for r in resources:
        meta = r['metadata']
        status = r['status']
        r_name = meta['name']
        r_label = [v for k, v in meta.get('labels', {}).items()][0] if 'labels' in meta \
            else 'Tiltfile' if r_name == '(Tiltfile)' \
            else 'unlabeled'
        update_status = status['updateStatus']
        runtime_status = status['runtimeStatus']
        if update_status != 'none':
            result_list.append((r_label, r_name, update_status, runtime_status))

    # Sort order: Items with labels (A->Z) >> Items without label >> Tiltfile
    result_list.sort(key=lambda x: (x[0] == 'Tiltfile', x[0] == 'unlabeled', x[0]))
    return result_list


def is_tilt_healthy(result_list=None):
    prv_tilt_healthy = app.tilt_healthy
    if result_list is None:
        result_list = get_tilt_status()
    statuses = [status for rs in result_list for status in [rs[2], rs[3]] if status != 'not_applicable']
    if any(s == 'error' for s in statuses):
        tilt_healthy = False
    elif any(s in ['pending', 'in_progress'] for s in statuses):
        tilt_healthy = None
    elif all(s == 'ok' for s in statuses):
        tilt_healthy = True
    else:
        log(f'Unknown Tilt status:\n{statuses}', 'WARN')
        tilt_healthy = False
    if tilt_healthy != prv_tilt_healthy:
        tilt_status_text, log_lvl = \
            ('OK', 'INFO') if tilt_healthy \
            else ('Pending', 'WARN') if tilt_healthy is None \
            else ('Error', 'ERROR')
        log(f'Tilt status: {tilt_status_text}', log_lvl)
        app.tilt_healthy = tilt_healthy
    return tilt_healthy


def is_tilt_running():
    try:
        _ = api_get_tilt_status(timeout=2)
        is_running = True
        log_msg = 'Tilt daemon is running'
    except (ConnectionError, requests.ConnectionError):
        is_running = False
        log_msg = 'Tilt daemon is not running'
    except requests.RequestException:
        is_running = True
        log_msg = 'Tilt daemon is running, but status API returned an error'
    if is_running != app.tilt_running:
        log(log_msg)
    app.tilt_running = is_running
    return is_running


def get_tilt_file_path():
    """Gets and normalizes the tilt_file_path from the latest config."""
    cfg = load_config()
    path = cfg.get('tilt_file_path', '')
    if path.endswith('Tiltfile'):
        path = os.path.dirname(path)
    return path


def is_tiltfile_path_valid(path_str):
    if not path_str:
        return False
    path = Path(path_str)
    if path.is_dir():
        return (path / 'Tiltfile').is_file()
    return path.is_file() and path.name == 'Tiltfile'


def is_app_location_valid():
    if bundle_path.startswith('/Applications/') or not os.access(bundle_path, os.W_OK):
        return True
    return False


def move_to_applications():
    """Move the app bundle to the Applications folder. NOTE: Must be run only after TiltMonitorApp was initialized to use rump commands"""
    app_name = os.path.basename(bundle_path)
    destination_path = os.path.join('/Applications', app_name)
    dest_exists = os.path.exists(destination_path)

    alert_msg = (f'To keep your applications organized, it is recommended to move {APP_NAME} to your Applications folder.\n\n'
                 f'Would you like to move it now{" (overwrite the existing version)" if dest_exists else ""} and relaunch?')
    response = rumps_alert(title=f'Move {APP_NAME}?', message=alert_msg, ok='Move to Applications', cancel="Don't Move")
    if response == 1:  # OK button
        try:
            if dest_exists:
                log(f'Removing existing destination: {destination_path}')
                shutil.rmtree(destination_path)
            log(f'Moving {bundle_path} to {destination_path}')
            shutil.move(bundle_path, destination_path)
            log('Relaunching from new location')
            subprocess.Popen(['open', destination_path])
            rumps.quit_application()
        except Exception as mv_err:
            log(f'Failed to move application: {mv_err}', 'ERROR', mv_err)
            alert_msg = f'Could not move {APP_NAME} to the Applications folder.\n\nPlease do it manually.'
            rumps_alert(title='Move Failed', message=alert_msg, ok='OK')


def run_tilt_command(command):
    """Run a tilt command (up/down) with configured arguments"""
    try:
        cmd_env = os.environ.copy()
        cmd = [app.tilt, command]
        if command == 'up': # ToDo - Add --host and --port to all commands, to support multiple Tilt instances
            cmd.extend(tilt_cmd_args.split())
            try:
                cmd_env = get_terminal_environ()
            except Exception as env_err:
                log(f'Cannot run `tilt {command}`; Error getting terminal environment: {str(env_err)}', 'ERROR', env_err)
                return False, None

        log(f'Running command: {" ".join(cmd)}')
        process = subprocess.Popen(cmd, cwd=tilt_file_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=cmd_env)
        log(f'Command `tilt {command}` executed')
        return True, process
    except Exception as cmd_err:
        log(f'Error running `tilt {command}`: {str(cmd_err)}', 'ERROR', cmd_err)
        return False, None


def rumps_notification(subtitle, message):
    """
    :param title: The notification title (required)
    :param subtitle: The notification subtitle (optional)
    :param message: The notification message/body (optional)
    :param data: Custom data to be passed to callback (optional)
    :param sound: Boolean to enable/disable sound (default True)
    :param icon: Path to icon image (optional)
    :param action_button: Text for the action button (optional)
    :param other_button: Text for the other button (optional)
    :param callback: Function to call when notification is clicked (optional)
    :return:
    """
    try:
        rumps.notification(APP_NAME, subtitle, message)
    except RuntimeError:
        log(f'Notification not shown:\n\t{subtitle}\n\t{message}', 'WARN')


def get_resource_state_summary(data=None):
    if not data:
        data = api_get_tilt_status()
    resources = data.get('uiResources', [])
    state_counts = {'ok': 0, 'pending': 0, 'error': 0, 'warn': 0}
    for r in resources:
        status = r.get('status', {})
        disable = status.get('disableStatus', {})
        if disable and disable.get('state') == 'Disabled':
            continue  # skip disabled
        # Count warnings if present
        warn_count = status.get('warningCount')
        if warn_count and warn_count > 0:
            state_counts['warn'] += 1
            continue
        warnings = status.get('warnings')
        if warnings and isinstance(warnings, list) and len(warnings) > 0:
            state_counts['warn'] += 1
            continue
        # Use updateStatus and runtimeStatus for other states
        update_status = status.get('updateStatus')
        runtime_status = status.get('runtimeStatus')
        # error
        if update_status == 'error' or runtime_status == 'error':
            state_counts['error'] += 1
        # pending
        elif update_status in ('pending', 'in_progress') or runtime_status in ('pending', 'in_progress'):
            state_counts['pending'] += 1
        # ok/healthy
        elif update_status == 'ok' and (runtime_status == 'ok' or runtime_status == 'not_applicable'):
            state_counts['ok'] += 1
    summary_parts = []
    if state_counts['error']:
        summary_parts.append(f"🔴 {state_counts['error']}")
    if state_counts['warn']:
        summary_parts.append(f"🟡 {state_counts['warn']}")
    if state_counts['pending']:
        summary_parts.append(f"⚪️ {state_counts['pending']}")
    if state_counts['ok']:
        summary_parts.append(f"🟢 {state_counts['ok']}")
    return '  '.join(summary_parts)


class TiltMonitorApp(rumps.App):
    """macOS Menu Bar App for monitoring Tilt"""
    # ToDo - implement check for updates
    def __init__(self, short_timer_interval=keepalive_interval, long_timer_interval=sleep_interval, up_on_start=False):
        super().__init__(APP_NAME, icon=default_icon)

        self.title = ''  # must remain empty, otherwise the renderer attempts to show the title instead of the icon
        self.menu = []  # Menu will be populated in update_menu_visibility
        self.icon = gray_icon  # Start with gray until status check
        self.short_timer = rumps.Timer(self.check_tilt, short_timer_interval)
        self.long_timer = rumps.Timer(self.check_tilt, long_timer_interval)
        self.tilt_starting = False
        self.tilt_process = None
        self.up_on_start = up_on_start
        self.show_reload_option = False
        # Initial check on delayed timer to allow the app to run
        self.init_timer = rumps.Timer(self.initialize, 1)
        self.init_timer.start()

    def initialize(self, _):
        if not is_app_location_valid():
            move_to_applications()

        is_tilt_running()
        self.update_menu_visibility()
        if app.tilt_running:
            self.activate_short_timer()
        else:
            self.activate_long_timer()
            if self.up_on_start:
                self.tilt_up(None)
        self.init_timer.stop()

    def cleanup_and_quit(self, _):
        for f in glob.glob(f'{tmp_file_pfx}*'):
            if os.path.isfile(f):
                log(f'Removing temp file: {f}')
                os.remove(f)
        log('Closing application')
        self.tilt_down(None)
        rumps.quit_application()

    def activate_short_timer(self):
        self.long_timer.stop()
        self.short_timer.start()
        log(f'Set health check timer to {self.short_timer.interval} seconds')

    def activate_long_timer(self):
        self.short_timer.stop()
        self.long_timer.start()
        log(f'Set health check timer to {self.long_timer.interval} seconds')

    def check_tilt(self, _):
        try:
            prv_tilt_running = app.tilt_running
            is_tilt_running()
            if app.tilt_running:
                try:
                    healthy = is_tilt_healthy()
                    self.icon = {
                        True: green_icon,
                        False: red_icon,
                        None: gray_icon
                    }.get(healthy, gray_icon)
                    if self.tilt_starting and healthy is not None:
                        self.tilt_starting = False
                        self.update_menu_visibility()
                except Exception as api_err:
                    log(f'Error getting Tilt status: {api_err}', 'ERROR', api_err)
                    self.icon = red_icon  # API error indicates unhealthy state
            else:
                self.icon = transparent_icon

            if prv_tilt_running != app.tilt_running:
                self.update_menu_visibility()
                if app.tilt_running:
                    self.activate_short_timer()
                else:
                    self.activate_long_timer()
        except Exception as tilt_err:
            self.icon = gray_icon
            log(f'{tilt_err}', 'ERROR', tilt_err)
            self.update_menu_visibility()

    @rumps.clicked(MENU_OPT_EDIT_CONFIG)
    def edit_config(self, _):
        """Open configuration file in default editor"""
        try:
            if not os.path.exists(config_file):
                load_config()
            log(f'Edit configuration file: {config_file}')
            subprocess.call(['open', config_file])
            self.show_reload_option = True
            self.update_menu_visibility()
            rumps_notification('Edit Configuration', "Click 'Reload' from the app menu when done to apply changes")
        except Exception as edit_err:
            log(f'Error opening config file: {edit_err}', 'ERROR', edit_err)
            rumps_alert('Error', f'Could not open configuration file: {edit_err}')

    def about(self, _):
        """Show the About window"""
        log('Showing About message window')
        about_msg = f'Version {APP_VERSION}\n\n{APP_DESCRIPTION}'
        clicked = rumps_alert(
            title=APP_NAME,
            message=about_msg,
            ok='Close',  # 1
            other='View on GitHub',  # 0
            # cancel = 'Cancel',  # -1
        )
        log(f'Button clicked: {clicked}')
        if clicked == 0:
            log('Opening GitHub page')
            webbrowser.open(APP_URL)

    def reload_app(self, _):
        """Reload the application"""
        log('Reloading application')
        args = [arg for arg in sys.argv if arg != '--reloaded']
        os.execv(sys.executable, [sys.executable] + args + ['--reloaded'])

    @rumps.clicked(MENU_OPT_SHOW_LOG)
    def show_log(self, _):
        """Open the log file in the default editor"""
        try:
            subprocess.call(['open', log_file])
        except Exception as show_err:
            log(f'Error opening log file: {show_err}', 'ERROR', show_err)
            rumps_alert('Error', f'Could not open log file: {show_err}. Please check the log file manually ({log_file}).')

    @rumps.clicked(MENU_OPT_OPEN_UI)
    def open_ui(self, _):
        import webbrowser
        webbrowser.open(tilt_ui_url)

    @rumps.clicked(MENU_OPT_TILT_UP)
    def tilt_up(self, _):
        if not is_tiltfile_path_valid(tilt_file_path):
            log("Cannot 'tilt up': 'tilt_file_path' is not configured or is invalid.", 'WARN')
            rumps_notification(
                'Configuration Required',
                "Click on 'Edit Configuration' and set 'tilt_file_path' to a valid Tiltfile path"
            )
            return

        log('Starting Tilt')
        success, process = run_tilt_command('up')
        if success:
            self.tilt_process = process
            self.tilt_starting = True
            self.update_menu_visibility()  # Update menu to show "starting" status
            self.poll_timer = rumps.Timer(self.poll_tilt_started, 1)  # Start a polling timer to check when Tilt is available
            self.poll_timer.start()
            # rumps_notification('Tilt Up', 'Tilt has been started')

    def poll_tilt_started(self, _):
        try:
            api_get_tilt_status(timeout=1)
            self.poll_timer.stop()
            app.tilt_running = True
            self.activate_short_timer()
            self.update_menu_visibility()
            log('Tilt API is now available')
        except Exception:
            pass  # API not available yet, will try again on next poll

    @rumps.clicked(MENU_OPT_TILT_DOWN)
    def tilt_down(self, _):
        process_killed = False
        log('Stopping Tilt')

        if self.tilt_starting and hasattr(self, 'poll_timer') and self.poll_timer.is_alive():
            self.poll_timer.stop()

        if self.tilt_process:
            try:
                import signal
                os.kill(self.tilt_process.pid, signal.SIGTERM)
                log(f'Terminated Tilt process {self.tilt_process.pid}')
                process_killed = True
            except Exception as kill_err:
                log(f'Failed to terminate Tilt process: {kill_err}', 'ERROR')

        if not process_killed:
            success, _ = run_tilt_command('down')
            if not success:
                return  # Failed to stop Tilt

        self.tilt_starting = False
        self.tilt_process = None
        app.tilt_running = False
        self.activate_long_timer()
        self.icon = transparent_icon
        self.update_menu_visibility()
        # rumps_notification('Tilt Down', 'Tilt has been stopped')

    def update_menu_visibility(self):
        """Update menu items based on Tilt status"""
        is_running = app.tilt_running

        self.menu.clear()
        # ToDo - improve the logic of adding and removing menu items
        # Add items based on current state
        if self.tilt_starting:
            self.menu.add(MENU_OPT_TILT_STARTING)
            self.menu.add(MENU_OPT_TILT_DOWN)
            self.menu[MENU_OPT_TILT_DOWN].set_callback(self.tilt_down)
            if is_running:
                self.menu.add(MENU_OPT_OPEN_UI)
                self.menu[MENU_OPT_OPEN_UI].set_callback(self.open_ui)
        elif is_running:
            ########## TBD: Add status summary to the menu ##########  ToDo - implement status summary
            # if MENU_OPT_STATUS_SUMMARY not in self.menu:
            #     self.menu[MENU_OPT_STATUS_SUMMARY] = rumps.MenuItem(MENU_OPT_STATUS_SUMMARY)
            # summary_item = self.menu[MENU_OPT_STATUS_SUMMARY]
            # summary_item.title = get_resource_state_summary()
            # self.menu.add(None)
            #########################################################
            self.menu.add(MENU_OPT_OPEN_UI)
            self.menu[MENU_OPT_OPEN_UI].set_callback(self.open_ui)
            self.menu.add(MENU_OPT_TILT_DOWN)
            self.menu[MENU_OPT_TILT_DOWN].set_callback(self.tilt_down)
        else:
            self.menu.add(MENU_OPT_TILT_UP)
            if is_tiltfile_path_valid(tilt_file_path):
                self.menu[MENU_OPT_TILT_UP].set_callback(self.tilt_up)
            else:
                self.menu[MENU_OPT_TILT_UP].set_callback(None)

            self.menu.add(MENU_OPT_EDIT_CONFIG)
            self.menu[MENU_OPT_EDIT_CONFIG].set_callback(self.edit_config)

            if self.show_reload_option:
                self.menu.add(MENU_OPT_RELOAD)
                self.menu[MENU_OPT_RELOAD].set_callback(self.reload_app)
        # Always shown:
        self.menu.add(None)  # separator
        self.menu.add(MENU_OPT_SHOW_LOG)
        self.menu[MENU_OPT_SHOW_LOG].set_callback(self.show_log)
        self.menu.add(None)  # separator
        self.menu.add(MENU_OPT_ABOUT)
        self.menu[MENU_OPT_ABOUT].set_callback(self.about)
        quit_item = rumps.MenuItem('Quit', callback=self.cleanup_and_quit)
        self.menu.add(quit_item)


def main():
    try:
        if '--reloaded' in sys.argv:
            sys.argv.remove('--reloaded')
        else:
            rotate_logs()

        log(f'============ {APP_NAME} {APP_VERSION} ============')
        update_environ()
        get_terminal_environ()

        log('Parse configuration')
        args = parser.parse_args()

        env_args = {ev[0]: ev[1] for ev in os.environ.items() if ev[0].startswith('TMB_')}

        time_interval = keepalive_interval
        if args.time_interval is not None:
            time_interval = int(args.time_interval)
        elif env_args.get('TMB_TIME_INTERVAL', '').isdigit():
            time_interval = int(env_args['TMB_TIME_INTERVAL'])

        log(f'Starting menu bar app with timer interval: {time_interval} seconds')
        app_instance = TiltMonitorApp(short_timer_interval=time_interval, up_on_start=args.up)
        app_instance.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as err:
        log(f'{err}', 'ERROR', err)
        sys.exit(1)


if __name__ == '__main__':
    main()
