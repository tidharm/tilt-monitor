import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback

from tilt_monitor import __app_name__, __version__


ASSETS_DIR = 'tilt_monitor/assets'
ICON_SRC = 'green.png'
ICON_SET_NAME = 'tilt.iconset'
ICNS_NAME = 'tilt.icns'
ICNS_PATH = os.path.join(ASSETS_DIR, ICNS_NAME)
PKG_DIR = 'package'
DIST_DIR = 'dist'
BUILD_DIR = 'build'
VENV_DIR = '.venv'
APP_NAME = __app_name__
APP_VERSION = __version__
DMG_NAME = f'{APP_NAME.replace(" ", "-")}-{APP_VERSION}.dmg'

include_dmg_license = True

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
parser.add_argument('--dmg', action='store_true', help='Create a distributable DMG file.')
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


def ex(e):
    tb = e.__traceback__
    l_frame = traceback.extract_tb(tb)[-1]
    return f'{type(e).__name__}][{l_frame.name}:{l_frame.lineno}]({l_frame.filename})'


def setup_environment():
    """
    Sets up a virtual environment and installs dependencies.
    Returns the path to the Python executable in the virtual environment.
    """
    venv_dir = os.environ.get('VIRTUAL_ENV')
    if venv_dir:
        logger.info(f"Using existing virtual environment: '{venv_dir}'")
    else:
        for item in os.listdir('.'):
            if os.path.isdir(item) and os.path.exists(os.path.join(item, 'pyvenv.cfg')):
                venv_dir = item  # found an existing, inactive venv
                logger.info(f"Using existing virtual environment: '{venv_dir}'")
                break

    if venv_dir is None:
        venv_dir = VENV_DIR
        logger.info(f"Creating virtual environment: '{venv_dir}'")
        subprocess.check_call([sys.executable, '-m', 'venv', venv_dir])

    python = os.path.join(venv_dir, 'bin', 'python')

    logger.info('Installing dependencies...')
    subprocess.check_output([python, '-m', 'pip', 'install', '-r', 'requirements.txt', '--upgrade'])
    
    logger.info('Installing dev dependencies...')
    subprocess.check_output([python, '-m', 'pip', 'install', '-r', 'requirements-dev.txt', '--upgrade'])

    # Add the venv's package dir to path for current execution (required for scripts that bootstrap their own dependencies).
    site_packages_path = subprocess.check_output([python, '-c', "import sysconfig; print(sysconfig.get_paths()['purelib'])"], text=True).strip()
    if site_packages_path not in sys.path:
        sys.path.insert(0, site_packages_path)

    return python


def create_icon():
    """Create .icns file from .png using sips and iconutil."""
    if os.path.exists(ICNS_PATH):
        logger.debug(f'Icon "{ICNS_PATH}" already exists.')
        return

    logger.info('Creating icon...')
    iconset_dir = os.path.join(ASSETS_DIR, ICON_SET_NAME)
    os.makedirs(iconset_dir, exist_ok=True)
    source_image = os.path.join(ASSETS_DIR, ICON_SRC)

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
            subprocess.check_output([
                'sips', '-z', str(size), str(size), source_image, '--out', os.path.join(iconset_dir, name)
            ])
        shutil.copy(source_image, os.path.join(iconset_dir, 'icon_512x512@2x.png'))

        # Create .icns from iconset
        subprocess.check_output(['iconutil', '-c', 'icns', iconset_dir, '-o', ICNS_PATH])
        logger.info(f'Icon created at "{ICNS_PATH}"')

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'Error during icon creation: {e}')
        if isinstance(e, subprocess.CalledProcessError):
            logger.error(f'Stderr: {e.stderr.decode("utf-8")}')
        sys.exit(1)
    finally:
        if os.path.exists(iconset_dir):
            shutil.rmtree(iconset_dir)


def is_app_running():
    """Check if the application is running."""
    return subprocess.run(['pgrep', '-x', APP_NAME], capture_output=True).returncode == 0


