import curses
import curses.textpad
import os
import sys
from signal import signal, SIGWINCH
from math import ceil
import shutil
from .utils import set_config_value, get_config_value
from .logger import logger
from .constants import (
    CONFIG_DIR, CONFIG_FILE, PASSFILE, USER, VERSION, SPLIT_TUNNEL_FILE
)
from . import connection


def settings_tui():
    """Launches the TUI for ProtonVPN settings."""

    # Initializes the main window
    stdscr = curses.initscr()
    rows, cols = stdscr.getmaxyx()

    # Menu options
    menu = ["Username and Password", "ProtonVPN Plan", "Default Protocol",
            "DNS Management", "Kill Switch", "Split Tunneling", "Purge Configuration"] # noqa

    left_window = curses.newwin(ceil(rows - rows/6), ceil(cols/3),
                                ceil(rows / 10), ceil(cols/50))

    right_window = curses.newwin(ceil(rows - rows / 6), ceil(cols/1.63), # noqa
                                 ceil(rows/10), ceil(cols - cols/1.57))

    # curses.window cannot be instantiated, so the below classes cannot inhert
    # from curses.window and functions would have to be reimplemented manually
    class left_menu_scr:
        """Extends the curses.window class to add additional functions."""

        selected_line = 0
        hovered_line = 0
        scr = None

        def __init__(self, left_menu_scr):
            """Initializes the left menu."""
            logger.debug("Initialized left menu")
            self.scr = left_menu_scr

        def update(self):
            """Redraws the left menu when terminal sizes change."""
            scr = self.scr

            rows, cols = stdscr.getmaxyx()
            scr.clear()
            scr.resize(ceil(rows - rows/6), ceil(cols/3))
            scr.mvwin(ceil(rows / 10), ceil(cols/50))
            scr.border()
            self.update_home_page()
            scr.refresh()

        def update_home_page(self):
            """Draws the left side menu and highlights selections."""
            selected_line = self.selected_line
            hovered_line = self.hovered_line

            stdscr.addstr(2, 1, str(selected_line))
            stdscr.addstr(3, 1, str(hovered_line))
            stdscr.refresh()

            # Everything here is going in the left side menu
            scr = self.scr
            rows, cols = scr.getmaxyx()
            j = 2

            scr.clear()
            scr.border()
            # Draws each element in the settings menu
            for i in menu:
                if j - 2 == selected_line and selected_line == hovered_line:
                    scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), "* " + i,
                               curses.A_REVERSE)
                elif j - 2 == hovered_line:
                    scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i, curses.A_REVERSE) # noqa
                elif j - 2 == selected_line:
                    scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), "* " + i,
                               curses.A_BOLD)
                else:
                    scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i)
                j += 1

            scr.refresh()

        def get_selected_line(self):
            """Returns the selected row in the left side menu."""
            return self.selected_line

        def get_hovered_line(self):
            """Returns the line that the highlight is current over on the left side menu."""
            return self.hovered_line

        def set_selected_line(self, new_value):
            """Sets the selected row in the left side menu."""
            assert new_value < len(menu) and 0 <= new_value

            self.selected_line = new_value

        def set_hovered_line(self, new_value):
            """Sets the hovered row in the left side menu."""
            if new_value is None:
                stdscr.addstr(2, 1, "None")
            self.hovered_line = new_value

        def addstr(self, y, x, text, attr=None):
            """Draws a new string in some place on the screen"""
            if attr is None:
                self.scr.addstr(y, x, text)
            else:
                self.scr.addstr(y, x, text, attr)

        def getmaxyx(self):
            """Returns a pair of values y and x that is the current size of window."""
            return self.scr.getmaxyx()

        def clear(self):
            """Clears the screen"""
            self.scr.clear()

        def border(self):
            """Draws a border around the window"""
            self.scr.border()

        def getch(self, y=None, x=None):
            """Get charater and returns ascii code"""
            if y is None and x is None:
                return self.scr.getch()
            elif y is not None and x is not None:
                return self.scr.getch(y, x)

        def resize(self, y, x):
            """Changes the size of the window"""
            self.scr.resize(y, x)

        def mvwin(self, y, x):
            """Moves the window to a new place on the screen"""
            self.scr.mvwin(y, x)

        def refresh(self):
            """Updates window to reflect new changes"""
            self.scr.refresh()

    class right_menu_scr:
        """Extends curses.window for additional methods for right side menu."""

        l_scr = None
        r_scr = None

        def __init__(self, left_menu_scr, right_menu_scr):
            """Initializes extensions for right side menu."""
            self.l_scr = left_menu_scr
            self.r_scr = right_menu_scr

        def update(self):
            """Redraws the right menu when terminal sizes change."""
            rows, cols = stdscr.getmaxyx()
            scr = r_screen

            scr.clear()
            scr.border()
            scr.resize(ceil(rows - rows / 6), ceil(cols/1.63))
            scr.mvwin(ceil(rows/10), ceil(cols - cols/1.57))

            self.launch_current_menu()

            scr.refresh()

        def launch_current_menu(self):
            """Redraws the currently used right side menu."""
            l_scr = self.l_scr
            selected_line = l_scr.get_selected_line()

            if selected_line == 0:
                username_password()
            elif selected_line == 1:
                pvpn_plan()
            elif selected_line == 2:
                default_protocol()
            elif selected_line == 3:
                dns_management()
            elif selected_line == 4:
                kill_switch()
            elif selected_line == 5:
                split_tunneling()
            elif selected_line == 6:
                purge_configuration()

            l_scr.set_hovered_line(selected_line)
            l_scr.update_home_page()

        def addstr(self, y, x, text, attr=None):
            """Draws a new string in some place on the screen"""
            if attr is None:
                self.r_scr.addstr(y, x, text)
            else:
                self.r_scr.addstr(y, x, text, attr)

        def getmaxyx(self):
            """Returns a pair of values y and x that is the current size of window."""
            return self.r_scr.getmaxyx()

        def clear(self):
            """Clears the screen"""
            self.r_scr.clear()

        def border(self):
            """Draws a border around the window"""
            self.r_scr.border()

        def getch(self, y=None, x=None):
            """Gets a character and returns the ascii code as an int"""
            if y is None and x is None:
                return self.r_scr.getch()
            elif y is not None and x is not None:
                return self.r_scr.getch(y, x)

        def resize(self, y, x):
            """Changes the size of the window"""
            self.r_scr.resize(y, x)

        def mvwin(self, y, x):
            """Moves the window to a new place on the screen"""
            self.r_scr.mvwin(y, x)

        def refresh(self):
            """Updates window to reflect new changes"""
            self.r_scr.refresh()

    # Sets the curser to invisible by default
    curses.curs_set(0)

    # Turns off echoing by default
    curses.noecho()

    # Initializes the left side menu
    l_screen = left_menu_scr(left_window)

    # Initializes the right side menu
    r_screen = right_menu_scr(l_screen, right_window)

    def redraw_screen():
        """Redraws the screen when called to make the window responsive to terminal size changes."""
        # Get the screen dimensions after terminal size changes
        rows, cols = stdscr.getmaxyx()

        # Refreshes the main screen, no need to call resize and mvwin here as it
        # automatically adapts to the new screen size
        stdscr.clear()
        stdscr.border()

        # Adds the title at the top
        stdscr.addstr(ceil(rows/22.5), ceil(cols/2 - 12), "ProtonVPN-CLI Settings",  # noqa
                      curses.A_BOLD)

        stdscr.addstr(ceil(rows - rows/22), ceil(cols - (cols - 1)),
                      "Press CTRL-C to exit this menu", curses.A_REVERSE)
        stdscr.refresh()

        # Refreshes the left and right screens to the new
        # screen size
        l_screen.update()
        r_screen.update()

    def resize_handler(signum, frame):
        """Handles the resizing by terminating the current windows and redraws the screen."""
        curses.endwin()
        stdscr.refresh()
        redraw_screen()

    def username_password():
        """Draws the right side window for username and password menu."""
        scr = r_screen
        current_username = get_config_value("USER", "username")
        rows, cols = scr.getmaxyx()

        scr.clear()
        scr.border()

        # Writes in Username and Password Texts
        scr.addstr(ceil(rows / 3.80), ceil(cols / 2 - 9), "OpenVPN Username:",
                   curses.A_BOLD)
        scr.addstr(ceil(rows / 2.3), ceil(cols / 2 - 9), "OpenVPN Password:",
                   curses.A_BOLD)
        scr.refresh()

        # Creates the two text boxes for user input
        username_box = curses.newwin(3, ceil(cols / 3), ceil(rows / 2 - rows/12),
                                     ceil(cols / 1.09))
        password_box = curses.newwin(3, ceil(cols / 3), ceil(rows / 2 + rows/12),
                                     ceil(cols / 1.09))
        username_box.border()
        password_box.border()
        username_box.refresh()
        password_box.refresh()

        # Enable Echoing and curser display
        curses.echo()
        curses.curs_set(2)

        username = ""
        password = ""

        # while True:
        #    input = username_box.getch(y, x)
        #    if input > 31 and input < 126:
        #        username = username + chr(input)

        # Disable echoing and curser display again
        curses.noecho()
        curses.curs_set(0)

        # Write configuration
        set_config_value("USER", "username", username)

        with open(PASSFILE, "w") as f:
            f.write("{0}\n{1}".format(username, password))
            logger.debug("Passfile updated")
            scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15),
                       "Username and Password Updated", curses.A_REVERSE)
            scr.refresh()
            os.chmod(PASSFILE, 0o600)

    def pvpn_plan():
        """Draws the right side window for choosing ProtonVPN Plans."""
        protonvpn_plans = ['ProtonVPN Free', 'ProtonVPN Basic', 'ProtonVPN Plus',
                           'ProtonVPN Visionary']
        scr = r_screen
        selection = 0

        def update_tier_menu(selection=None):
            rows, cols = scr.getmaxyx()
            current_plan = int(get_config_value("USER", "tier"))
            half = ceil(rows / 2 - len(protonvpn_plans))
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 15),
                       "Please select your ProtonVPN plan:", curses.A_BOLD)
            # Draws each tier in the right s
            for i in protonvpn_plans:
                # Display a star and highlight if it is the selection and the
                # current tier in the config file
                if j - half == selection and j - half == current_plan:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), "* " + i,
                               curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i,
                               curses.A_REVERSE)
                # Display a star if it's the current tier but not selected
                elif j - half == current_plan:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), "* " + i,
                               curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i)
                j += 1

            scr.refresh()

        # Initialize Screen
        update_tier_menu(0)

        while 1:
            char1 = scr.getch()
            if char1 not in [None, -1, 410]:
                if char1 in [10, 13]:
                    set_config_value("USER", "tier", selection)
                    scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15), "Tier Updated", # noqa
                               curses.A_REVERSE)
                    # Redraw the window so the asterisk moves immediately
                    update_tier_menu(None)
                    break
                else:
                    char2 = scr.getch()
                    char3 = scr.getch()

                    if char1 == 27 and char2 == 91 and char3 == 65:
                        # Up
                        selection = (selection - 1) % len(protonvpn_plans)
                        update_tier_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 == 66:
                        # Down
                        selection = (selection + 1) % len(protonvpn_plans)
                        update_tier_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        # left and right
                        update_tier_menu(None)
                        break

    def default_protocol():
        """Draws the right side window for choosing the default OpenVPN Protocol."""
        ovpn_protocols = ["udp", "tcp"]
        scr = r_screen
        selection = 0

        def update_protocol_menu(selection=None):
            rows, cols = scr.getmaxyx()
            current_protocol = get_config_value("USER", "default_protocol")
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 22),
                       "Please select your preferred transport protocol:",
                       curses.A_BOLD)

            # Draws each default protocol in the right
            for i in ovpn_protocols:
                # Display a star and highlight if it is the selection
                # and the current protocol in the config file
                if j - half == selection and ovpn_protocols[j - half] == current_protocol: # noqa
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(), # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current default protocol
                # but not selected
                elif ovpn_protocols[j - half] == current_protocol:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper()) # noqa
                j += 1

            scr.refresh()

        update_protocol_menu(0)

        while 1:
            char1 = scr.getch()

            if char1 not in [None, -1, 410]:
                if char1 in [10, 13]:
                    set_config_value("USER", "default_protocol",
                                     ovpn_protocols[selection])
                    # Redraw the window so the asterisk moves immediately
                    update_protocol_menu(None)
                    break
                else:
                    char2 = scr.getch()
                    char3 = scr.getch()

                    if char1 == 27 and char2 == 91 and char3 == 65:
                        # Up
                        selection = (selection - 1) % len(ovpn_protocols)
                        update_protocol_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 == 66:
                        # Down
                        selection = (selection + 1) % len(ovpn_protocols)
                        update_protocol_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        # left and right
                        update_protocol_menu(None)
                        break

    def dns_management():
        """Draws the right side window for choosing to turn on or off DNS leak protection or set custom servers."""
        pass

    def kill_switch():
        """ Draws the right side window for managing killswitch."""
        killswitch_options = ["Disable Kill Switch",
                              "Enable Kill Switch (Block access to/from LAN)",
                              "Enable Kill Switch (Allow access to/from LAN)"]

        scr = r_screen
        selection = 0

        def update_killswitch_menu(selection=None):
            rows, cols = scr.getmaxyx()
            current_config = int(get_config_value("USER", "killswitch"))
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 28),
                       "Please select your preferred killswitch configuration:", # noqa
                       curses.A_BOLD)

            # Draws each killswitch option in the right
            for i in killswitch_options:
                # Display a star and highlight if it is the selection
                # and the current killswitch config in the file
                if j - half == selection and j - half == current_config: # noqa
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(), # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current killswitch config
                # but not selected
                elif j - half == current_config:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper()) # noqa
                j += 1

            scr.refresh()

        update_killswitch_menu(0)

        while 1:
            char1 = scr.getch()

            if char1 not in [None, -1, 410]:
                if char1 in [10, 13]:
                    set_config_value("USER", "killswitch",
                                     selection)
                    # Redraw the window so the asterisk moves immediately
                    update_killswitch_menu(None)
                    break
                else:
                    char2 = scr.getch()
                    char3 = scr.getch()

                    if char1 == 27 and char2 == 91 and char3 == 65:
                        # Up
                        selection = (selection - 1) % len(killswitch_options)
                        update_killswitch_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 == 66:
                        # Down
                        selection = (selection + 1) % len(killswitch_options)
                        update_killswitch_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        # left and right
                        update_killswitch_menu(None)
                        break

    def split_tunneling():
        """Draws the right side window for configuring split tunneling."""
        pass

    def purge_configuration():
        """Draws the right side window for clearing configuration of PVPN-CLI."""
        options = ["yes", "no"]
        scr = r_screen
        selection = 0

        def update_purge_menu(selection=None):
            rows, cols = scr.getmaxyx()
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 28),
                       "Are you sure you want to purge the configuration?",
                       curses.A_BOLD)

            # Draws each killswitch option in the right
            for i in options:
                # Highlight if it is the current selection
                if j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(), # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current killswitch config
                # but not selected
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper()) # noqa
                j += 1

            scr.refresh()

        update_purge_menu(0)

        while 1:
            char1 = scr.getch()

            if char1 not in [None, -1, 410]:
                if char1 in [10, 13]:
                    if selection == 0:
                        connection.disconnect(passed=True)
                        if os.path.isdir(CONFIG_DIR):
                            shutil.rmtree(CONFIG_DIR)
                        curses.endwin()
                        sys.exit(0)
                    else:
                        update_purge_menu(None)
                    break
                else:
                    char2 = scr.getch()
                    char3 = scr.getch()

                    if char1 == 27 and char2 == 91 and char3 == 65:
                        # Up
                        selection = (selection - 1) % len(options)
                        update_purge_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 == 66:
                        # Down
                        selection = (selection + 1) % len(options)
                        update_purge_menu(selection)
                    elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        # left and right
                        update_purge_menu(None)
                        break

    signal(SIGWINCH, resize_handler)

    curses.initscr()

    scr = l_screen

    try:
        # Initial drawing of screen
        redraw_screen()

        temp_row = 0

        selected_line = scr.get_selected_line()
        # For debugging
        assert selected_line >= 0 & selected_line < len(menu)

        while 1:
            assert selected_line <= len(menu) and selected_line >= 0
            assert temp_row <= len(menu) and temp_row >= 0

            char1 = scr.getch()
            if char1 not in [None, -1, 410]:
                if char1 in [10, 13]:
                    # Enter key
                    # Intepreted as select option
                    scr.set_selected_line(temp_row)
                    # Redraw home page so that the updated variant is used
                    scr.set_hovered_line(None)
                    scr.update_home_page()

                    r_screen.launch_current_menu()
                else:
                    char2 = scr.getch()
                    char3 = scr.getch()

                    if char1 == 27 and char2 == 91 and char3 == 65:
                        # Up button
                        temp_row = (temp_row - 1) % len(menu)
                        scr.set_hovered_line(temp_row)
                        scr.update_home_page()
                    elif char1 == 27 and char2 == 91 and char3 == 66:
                        # Down button
                        temp_row = (temp_row + 1) % len(menu)
                        scr.set_hovered_line(temp_row)
                        scr.update_home_page()
                    elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        scr.set_hovered_line(None)
                        scr.update_home_page()
                        r_screen.launch_current_menu()

    except (KeyboardInterrupt, SystemExit):
        curses.endwin()
    except Exception as e:
        # Catches errors caused by resizing the window to too small of a size
        # and also terminates curses before raising the exception
        # so as not to cause breakage of terminal
        if "ERR" in str(e):
            curses.endwin()
            print("[!] ProtonVPN Settings has crashed.")
            print("[!] Please avoid making the terminal window too small")
        else:
            # Terminate curses before crashing so that the terminal \
            # doesn't get screwed up
            curses.endwin()z
            raise e
