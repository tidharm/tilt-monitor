import argparse
import glob
import logging
import os
import shutil
import subprocess
import sys
import time

from tilt_monitor import __app_name__ as APP_NAME


RESOURCE_DIR = 'tilt_monitor/resources'
ICON_SRC = 'green.png'
ICON_SET_NAME = 'tilt.iconset'
ICNS_NAME = 'tilt.icns'
ICNS_PATH = os.path.join(RESOURCE_DIR, ICNS_NAME)
PKG_DIR = 'package'
DIST_DIR = 'dist'
BUILD_DIR = 'build'

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
args = parser.parse_args()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
if logger.hasHandlers():
    logger.handlers.clear()

# Set formats
console_format = '%(message)s'
if args.verbose:
    file_format = '%(asctime)s %(levelname)-5s - [%(funcName)-15s] %(message)s'
else:
    file_format = '%(asctime)s %(levelname)-5s - %(message)s'

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(console_format))
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

# File Handler
file_handler = logging.FileHandler('build.log', mode='w')
file_handler.setFormatter(logging.Formatter(file_format))
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def create_icon():
    """Create .icns file from .png using sips and iconutil."""
    if os.path.exists(ICNS_PATH):
        logger.debug(f'Icon "{ICNS_PATH}" already exists.')
        return

    logger.info('Creating icon...')
    iconset_dir = os.path.join(RESOURCE_DIR, ICON_SET_NAME)
    os.makedirs(iconset_dir, exist_ok=True)
    source_image = os.path.join(RESOURCE_DIR, ICON_SRC)

    try:
        # Create iconset
        sizes = {
            'icon_16x16.png': 16,
            'icon_16x16@2x.png': 32,
            'icon_32x32.png': 32,
            'icon_32x32@2x.png': 64,
            'icon_128x128.png': 128,
            'icon_128x128@2x.png': 256,
            'icon_256x256.png': 256,
            'icon_256x256@2x.png': 512,
            'icon_512x512.png': 512,
        }
        for name, size in sizes.items():
            subprocess.run([
                'sips', '-z', str(size), str(size), source_image, '--out', os.path.join(iconset_dir, name)
            ], check=True, capture_output=True)
        shutil.copy(source_image, os.path.join(iconset_dir, 'icon_512x512@2x.png'))

        # Create .icns from iconset
        subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', ICNS_PATH], check=True, capture_output=True)
        logger.info(f'Icon created at "{ICNS_PATH}"')

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'Error during icon creation: {e}')
        if isinstance(e, subprocess.CalledProcessError):
            logger.error(f'Stderr: {e.stderr.decode("utf-8")}')
        sys.exit(1)
    finally:
        if os.path.exists(iconset_dir):
            shutil.rmtree(iconset_dir)


def quit_app():
    try:
        is_running_check = subprocess.run(['pgrep', '-x', APP_NAME], capture_output=True)
        logger.debug(is_running_check)
        if is_running_check.returncode == 0:
            logger.info(f'{APP_NAME} is running')

            dialog_text = f'{APP_NAME} is running." & return & return & "Quit it to continue the build, or Cancel to abort.'
            dialog_icon = f'(POSIX file "{os.path.abspath(ICNS_PATH)}")' if os.path.exists(ICNS_PATH) else 'caution'
            prompt_script = f'return button returned of (display dialog "{dialog_text}" buttons {{"Cancel", "Quit"}} default button "Quit" with icon {dialog_icon})'
            prompt_result = subprocess.run(['osascript', '-e', prompt_script], capture_output=True, text=True)

            if prompt_result.returncode == 1 and "User canceled" in prompt_result.stderr:
                logger.info('Build cancelled by user')
                sys.exit(0)
            elif prompt_result.returncode != 0:
                logger.error(f'Error displaying dialog: {prompt_result.stderr}')
                sys.exit(1)

            if 'Quit' in prompt_result.stdout:
                logger.info('Quitting application...')
                quit_script = f'tell application "{APP_NAME}" to quit'
                subprocess.run(['osascript', '-e', quit_script], check=True)
                time.sleep(2)  # Give the app time to quit.
            else:
                logger.info('Build cancelled')
                sys.exit(0)
        else:
            logger.debug(f'{APP_NAME} is not running, skipping check')
    except FileNotFoundError as e_nf:
        logger.warning(f'Command `{e_nf.filename}` not found. Skipping check for running app')
    except Exception as e:
        logger.error(f'ERROR: {e}')
        sys.exit(1)


def build():
    """Build the macOS application."""
    create_icon()

    quit_app()

    if os.path.exists(PKG_DIR):
        shutil.rmtree(PKG_DIR)
    os.makedirs(PKG_DIR)

    logger.info(f'Packaging {APP_NAME} using py2app (see log for details)')
    try:
        subprocess.run(
            [sys.executable, 'setup.py', 'py2app'],
            stdout=file_handler.stream,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f'py2app build failed: {e.stderr}')
        sys.exit(1)

    logger.info('Build successful')

    app_bundle = os.path.join(DIST_DIR, f'{APP_NAME}.app')
    if os.path.exists(app_bundle):
        shutil.move(app_bundle, PKG_DIR)
    else:
        logger.error(f'Could not find {app_bundle}')
        sys.exit(1)

    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

    logger.info('Cleanup complete')
    logger.info(f'Package created: {os.path.join(PKG_DIR, f"{APP_NAME}.app")}')


if __name__ == '__main__':
    try:
        build()
    except KeyboardInterrupt:
        pass
