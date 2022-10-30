import logging

import telegram

import pcbot.PcBotCore as Core


class Destiny(Core.DynamicCommand):
    def name(self):
        return 'destiny'

    def description(self):
        return 'Open Destiny 2'

    def requirements(self):
        import sys
        return ['pywinauto', 'pyautogui'] if sys.platform == 'win32' else []

    def can_be_executed(self):
        import sys
        return sys.platform == 'win32'

    def execute(self, update, context):
        import pywinauto
        import time
        import pyautogui
        import subprocess

        pyautogui.FAILSAFE = False

        subprocess.Popen("start steam://rungameid/1085660", shell=True)
        Core.send_message(update, "Starting Destiny 2")
        for _ in range(30):
            if not (wind := pywinauto.Desktop(backend="win32").windows(title_re="Destiny 2", visible_only=True)):
                time.sleep(1)
            else:
                time.sleep(10)
                wind[0].set_focus()
                time.sleep(0.5)
                pyautogui.click()
                break
        Core.send_message(update, "Destiny 2 started")


class Refind(Core.DynamicCommand):
    c = None

    def name(self):
        return 'refind'

    def description(self):
        return 'Change OS'

    def can_be_executed(self):
        return True

    def execute(self, update, context):
        oses = {'Linux': 'Boot @\\boot\\vmlinuz-linux-zen from Arch', 'Windows': 'Boot Microsoft EFI boot from EFI system partition'}
        reply_markup = telegram.ReplyKeyboardMarkup([list(oses.keys())])

        refind_get = self.get_refind_get_function()
        refind_set = self.get_refind_set_function()

        Core.send_message(update, f"Choose or write the wanted OS\nCurrent string:\n{refind_get()}", reply_markup=reply_markup)
        message = Core.msg_queue.get(timeout=None, reset_before_start=False, reset_after_return=True)[0]
        os_str = oses.get(message, message)

        # import os
        # paths = {'linux': '/boot/', 'win32': 'M:/boot/'}
        # value = [i for i in sorted(os.listdir(paths[sys.platform]), key=lambda x: os.path.getmtime(f'{paths[sys.platform]}{x}')) if i[:7] == 'vmlinuz'][-1]
        # value = f'"Boot boot\\{value} from Manjaro"'

        try:
            refind_set(os_str)
        except Exception as e:
            Core.send_message(update, f'Error while setting OS: {repr(e)}', log_level=40, reply_markup=telegram.ReplyKeyboardRemove())
            return

        Core.send_message(update, f'OS set for next reboot. Use /reboot to use it immediately', reply_markup=telegram.ReplyKeyboardRemove())

    def get_refind_get_function(self):
        import sys
        if sys.platform == 'win32':
            return self.refind_win32_get
        elif sys.platform == 'linux':
            return self.refind_linux_get
        else:
            raise NotImplementedError

    def get_refind_set_function(self):
        import sys
        if sys.platform == 'win32':
            return self.refind_win32_set
        elif sys.platform == 'linux':
            return self.refind_linux_set
        else:
            raise NotImplementedError

    def refind_win32_start(self):
        import subprocess
        import rpyc
        import time

        subprocess.Popen(['schtasks', '/RUN', '/TN', '\\Refind\\Refind']).wait()
        logging.info('Refind task started')
        for _ in range(30):
            try:
                self.c = rpyc.connect("localhost", 84758)
                break
            except ConnectionRefusedError:
                logging.info('Waiting for Refind')
                time.sleep(0.5)
        else:
            raise ConnectionRefusedError('Refind not started')
        logging.info('Rpyc connected')

    def refind_win32_get(self):
        if self.c is None:
            self.refind_win32_start()
        logging.info('Getting current OS')
        value = self.c.root.get()
        self.refind_win32_stop()
        return value

    def refind_win32_set(self, value):
        if self.c is None:
            self.refind_win32_start()
        logging.info(f'Setting OS to {value}')
        value = self.c.root.set(value)
        self.refind_win32_stop()
        return value

    def refind_win32_stop(self):
        self.c.close()
        self.c = None
        logging.info('Rpyc closed')

    @staticmethod
    def refind_linux_get():
        import subprocess

        return subprocess.check_output(['refind-next-reboot', 'get'], text=True).strip()

    @staticmethod
    def refind_linux_set(value):
        import subprocess

        return subprocess.check_output(['refind-next-reboot', 'set', value], text=True).strip()


