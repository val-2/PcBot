def main():
    import pystray
    import rpyc
    from PIL import Image, ImageDraw
    import time
    from rpyc.utils.server import ThreadPoolServer
    import threading

    def create_image(fill='limegreen'):
        x = 21
        y = x * 5 // 6
        image = Image.new('RGBA', (x + 1, y + 1))
        final_image = Image.new('RGBA', (x + 1, x + 1))
        dc = ImageDraw.Draw(image)

        x0_display = int(x * .1)
        y0_display = int(y * .12)
        x0_stand = int(x * .45)
        y0_stand = int(y * .8)
        x0_base = int(x * .30)
        y0_base = int(y * 39 / 40 + 1)

        dc.rectangle((x0_base, y0_base, x - x0_base, y), fill='lightgray')  # base
        dc.rectangle((x0_stand, y0_stand, x - x0_stand, y0_base), fill='lightgray')  # stand
        dc.rectangle((0, 0, x, y0_stand), fill='white')  # frame
        dc.rectangle((x0_display, y0_display, x - x0_display, y0_stand - y0_display), fill=fill)  # display
        final_image.paste(image, (max(0, (y - x) // 2), max(0, (x - y) // 2)))
        return final_image

    def setup(i):
        i.visible = True
        rpc_server.start()

    class PcBotIconService(rpyc.Service):
        def __init__(self):
            super().__init__()
            self.icon = icon
            self.conn = None

        def on_connect(self, conn):
            self.conn = conn
            self.icon.menu = pystray.Menu(pystray.MenuItem('Debug', self.toggle_debug),
                                          pystray.MenuItem('Exit', self.stop_bot))
            self.exposed_change_image('red')

        def on_disconnect(self, conn):
            self.conn = None
            self.icon.menu = None
            self.icon.update_menu()
            self.exposed_change_image('gray')
            threading.Thread(target=self.stop).start()

        def exposed_change_image(self, fill='limegreen'):
            self.icon.icon = create_image(fill)

        def exposed_visible(self, visible):
            self.icon.visible = visible

        def exposed_notify(self, s):
            self.icon.notify(s)

        def exposed_menu(self, m):
            self.icon.menu = m
            self.icon.update_menu()

        def exposed_update_menu(self):
            self.icon.update_menu()

        def toggle_debug(self):
            self.conn.root.toggle_debug()

        def restart_bot(self):
            self.conn.root.restart_bot()

        def stop_bot(self):
            self.conn.root.stop_bot()
            self.exposed_change_image('gray')

        def stop(self):
            rpc_server.close()
            self.icon.stop()

    rpc_server = ThreadPoolServer(service=PcBotIconService, port=7778)
    icon = pystray.Icon(f'PcBot_{time.time()}')
    icon.icon = create_image('gray')
    icon.run(setup=setup)
