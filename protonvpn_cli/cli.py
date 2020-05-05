"""
A CLI for ProtonVPN.

Usage:
    protonvpn init
    protonvpn (c | connect) [<servername>] [-p <protocol>]
    protonvpn (c | connect) [-f | --fastest] [-p <protocol>]
    protonvpn (c | connect) [--cc <code>] [-p <protocol>]
    protonvpn (c | connect) [--sc] [-p <protocol>]
    protonvpn (c | connect) [--p2p] [-p <protocol>]
    protonvpn (c | connect) [--tor] [-p <protocol>]
    protonvpn (c | connect) [-r | --random] [-p <protocol>]
    protonvpn (r | reconnect)
    protonvpn (d | disconnect)
    protonvpn (s | status)
    protonvpn configure
    protonvpn refresh
    protonvpn examples
    protonvpn (-h | --help)
    protonvpn (-v | --version)

Options:
    -f, --fastest       Select the fastest ProtonVPN server.
    -r, --random        Select a random ProtonVPN server.
    --cc CODE           Determine the country for fastest connect.
    --sc                Connect to the fastest Secure-Core server.
    --p2p               Connect to the fastest torrent server.
    --tor               Connect to the fastest Tor server.
    -p PROTOCOL         Determine the protocol (UDP or TCP).
    -h, --help          Show this help message.
    -v, --version       Display version.

Commands:
    init                Initialize a ProtonVPN profile.
    c, connect          Connect to a ProtonVPN server.
    r, reconnect        Reconnect to the last server.
    d, disconnect       Disconnect the current session.
    s, status           Show connection status.
    configure           Change ProtonVPN-CLI configuration.
    refresh             Refresh OpenVPN configuration and server data.
    examples            Print some example commands.

Arguments:
    <servername>        Servername (CH#4, CH-US-1, HK5-Tor).
"""
# Standard Libraries
import sys
import os
import textwrap
import configparser
import getpass
import shutil
import time
# External Libraries
from docopt import docopt
# protonvpn-cli Functions
from . import connection
from .logger import logger
from .utils import (
    check_root, change_file_owner, pull_server_data, make_ovpn_template,
    check_init, set_config_value, get_config_value, is_valid_ip,
    wait_for_network
)
# Constants
from .constants import (
    CONFIG_DIR, CONFIG_FILE, PASSFILE, USER, VERSION, SPLIT_TUNNEL_FILE
)
from .settings_tui import settings_tui


def main():
    """Main function"""
    try:
        cli()
    except KeyboardInterrupt:
        print("\nQuitting...")
        sys.exit(1)


def cli():
    """Run user's input command."""

    # Initial log values
    change_file_owner(os.path.join(CONFIG_DIR, "pvpn-cli.log"))
    logger.debug("###########################")
    logger.debug("### NEW PROCESS STARTED ###")
    logger.debug("###########################")
    logger.debug(sys.argv)
    logger.debug("USER: {0}".format(USER))
    logger.debug("CONFIG_DIR: {0}".format(CONFIG_DIR))

    args = docopt(__doc__, version="ProtonVPN-CLI v{0}".format(VERSION))
    logger.debug("Arguments\n{0}".format(str(args).replace("\n", "")))

    # Parse arguments
    if args.get("init"):
        init_cli()
    elif args.get("c") or args.get("connect"):
        check_root()
        check_init()

        # Wait until a connection to the ProtonVPN API can be made
        # As this is mainly for automatically connecting on boot, it only
        # activates when the environment variable PVPN_WAIT is 1
        # Otherwise it wouldn't connect when a VPN process without
        # internet access exists or the Kill Switch is active
        if int(os.environ.get("PVPN_WAIT", 0)) > 0:
            wait_for_network(int(os.environ["PVPN_WAIT"]))

        protocol = args.get("-p")
        if protocol is not None and protocol.lower().strip() in ["tcp", "udp"]:
            protocol = protocol.lower().strip()

        if args.get("--random"):
            connection.random_c(protocol)
        elif args.get("--fastest"):
            connection.fastest(protocol)
        elif args.get("<servername>"):
            connection.direct(args.get("<servername>"), protocol)
        elif args.get("--cc") is not None:
            connection.country_f(args.get("--cc"), protocol)
        # Features: 1: Secure-Core, 2: Tor, 4: P2P
        elif args.get("--p2p"):
            connection.feature_f(4, protocol)
        elif args.get("--sc"):
            connection.feature_f(1, protocol)
        elif args.get("--tor"):
            connection.feature_f(2, protocol)
        else:
            connection.dialog()
    elif args.get("r") or args.get("reconnect"):
        check_root()
        check_init()
        connection.reconnect()
    elif args.get("d") or args.get("disconnect"):
        check_root()
        check_init()
        connection.disconnect()
    elif args.get("s") or args.get("status"):
        connection.status()
    elif args.get("configure"):
        check_root()
        check_init()
        configure_cli()
    elif args.get("refresh"):
        pull_server_data(force=True)
        make_ovpn_template()
    elif args.get("examples"):
        print_examples()


