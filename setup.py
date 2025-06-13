from setuptools import setup, find_packages
from tilt_monitor import __app_name__, __app_description__, __app_url__, __version__
from glob import glob


setup(
    name=__app_name__,
    version=__version__,
    author='tidharm',
    description=f'{__app_description__}',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url=__app_url__,
    license='LICENSE',
    classifiers=[
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: MacOS',
    ],
    packages=find_packages(),
    python_requires='>=3.9',
    install_requires=[line.strip() for line in open('requirements.txt').readlines()],
    extras_require={
        'dev': [line.strip() for line in open('requirements-dev.txt').readlines()],
    },
    package_data={
        'tilt_monitor': ['resources/*.png', 'resources/*.icns', 'tilt_monitor_config.json'],
    },
    entry_points={
        'console_scripts': [
            'tilt-monitor=tilt_monitor.tilt_monitor:main',
            'tilt-status=tilt_monitor.tilt_status:main',
        ],
    },
    app=['tilt_monitor/tilt_monitor.py'],
    data_files=[('resources', glob('tilt_monitor/resources/*.png') + glob('tilt_monitor/resources/*.icns'))],
    options={
        'py2app': {
            'iconfile': 'tilt_monitor/resources/tilt.icns',
            'includes': ['rumps', 'pyobjc_framework_Cocoa', 'imp'],
            'plist': {
                'CFBundleIdentifier': 'com.tilt.monitor',
                'CFBundleDisplayName': __app_name__,
                'CFBundleShortVersionString': __version__,
                'ASApplicationDescription': __app_description__,
                'ApplicationHomepageURL': __app_url__,
                'LSUIElement': True  # Hide app from Dock
            }
        }
    },
    setup_requires=['py2app'],
)
