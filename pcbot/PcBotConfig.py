import json
import os
import pathlib
import sys

config_files = {'win32': pathlib.Path.home() / 'AppData' / 'Local' / 'pcbot' / 'config.json',
                'linux': pathlib.Path.home() / '.config' / 'pcbot' / 'config.json'}


def main():  # TODO
    config = {'bot_token': input('Insert bot token:\n'), 'chat_ids': [int(input('Insert chat id\n'))]}
    os.mkdir(os.path.split(config_files[sys.platform])[0])
    json.dump(config, open(config_files[sys.platform], 'w'), indent=4)


def get_local_directory():
    local_directories = {'win32': pathlib.Path.home() / 'AppData' / 'Local' / 'pcbot',
                         'linux': pathlib.Path.home() / '.local' / 'share' / 'pcbot'}
    return local_directories[sys.platform]


def get_config():
    for config_file in [config_files[sys.platform]]:
        if os.path.exists(config_file):
            return json.load(open(config_file))
    else:
        main()


if __name__ == '__main__':
    main()