class EnableHotspot(Core.DynamicCommand):
    def name(self):
        return 'enablehotspot'

    def description(self):
        return 'Start Windows hotspot'

    def can_be_executed(self):
        import sys
        return sys.platform == 'win32'

    def execute(self, update, context):
        import subprocess

        Core.send_message(update, "Starting Hotspot...")
        subprocess.check_output(["powershell", "-c", "[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile([Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()).StartTetheringAsync()"])


class DisableHotspot(Core.DynamicCommand):
    def name(self):
        return 'disablehotspot'

    def description(self):
        return 'Stop Windows hotspot'

    def can_be_executed(self):
        import sys
        return sys.platform == 'win32'

    def execute(self, update, context):
        import subprocess

        Core.send_message(update, "Stopping Hotspot...")
        subprocess.check_output(["powershell", "-c", "[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile([Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()).StopTetheringAsync()"])


class AKSRoulette(Core.DynamicCommand):
    wordpress_sec = ''
    wordpress_logged_in = ''

    def name(self):
        return 'aksroulette'

    def description(self):
        return 'Send a message before next probable winner'

    def can_be_executed(self):
        try:
            import aksroulette
            return True
        except ModuleNotFoundError:
            return False

    def execute(self, update, context):
        import aksroulette.analyze
        import time

        try:
            self.refresh_aks_config()
        except FileNotFoundError:
            Core.send_message(update, 'No AKS config found')
            return
        except KeyError:
            Core.send_message(update, 'AKS config is invalid')
            return

        self.request_extension_spin()

        without_message = False

        while True:
            next_win_time = aksroulette.analyze.get_next_win_time()
            wait_time = self.get_wait_time(next_win_time)
            if wait_time > 60 and not without_message:
                Core.send_message(update, f'A message will be sent a minute before: {next_win_time.strftime(aksroulette.time_format)}')
            elif wait_time > -120:
                pass
            else:
                if not without_message:
                    Core.send_message(update, f'Probable next win time has already passed: {next_win_time.strftime(aksroulette.time_format)}\n'
                                              f'A message will be sent a minute before the next probable next win time')
                for i in range(60):
                    time.sleep(60)
                    next_win_time = aksroulette.analyze.get_next_win_time()
                    wait_time = self.get_wait_time(next_win_time)
                    if wait_time > 0:
                        break
                else:
                    if not without_message:
                        Core.send_message(update, 'Even after waiting an hour, no new probable next win time found', log_level=logging.WARNING)
                    return
            self.wait_next_time(next_win_time, update)
            time.sleep(24 * 60 * 60)
            without_message = True

    def wait_next_time(self, next_win_time, update, without_message=False):
        import aksroulette.analyze
        import time

        wait_time = self.get_wait_time(next_win_time)
        if wait_time > 60:
            time.sleep(wait_time - 60)

        aksroulette.main()
        next_win_time = aksroulette.analyze.get_next_win_time()
        wait_time = self.get_wait_time(next_win_time)
        if wait_time > 60:
            self.wait_next_time(next_win_time, update)
            return
        elif wait_time > 0:
            if not without_message:
                Core.send_message(update, f'Probable next winner in a minute: {next_win_time.strftime(aksroulette.time_format)}')
            time.sleep(wait_time)
        if not without_message:
            Core.send_message(update, f'Probable next winner now: {next_win_time.strftime(aksroulette.time_format)}')

        win = self.spin_roulette()
        Core.send_message(update, f'You won {win}')

    @staticmethod
    def get_wait_time(next_win_time):
        import aksroulette.analyze
        import datetime

        return (next_win_time - datetime.datetime.now(tz=aksroulette.preferred_tz)).total_seconds()

    def request_extension_spin(self):
        import requests

        extension_request = requests.post('https://www.allkeyshop.com/blog/wp-admin/admin-ajax.php?action=set_user_extension_enabled', headers={
            'authority': 'www.allkeyshop.com',
            'accept': '*/*',
            'accept-language': 'it,it-IT;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cookie': f'wordpress_sec_9aae1317051b689fdd8093cf69c60dae={self.wordpress_sec}; wordpress_logged_in_9aae1317051b689fdd8093cf69c60dae={self.wordpress_logged_in}; mycred_site_visit=1; _ga=GA1.2.301829975.1651340368; geo-redirect-new=1; _gid=GA1.2.292643820.1661263261; _gat=1',
            'origin': 'https://www.allkeyshop.com',
            'referer': 'https://www.allkeyshop.com/blog/reward-program/',
            'sec-ch-ua': '\"Chromium\";v=\"104\", \" Not A;Brand\";v=\"99\", \"Microsoft Edge\";v=\"104\"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '\"Windows\"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.102 Safari/537.36 Edg/104.0.1293.63',
        })

        if extension_request.text != 'ok':
            raise ConnectionRefusedError('AKS credentials expired')

        return extension_request

    def spin_roulette(self):
        import requests
        import re
        import json

        html_aks = requests.get('https://www.allkeyshop.com/blog/reward-program/').text
        games = re.findall(r'\s+games: \[(\d{3}),(\d{3}),(\d{3}),(\d{3}),(\d{3}),(\d{3}),(\d{3}),(\d{3})],', html_aks)[0]
        data_request = f'action=draw&gameIDs%5B%5D={"&gameIDs%5B%5D=".join(games)}&wheelTier=3&drawModelId=40461&mode=dailyFreeDraw'

        spin_request = requests.post('https://www.allkeyshop.com/blog/wp-admin/admin-ajax.php', headers={
            'authority': 'www.allkeyshop.com',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'it,it-IT;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'cookie': f'wordpress_sec_9aae1317051b689fdd8093cf69c60dae={self.wordpress_sec}; wordpress_logged_in_9aae1317051b689fdd8093cf69c60dae={self.wordpress_logged_in}; mycred_site_visit=1; _ga=GA1.2.301829975.1651340368; geo-redirect-new=1; _gid=GA1.2.292643820.1661263261; _gat=1',
            'origin': 'https://www.allkeyshop.com',
            'referer': 'https://www.allkeyshop.com/blog/reward-program/',
            'sec-ch-ua': '\"Chromium\";v=\"104\", \" Not A;Brand\";v=\"99\", \"Microsoft Edge\";v=\"104\"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '\"Windows\"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.102 Safari/537.36 Edg/104.0.1293.63',
            'x-requested-with': 'XMLHttpRequest'
        }, data=data_request.encode())
        response = json.loads(spin_request.text)
        if response['error']:
            return f'an error: {response["error"]}'

        n_game = response['response']['wonGame']
        win = re.findall(fr'\s+id: {n_game},\s+name: "(.+)",', html_aks)
        return win[0]

    def refresh_aks_config(self):
        import json
        import pathlib
        import sys

        universal_config = pathlib.Path(__file__).parent.parent.absolute() / 'configs' / 'aksconfig.json'
        config_filenames = {'win32': pathlib.Path.home() / 'AppData' / 'Local' / 'pcbot' / 'aksconfig.json',
                            'linux': pathlib.Path.home() / '.config' / 'pcbot' / 'aksconfig.json'}
        user_config = config_filenames[sys.platform]

        possible_configs = {user_config, universal_config}
        for config in possible_configs:
            if config.exists():
                with open(config, 'r') as f:
                    json_config = json.load(f)
                self.wordpress_logged_in = json_config['wordpress_logged_in']
                self.wordpress_sec = json_config['wordpress_sec']
                return
        else:
            raise FileNotFoundError('No config file found')


class Test(Core.DynamicCommand):
    def name(self):
        return 'test'

    def description(self):
        return 'Test'

    def can_be_executed(self):
        return True

    def execute(self, update, context):
        import subprocess
        import time
        import rpyc

        update.message.reply_text('Starting')
        subprocess.Popen(['schtasks', '/RUN', '/TN', '\\Refind\\Refind']).wait()
        update.message.reply_text('Refind started')
        while True:
            try:
                c = rpyc.connect("localhost", 84758)
                break
            except ConnectionRefusedError:
                update.message.reply_text('Waiting for Refind')
                time.sleep(0.5)
        update.message.reply_text('Rpyc connected')
        update.message.reply_text(str(c.root.get()))
        try:
            c.root.close()
            update.message.reply_text('Rpyc closed')
        except EOFError:
            update.message.reply_text('Rpyc not closed')
            pass


dynamic_commands = [Destiny, Refind, EnableHotspot, DisableHotspot, AKSRoulette, Test]
