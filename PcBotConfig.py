import os
import sys
import pathlib
import json

config_files = {'win32': os.path.join(pathlib.Path.home(), 'AppData', 'Local', 'pcbot', 'config.json'), 'linux': os.path.join(pathlib.Path.home(), '.config', 'pcbot', 'config.json')}


def main():  # TODO
    config = {'bot_token': input('Insert bot token:\n'), 'chat_ids': [int(input('Insert chat id\n'))]}
    os.mkdir(os.path.split(config_files[sys.platform])[0])
    json.dump(config, open(config_files[sys.platform], 'w'), indent=4)


def get_config():
    for config_file in [config_files[sys.platform]]:
        if os.path.exists(config_file):
            return json.load(open(config_file))
    else:
        main()


if __name__ == '__main__':
    main()