def init_cli():
    """Initialize the CLI."""

    def init_config_file():
        """"Initialize configuration file."""
        config = configparser.ConfigParser()
        config["USER"] = {
            "username": "None",
            "tier": "None",
            "default_protocol": "None",
            "initialized": "0",
            "dns_leak_protection": "1",
            "custom_dns": "None",
            "check_update_interval": "3",
        }
        config["metadata"] = {
            "last_api_pull": "0",
            "last_update_check": str(int(time.time())),
        }

        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        change_file_owner(CONFIG_FILE)
        logger.debug("pvpn-cli.cfg initialized")

    check_root()

    if not os.path.isdir(CONFIG_DIR):
        os.mkdir(CONFIG_DIR)
        logger.debug("Config Directory created")
    change_file_owner(CONFIG_DIR)

    # Warn user about reinitialization
    try:
        if int(get_config_value("USER", "initialized")):
            print("An initialized profile has been found.")
            overwrite = input(
                "Are you sure you want to overwrite that profile? [y/N]: "
            )
            if overwrite.strip().lower() != "y":
                print("Quitting...")
                sys.exit(1)
            # Disconnect, so every setting (Kill Switch, IPv6, ...)
            # will be reverted (See #62)
            connection.disconnect(passed=True)
    except KeyError:
        pass

    term_width = shutil.get_terminal_size()[0]
    print("[ -- PROTONVPN-CLI INIT -- ]\n".center(term_width))

    init_msg = (
        "ProtonVPN uses two different sets of credentials, one for the "
        "website and official apps where the username is most likely your "
        "e-mail, and one for connecting to the VPN servers.\n\n"
        "You can find the OpenVPN credentials at "
        "https://account.protonvpn.com/account.\n\n"
        "--- Please make sure to use the OpenVPN credentials ---\n"
    ).splitlines()

    for line in init_msg:
        print(textwrap.fill(line, width=term_width))

    # Set ProtonVPN Username and Password
    ovpn_username, ovpn_password = set_username_password(write=False)

    # Set the ProtonVPN Plan
    user_tier = set_protonvpn_tier(write=False)

    # Set default Protocol
    user_protocol = set_default_protocol(write=False)

    protonvpn_plans = {1: "Free", 2: "Basic", 3: "Plus", 4: "Visionary"}

    print()
    print(
        "You entered the following information:\n" +
        "Username: {0}\n".format(ovpn_username) +
        "Password: {0}\n".format("*" * len(ovpn_password)) +
        "Tier: {0}\n".format(protonvpn_plans[user_tier]) +
        "Default protocol: {0}".format(user_protocol.upper())
    )
    print()

    user_confirmation = input(
        "Is this information correct? [Y/n]: "
    ).strip().lower()

    if user_confirmation == "y" or user_confirmation == "":
        print("Writing configuration to disk...")
        init_config_file()

        pull_server_data()
        make_ovpn_template()

        # Change user tier to correct value
        if user_tier == 4:
            user_tier = 3
        user_tier -= 1

        set_config_value("USER", "username", ovpn_username)
        set_config_value("USER", "tier", user_tier)
        set_config_value("USER", "default_protocol", user_protocol)
        set_config_value("USER", "dns_leak_protection", 1)
        set_config_value("USER", "custom_dns", None)
        set_config_value("USER", "killswitch", 0)

        with open(PASSFILE, "w") as f:
            f.write("{0}\n{1}".format(ovpn_username, ovpn_password))
            logger.debug("Passfile created")
            os.chmod(PASSFILE, 0o600)

        set_config_value("USER", "initialized", 1)

        print()
        print("Done! Your account has been successfully initialized.")
        logger.debug("Initialization completed.")
    else:
        print()
        print("Please restart the initialization process.")
        sys.exit(1)


def print_examples():
    """Print some examples on how to use this program"""

    examples = (
        "protonvpn connect\n"
        "               Display a menu and select server interactively.\n\n"
        "protonvpn c BE-5\n"
        "               Connect to BE#5 with the default protocol.\n\n"
        "protonvpn connect NO#3 -p tcp\n"
        "               Connect to NO#3 with TCP.\n\n"
        "protonvpn c --fastest\n"
        "               Connect to the fastest VPN Server.\n\n"
        "protonvpn connect --cc AU\n"
        "               Connect to the fastest Australian server\n"
        "               with the default protocol.\n\n"
        "protonvpn c --p2p -p tcp\n"
        "               Connect to the fastest torrent server with TCP.\n\n"
        "protonvpn c --sc\n"
        "               Connect to the fastest Secure-Core server with\n"
        "               the default protocol.\n\n"
        "protonvpn reconnect\n"
        "               Reconnect the currently active session or connect\n"
        "               to the last connected server.\n\n"
        "protonvpn disconnect\n"
        "               Disconnect the current session.\n\n"
        "protonvpn s\n"
        "               Print information about the current session."
    )

    print(examples)


def configure_cli():
    settings_tui()
