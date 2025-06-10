from colorama import Fore, Style
import os
import sys
import traceback

from tilt_monitor.tilt_monitor import log, get_tilt_status


script_name = os.path.splitext(os.path.basename(__file__))[0]

# colors
GRN = Fore.GREEN
YLW = Fore.YELLOW
RED = Fore.RED
GRY = Fore.LIGHTBLACK_EX
NC = Style.RESET_ALL

status_colors = {
    'ok': GRN,
    'pending': YLW,
    'error': RED,
    'n/a': GRY,
}


def text_color(text, color=None):
    if color is None:
        return text
    return f'{color}{text}{NC}'


def print_status_results(result_list):
    log('Print Tilt status result table')
    prv_label = result_list[0][0]
    i = 1

    def _status(text):
        value = 'n/a' if text == 'not_applicable' else text
        status_text = text_color(value.upper().ljust(15), status_colors.get(value))
        return status_text

    print('\nTilt Status\n')
    print('   | Label     | Name                 | Update Status   | Runtime Status')
    print('---+-----------+----------------------+-----------------+---------------')

    for r_label, r_name, update_status, runtime_status in result_list:
        if prv_label != r_label:
            print('---+-----------+----------------------+-----------------+---------------')
        print(f'{str(i).ljust(2)} | {r_label.ljust(9)} | {r_name.ljust(20)} | {_status(update_status)} | {_status(runtime_status)}')
        i += 1
        prv_label = r_label


def main():
    try:
        log(f'============ {script_name} Start ============')
        tilt_status = get_tilt_status()
        print_status_results(tilt_status)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as err:
        log(err, 'ERROR', traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