def quit_app():
    try:
        if is_app_running():
            logger.info(f'{APP_NAME} is running')

            dialog_text = f'{APP_NAME} is running." & return & return & "Quit it to continue the build, or Cancel to abort.'
            dialog_icon = f'(POSIX file "{os.path.abspath(ICNS_PATH)}")' if os.path.exists(ICNS_PATH) else 'caution'
            prompt_script = f'return button returned of (display dialog "{dialog_text}" buttons {{\"Cancel\", \"Quit\"}} default button "Quit" with icon {dialog_icon})'
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
                subprocess.check_call(['osascript', '-e', quit_script])
                for _ in range(10):
                    if not is_app_running():
                        logger.info(f'{APP_NAME} has quit.')
                        break
                    time.sleep(0.5)
                else:
                    logger.warning(f'{APP_NAME} did not quit after 5 seconds. Build may fail.')
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


def unmount_existing_volumes():
    """Unmount any existing {APP_NAME} volumes."""
    try:
        for volume in os.listdir('/Volumes'):
            if volume.startswith(APP_NAME):
                logger.info(f'Unmounting existing volume "{volume}"...')
                subprocess.check_call(['hdiutil', 'detach', os.path.join('/Volumes', volume), '-quiet'])
    except FileNotFoundError:
        logger.warning(f'Could not list /Volumes to unmount existing images. Skipping')
    except subprocess.CalledProcessError as e:
        logger.warning(f'Could not unmount volume: {e}')


def build_dmg():
    import dmgbuild
    unmount_existing_volumes()

    logger.info(f'Creating {DMG_NAME}...')
    app_bundle = os.path.join(PKG_DIR, f'{APP_NAME}.app')
    if not os.path.exists(app_bundle):
        logger.error(f'  Application bundle not found at {app_bundle}')
        sys.exit(1)

    dmg_path = os.path.join(PKG_DIR, DMG_NAME)  # ToDo - include version (and update version by workflow)
    if os.path.exists(dmg_path):
        os.remove(dmg_path)

    # https://dmgbuild.readthedocs.io/en/latest/settings.html
    settings = {
        'filename': dmg_path,
        'volume_name': APP_NAME,
        'format': 'UDZO',
        'filesystem': 'HFS+',
        'files': [
            (app_bundle, f'{APP_NAME}.app'),
        ],
        'symlinks': {'Applications': '/Applications'},
        'badge_icon': ICNS_PATH,
        'icon_locations': {
            f'{APP_NAME}.app': (100, 180),
            'Applications': (400, 180),
        },
        'background': 'resources/dmg-background.png',
        'window_rect': ((100, 100), (500, 355)),
        'default_view': 'icon-view',
        'icon_size': 128,
        'text_size': 12,
    }
    if include_dmg_license:
        settings['license'] = {
            'default-language': 'en_US',
            'licenses': {'en_US': 'resources/LICENSE.rtf'}
        }

    try:
        dmgbuild.build_dmg(dmg_path, APP_NAME, settings=settings)
        logger.info(f'DMG created: {dmg_path}')
    except Exception as e:
        logger.error(f'Error creating DMG with dmgbuild:\n\t[{ex(e)}]{e}')
        sys.exit(1)


def build(python_executable=None):
    """Build the macOS application."""
    python = python_executable or sys.executable
    create_icon()

    quit_app()

    if os.path.exists(PKG_DIR):
        shutil.rmtree(PKG_DIR)
    os.makedirs(PKG_DIR)

    logger.info(f'Packaging {APP_NAME} using py2app (see log for details)')
    try:
        subprocess.run(
            [python, 'setup.py', 'py2app'],
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

    if args.dmg:
        build_dmg()
    else:
        logger.info(f'Package created: {os.path.join(PKG_DIR, f"{APP_NAME}.app")}')


if __name__ == '__main__':
    try:
        if not os.environ.get('CI'):
            python_exe = setup_environment()
        else:
            python_exe = sys.executable
        build(python_exe)
    except KeyboardInterrupt:
        pass
    except Exception as build_err:
        logger.error(f"A build step failed. Check 'build.log' for details.")
        sys.exit(1)