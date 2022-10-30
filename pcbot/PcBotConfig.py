import dataclasses
import json
import logging
import pathlib
import sys


@dataclasses.dataclass
class PcBotConfig:
    chat_ids: list
    bot_token: str


def get_config_filename():
    universal_config = pathlib.Path(__file__).parent.parent.absolute() / 'configs' / 'universalconfig.json'
    config_filenames = {'win32': pathlib.Path.home() / 'AppData' / 'Local' / 'pcbot' / 'config.json',
                        'linux': pathlib.Path.home() / '.config' / 'pcbot' / 'config.json'}
    user_config = config_filenames[sys.platform]

    possible_configs = {user_config, universal_config}
    return first_existent_file(possible_configs, default=user_config)


def first_existent_file(files, default=None):
    for file in files:
        if file.exists():
            return file
    if default is not None:
        return default
    raise FileNotFoundError('None of the files exist')


def main():  # TODO
    config = {'bot_token': input('Insert bot token:\n'), 'chat_ids': []}
    config_filename = get_config_filename()
    config_filename.parent.mkdir(parents=True, exist_ok=True)
    with open(config_filename, 'w') as f:
        json.dump(config, f, indent=4)


def save_config(config: PcBotConfig):
    with open(get_config_filename(), 'w') as f:
        json.dump(dataclasses.asdict(config), f, indent=4)


def get_local_directory():
    local_directories = {'win32': pathlib.Path.home() / 'AppData' / 'Local' / 'pcbot',
                         'linux': pathlib.Path.home() / '.local' / 'share' / 'pcbot'}
    return local_directories[sys.platform]


def get_config():
    config_filename = get_config_filename()
    if not config_filename.exists():
        main()
    logging.info(f'Using config file {config_filename}')
    with open(config_filename, 'r') as f:
        json_config = json.load(f)
        return PcBotConfig(json_config['chat_ids'], json_config['bot_token'])


if __name__ == '__main__':
    main()
