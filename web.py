import argparse

from poller import Poller
from config import Config
class Main:
    """ Parse command line options and perform the download. """
    def __init__(self):
        self.parse_arguments()
        self.conf = Config('./web.conf')

    def parse_arguments(self):
        ''' parse arguments, which include '-p' for port '''
        parser = argparse.ArgumentParser(prog='Echo Server', description='A simple echo server that handles one client at a time', add_help=True)
        parser.add_argument('-p', '--port', type=int, action='store', help='port the server will bind to',default=8080)
        parser.add_argument('-d', type=bool)
        self.args = parser.parse_args()

    def run(self):
        p = Poller(self.args.port, self.conf)
        p.run()

if __name__ == "__main__":
    m = Main()
    m.parse_arguments()
    try:
        m.run()
    except KeyboardInterrupt:
        pass