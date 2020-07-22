import curses
import curses.textpad
import os
import sys
from signal import signal, SIGWINCH
from math import ceil
import shutil
import random
from .utils import set_config_value, get_config_value, is_valid_ip
from .logger import logger
from .constants import (
    CONFIG_DIR, PASSFILE, SPLIT_TUNNEL_FILE
)
from . import connection


def settings_tui():
    """Launches the TUI for ProtonVPN settings."""
    # Initializes the main window
    stdscr = curses.initscr()
    rows, cols = stdscr.getmaxyx()
    stdscr.keypad(True)

    left_window = curses.newwin(ceil(rows - rows / 6), ceil(cols / 3),
                                ceil(rows / 10), ceil(cols / 50))

    right_window = curses.newwin(ceil(rows - rows / 6), ceil(cols/1.63),  # noqa
                                 ceil(rows / 10), ceil(cols - cols / 1.57))

    tips_window = curses.newwin(rows - 2, cols - 2, ceil(rows - rows / 22),
                                ceil(cols - (cols - 1)))

    # curses.window cannot be instantiated, so the below classes cannot inhert
    # from curses.window and functions would have to be reimplemented manually
    class basic_window:
        window = None

        def __init__(self, window):
            """Initalizes the window"""
            self.window = window

        def addstr(self, y, x, text, attr=None):
            """Draws a new string in some place on the screen."""
            if attr is None:
                self.window.addstr(y, x, text)
            else:
                self.window.addstr(y, x, text, attr)

        def getmaxyx(self):
            """Returns a pair of values y and x that is the current size of window."""
            return self.window.getmaxyx()

        def clear(self):
            """Clears the screen."""
            self.window.clear()

        def border(self):
            """Draws a border around the window."""
            self.window.border()

        def getch(self, y=None, x=None):
            """Get charater and returns ascii code."""
            if y is None and x is None:
                return self.window.getch()
            elif y is not None and x is not None:
                return self.window.getch(y, x)

        def addch(self, y=None, x=None, ch=None, attr=None):
            if y is None and x is None:
                self.window.addch(ch, attr)
            elif ch is not None and attr is not None:
                self.window.addch(y, x, ch, attr)

        def resize(self, y, x):
            """Changes the size of the window."""
            self.window.resize(y, x)

        def mvwin(self, y, x):
            """Moves the window to a new place on the screen."""
            self.window.mvwin(y, x)

        def refresh(self):
            """Updates window to reflect new changes."""
            self.window.refresh()

        def vline(self, y, x, ch=None, n=None):
            """Draws a vertical line"""
            if ch is None and n is None:
                self.window.vline(y, x)
            else:
                self.window.vline(y, x, ch, n)

        def hline(self, y, x, ch=None, n=None):
            """Draws a horizontal line"""
            if ch is None and n is None:
                self.window.hline(y, x)
            else:
                self.window.hline(y, x, ch, n)

        def keypad(self, flag):
            """Sets if some sequences are ignored or not"""
            self.window.keypad(flag)

    class left_menu_scr(basic_window):
        """Extends the curses.window class to add additional functions."""

        selected_line = None
        hovered_line = 0
        window = None

        def __init__(self, window):
            """Initializes the left menu."""
            logger.debug("Initialized left menu")
            self.window = window

        def update(self):
            """Redraws the left menu when terminal sizes change."""
            scr = self.window

            rows, cols = stdscr.getmaxyx()
            scr.clear()
            scr.resize(ceil(rows - rows / 6), ceil(cols / 3))
            scr.mvwin(ceil(rows / 10), ceil(cols / 50))
            scr.border()
            self.update_home_page()
            scr.refresh()

        def update_home_page(self):
            """Draws the left side menu and highlights selections."""
            selected_line = self.selected_line
            hovered_line = self.hovered_line

            # Everything here is going in the left side menu
            scr = self.window
            rows, cols = scr.getmaxyx()
            j = 2

            scr.clear()
            scr.border()
            # Draws each element in the settings menu
            for i in menus:
                name = i.name
                if j - 2 == selected_line and selected_line == hovered_line:
                    scr.addstr(j * 2, ceil(cols / 2 - len(name) / 2), "* " + name,  # noqa
                               curses.A_REVERSE)
                elif j - 2 == hovered_line:
                    scr.addstr(j * 2, ceil(cols / 2 - len(name) / 2), name, curses.A_REVERSE)  # noqa
                elif j - 2 == selected_line:
                    scr.addstr(j * 2, ceil(cols / 2 - len(name) / 2), "* " + name,  # noqa
                               curses.A_BOLD)
                else:
                    scr.addstr(j * 2, ceil(cols / 2 - len(name) / 2), name)
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
            assert new_value < len(menus) and 0 <= new_value

            self.selected_line = new_value

        def set_hovered_line(self, new_value):
            """Sets the hovered row in the left side menu."""
            if new_value is None:
                stdscr.addstr(2, 1, "None")
            self.hovered_line = new_value

    class right_menu_scr(basic_window):
        """Extends curses.window for additional methods for right side menu."""

        l_scr = None
        window = None

        def __init__(self, left_menu_scr, right_menu_scr):
            """Initializes extensions for right side menu."""
            self.l_scr = left_menu_scr
            self.window = right_menu_scr

        def update(self):
            """Redraws the right menu when terminal sizes change."""
            rows, cols = stdscr.getmaxyx()
            scr = self.window

            scr.clear()
            scr.border()
            scr.resize(ceil(rows - rows / 6), ceil(cols / 1.63))
            scr.mvwin(ceil(rows / 10), ceil(cols - cols / 1.57))

            self.launch_current_menu()

            scr.refresh()

        def launch_current_menu(self):
            """Redraws the currently used right side menu."""
            l_scr = self.l_scr
            selected_line = l_scr.get_selected_line()

            if selected_line is not None:
                menus[selected_line].show()

            l_scr.set_hovered_line(selected_line)
            l_scr.update_home_page()

    class tips_scr(basic_window):
        """Implements additional functions for the tips window"""
        default = "Press CTRL-C to exit ProtonVPN Settings"
        tip = default

        def update(self):
            """Updates the tips screen when window size changes"""
            rows, cols = stdscr.getmaxyx()
            scr = self.window

            scr.clear()
            scr.resize(1, cols - 2)
            scr.mvwin(rows - 2, ceil(cols - (cols - 1)))
            self.tip = self._mystery(self.tip)
            scr.addstr(0, 1, self.tip, curses.A_REVERSE)
            scr.refresh()

        def set_tip(self, str=default):
            """Sets tip screen, defaults to the exit guide if blank"""
            rows, cols = stdscr.getmaxyx()
            scr = self.window
            self.tip = self._mystery(str)

            scr.clear()
            scr.addstr(0, 1, self.tip, curses.A_REVERSE)
            scr.refresh()

        def _mystery(self, str):
            # Shhhhhhhhh
            easter_eggs = ["Look up! It's our servers in the sky!",
                           "Made with <3",
                           "Made globally, hosted in Switzerland!",
                           "Powered by artificial quantum singularities!"]

            if random.randint(0, 500) == 256:
                return easter_eggs[random.randint(0, len(easter_eggs) - 1)]
            else:
                return str

    class textbox(basic_window):
        surrounding_win = None
        contents = ""
        curser_location = [0, 0]

        def __init__(self, uly, ulx, ysize, xsize, insert_mode=False):
            self.win = curses.newwin(ysize, xsize, uly, ulx)
            self.surrounding_win = curses.newwin(ysize + 2, xsize + 2,
                                                 uly - 1, ulx - 1)
            self.surrounding_win.border()
            self.surrounding_win.refresh()

        def refresh(self, uly, ulx, ysize=None, xsize=None):
            surrounding_win = self.surrounding_win
            win = self.win

            y, x = win.getyx()
            win.clear()

            if ysize is not None and xsize is not None:
                win.resize(ysize, xsize)
                win.resize(uly, ulx)
            else:
                win.resize(uly, ulx)

            self.restore_state()
            
            surrounding_win.mvwin(uly - 1, ulx - 1)
            surrounding_win.resize(ysize + 2, xsize + 2)
            surrounding_win.border()
            surrounding_win.refresh()

        def restore_state(self, write=None):
            win = self.win
            if write is None:
                win.addstr(0, 0, self.contents)
            else:
                y, x = self.win.getyx()
                self.win.addstr(y, x, write)

        def add_ch(self, ch):
            self.contents = self.contents + ch

        def del_ch(self):
            y, x = self.win.getyx()
            self.contents = self.contents[:-1]

        
        def edit(self):
            curses.curs_set(2)
            while True:
                ch = self.win.getch()
                if ch == "7":
                    break
                else:
                    self.add_ch(chr(ch))
            curses.curs_set(0)

    class menu(basic_window):
        # Required
        name = ""
        window = None

        # The "assert False"s crashes the programs if you do
        # not change them. This is just a template of requirements.

        def __init__(self, window):
            """Initially called"""
            # This handles initialization and will automatically called
            # when you add it to the list of menus
            # This should remain constant between menus
            self.window = window

        def show(self):
            """Called when that menu item is selected"""
            assert False

        def refresh(self):
            """Called on sigwinch"""
            assert False

    class username_password(menu):
        name = "Username and Password"
        username = ""
        password = ""
        curser_location = 1
        focused_field = None
        username_box = None
        password_box = None

        def show(self):
            scr = self.window
            self.username = get_config_value("USER", "username")

            scr.clear()
            scr.border()

            rows, cols = scr.getmaxyx()

            self.username_box = curses.newwin(3, ceil(cols / 3),
                                              ceil(rows / 2 - rows / 12),
                                              ceil(cols / 1.09))
            self.password_box = curses.newwin(3, ceil(cols / 3),
                                              ceil(rows / 2 + rows / 12),
                                              ceil(cols / 1.09))

            username_box = self.username_box
            password_box = self.password_box
            edit_field = self.edit_field

            # Writes in Username and Password Texts
            scr.addstr(ceil(rows / 4.2), ceil(cols / 2 - 9), "OpenVPN Username:",  # noqa
                       curses.A_BOLD)
            scr.addstr(ceil(rows / 2.5), ceil(cols / 2 - 9), "OpenVPN Password:",  # noqa
                       curses.A_BOLD)
            scr.refresh()

            self.refresh()

            # Enable Echoing and curser display
            curses.curs_set(2)

            self.curser_location = len(self.username) + 1
            self.focused_field = "username"
            edit_field(username_box)
            # reset curser location between boxes
            self.curser_location = 1
            self.focused_field = "password"
            edit_field(password_box)

            # Disable echoing and curser display again
            curses.curs_set(0)

            tips.set_tip(
                "If you want to save and exit, press Enter, if not, just hit the left or right arrow keys.")  # noqa

            char1 = scr.getch()
            if char1 not in [None, -1, 410]:
                if char1 in [10, 13]:
                    # Write configuration
                    set_config_value("USER", "username", self.username)

                    with open(PASSFILE, "w") as f:
                        f.write("{0}\n{1}".format(self.username, self.password))  # noqa
                        logger.debug("Passfile updated")
                        scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15),
                                "Username and Password Updated", curses.A_REVERSE)  # noqa
                        scr.refresh()
                        os.chmod(PASSFILE, 0o600)

                    tips.set_tip()
                elif char1 == 27:
                    char2 = scr.getch()
                    char3 = scr.getch()

                    if char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        tips.set_tip()

        def refresh(self):
            """Updates the window on sigwinch"""
            scr = self.window
            username = self.username
            password = self.password
            username_box = self.username_box
            password_box = self.password_box
            draw_asterisks = self.draw_asterisks

            scr.clear()
            scr.border()

            rows, cols = scr.getmaxyx()

            # Writes in Username and Password Texts
            scr.addstr(ceil(rows / 4.2), ceil(cols / 2 - 9), "OpenVPN Username:",  # noqa
                       curses.A_BOLD)
            scr.addstr(ceil(rows / 2.5), ceil(cols / 2 - 9), "OpenVPN Password:",  # noqa
                       curses.A_BOLD)
            scr.refresh()

            # Updates Username box
            username_box.resize(3, ceil(cols / 2.5))
            username_box.mvwin(ceil(rows / 2 - rows / 12), ceil(cols / 1.13))
            username_box.addstr(1, 1, username)

            # Updates Password box
            password_box.resize(3, ceil(cols / 2.5))
            password_box.mvwin(ceil(rows / 2 + rows / 12), ceil(cols / 1.13))
            password_box.addstr(1, 1, draw_asterisks(len(password)))

            username_box.border()
            password_box.border()
            username_box.refresh()
            password_box.refresh()

        def add_ch(self, char):
            """handles adding of characters for username field"""
            focused_field = self.focused_field
            username_box = self.username_box
            password_box = self.password_box

            if focused_field == "username":
                username_box.addch(1, self.curser_location, char)
                username_box.refresh()
                self.username = self.username + char
            else:
                password_box.addch(1, self.curser_location, "*")
                password_box.refresh()
                self.password = self.password + char

            self.curser_location += 1

        def del_ch(self, field):
            """Handles deleting characters"""

            field.delch(1, self.curser_location - 1)
            field.refresh()
            if self.curser_location != 1:
                self.curser_location -= 1

            if self.focused_field == "username":
                self.username = self.username[:-1]
            else:
                self.password = self.password[:-1]

            # Refresh screen so right side line doesn't get screwed up
            field.clear()
            field.refresh()
            self.refresh()

        def draw_asterisks(self, num):
            asterisks = ""
            for i in range(num):
                asterisks = asterisks + "*"

            return asterisks

        def edit_field(self, field):
            """Handles the username_field textbox"""

            while True:
                char1 = field.getch(1, self.curser_location)

                # Printable ASCII character
                if char1 not in [None, -1, 410]:
                    if char1 in list(range(32, 126)):
                        self.add_ch(chr(char1))
                    elif char1 == 127:
                        self.del_ch(field)
                    elif char1 == 27:
                        # breaks out if up and down arrow keys are detected
                        char2 = field.getch()
                        char3 = field.getch()

                        if char1 == 27 and char2 == 91 and char3 in [65, 66]:
                            break

                    elif char1 in [10, 13]:
                        break

    class pvpn_plan(menu):
        """Draws the right side window for choosing ProtonVPN Plans."""

        name = "ProtonVPN Plan"
        protonvpn_plans = ['ProtonVPN Free', 'ProtonVPN Basic',
                           'ProtonVPN Plus', 'ProtonVPN Visionary']
        selection = 0
        current_plan = None

        def show(self):
            tips.set_tip("Use the up and down arrows to select the option."
                         " Pressing enter saves the choice.")

            update_tier_menu = self.refresh
            protonvpn_plans = self.protonvpn_plans
            scr = self.window
            selection = self.selection

            # Initialize Screen
            update_tier_menu(0)

            while True:
                char1 = scr.getch()
                rows, cols = scr.getmaxyx()
                if char1 not in [None, -1, 410]:
                    if char1 in [10, 13]:
                        set_config_value("USER", "tier", selection)
                        scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15), "Tier Updated",  # noqa
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
            tips.set_tip()

        def refresh(self, selection=None):
            scr = self.window
            protonvpn_plans = self.protonvpn_plans

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
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               "* " + i, curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i,
                               curses.A_REVERSE)
                # Display a star if it's the current tier but not selected
                elif j - half == current_plan:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               "* " + i, curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i)
                j += 1

            scr.refresh()

    class default_protocol(menu):
        """Menu for choosing default openvpn protocol"""
        name = "Default Protocol"
        ovpn_protocols = ["udp", "tcp"]
        selection = 0

        def show(self):
            scr = self.window
            update_protocol_menu = self.refresh
            ovpn_protocols = self.ovpn_protocols
            selection = self.selection

            update_protocol_menu(0)

            while True:
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
            tips.set_tip()

        def refresh(self, selection=None):
            scr = self.window
            ovpn_protocols = self.ovpn_protocols
            instructions = ["OpenVPN can act on two different protocols: UDP and TCP. UDP is preferred for speed but might",  # noqa
                            "be blocked in some networks. TCP is not as fast but a lot harder to block."]  # noqa

            rows, cols = scr.getmaxyx()
            current_protocol = get_config_value("USER", "default_protocol")
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()

            i = 0
            # I'm hella lazy
            for line in instructions:
                scr.addstr(ceil(half / 2.5 + i), ceil(cols / 2 - ceil(len(line)/2)),
                           line,
                           curses.A_BOLD)
                i += 1

            scr.addstr((half - 2), ceil(cols / 2) -
                       ceil(len("Input your preferred protocol. (Default: UDP)") / 2),  # noqa
                       "Input your preferred protocol. (Default: UDP)",
                       curses.A_BOLD)

            # Draws each default protocol in the right
            for i in ovpn_protocols:
                # Display a star and highlight if it is the selection
                # and the current protocol in the config file
                if j - half == selection and ovpn_protocols[j - half] == current_protocol:  # noqa
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(),  # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current default protocol
                # but not selected
                elif ovpn_protocols[j - half] == current_protocol:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper())  # noqa
                j += 1

            scr.refresh()

    class dns_management(menu):
        """Draws the right side window for toggling DNS leak protection and setting custom servers."""
        name = "DNS Management"
        options = ["Disable DNS Management",
                   "Enable DNS Leak Protection (recommended)",
                   "Configure Custom DNS Servers"]
        instructions = ["DNS Leak Protection makes sure that"
                        "you always use ProtonVPN's DNS servers.",
                        "For security reasons enabling leak"
                        "protection is recommended."]

        selection = 0
        current_config = None
        menu_state = 0
        textbox = None
        dns_content = ""

        def show(self):
            refresh = self.refresh
            options = self.options
            scr = self.window

            rows, cols = scr.getmaxyx()

            scr.clear()
            scr.border()

            tips.set_tip("Use the up and down arrows to select the option."
                         " Pressing enter saves the choice.")

            self.current_config = int(get_config_value("USER", "dns_leak_protection"))  # noqa

            # Check if there are custom DNS servers set
            if self.current_config == 0:
                if self.dns_content != "None":
                    self.dns_content = get_config_value(
                        "USER", "custom_dns").replace(", ", "\n")
                    self.current_config = 2

            refresh()

            while True:
                char1 = scr.getch()

                if char1 not in [None, -1, 410]:
                    if char1 in [10, 13]:
                        if self.selection == 0:
                            # Disable DNS management
                            set_config_value("USER", "dns_leak_protection",
                                             0)
                            set_config_value("USER", "custom_dns", "None")
                            scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15),
                                       "DNS Management Settings Updated", curses.A_REVERSE) # noqa
                            scr.refresh()
                        elif self.selection == 1:
                            # Enable DNS Management
                            set_config_value("USER", "dns_leak_protection",
                                             1)
                            set_config_value("USER", "custom_dns", "None")
                            scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15),
                                       "DNS Management Settings Updated", curses.A_REVERSE) # noqa
                            scr.refresh()
                        else:
                            # Use Custom DNS, show submenu
                            set_config_value("USER", "dns_leak_protection",
                                             0)
                            self.show_second_menu()

                        # Redraw the window so the asterisk moves immediately
                        self.current_config = self.selection
                        refresh()
                        break
                    else:
                        char2 = scr.getch()
                        char3 = scr.getch()

                        if char1 == 27 and char2 == 91 and char3 == 65:
                            # Up
                            self.selection = (self.selection - 1) % len(options)  # noqa
                            refresh(self.selection)
                        elif char1 == 27 and char2 == 91 and char3 == 66:
                            # Down
                            self.selection = (self.selection + 1) % len(options)  # noqa
                            refresh(self.selection)
                        elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                            # left and right
                            refresh()
                            break
            tips.set_tip()

        def refresh(self, selection=None):
            options = self.options
            scr = self.window
            instructions = self.instructions

            rows, cols = scr.getmaxyx()

            if self.menu_state == 0:
                # refresh menu 1

                half = ceil(rows / 2 - 2)
                j = half

                i = 0
                # I'm hella lazy
                for line in instructions:
                    scr.addstr(half - len(instructions) - 2 + i,
                               ceil(cols / 2 - len(line)/2), line,
                               curses.A_BOLD)
                    i += 1

                # Draws each DNS config in the right
                for i in options:
                    # Display a star and highlight if it is the selection
                    # in the config file
                    if j - half == self.selection and j - half == self.current_config:  # noqa
                        scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                                   ("* " + i).upper(), curses.A_REVERSE)
                    # Highlight if it is the current selection
                    elif j - half == self.selection:
                        scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(),  # noqa
                                   curses.A_REVERSE)
                    # Display a star if it's the current default protocol
                    # but not selected
                    elif j - half == self.current_config:
                        scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                                   ("* " + i).upper(), curses.A_BOLD)
                    else:
                        scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper())  # noqa
                    j += 1

                scr.refresh()
            elif self.menu_state == 1:
                # refresh menu 2
                scr.clear()
                scr.border()
                curses.curs_set(0)

                scr.addstr(ceil(rows / 2 - 7), ceil(cols / 2 - 25),
                           "Please enter IP address(es) of your DNS Resolvers",
                           curses.A_BOLD)
                scr.refresh()

                self.textbox.refresh(ceil(rows / 1.75 - 2), cols + 1, 4, 16)

        def show_second_menu(self):
            scr = self.window
            rows, cols = scr.getmaxyx()

            self.menu_state = 1

            tips.set_tip("Enter 1 IP per line and hit CTRL-G when done.")

            scr.clear()
            scr.border()

            scr.addstr(ceil(rows / 2 - 7), ceil(cols / 2 - 25),
                       "Please enter IP address(es) of your DNS Resolvers",
                       curses.A_BOLD)

            scr.refresh()

            self.textbox = textbox(ceil(rows / 1.75 - 2), cols + 1, 4, 16)

            # Fill in previous config if available
            if self.dns_content != "":
                self.textbox.restore_state(self.dns_content.replace(", ", "\n"))

            # Enable Echoing and curser display
            curses.curs_set(2)

            valid_ips = False

            while not valid_ips:
                rows, cols = scr.getmaxyx()
                
                # Get user input
                self.textbox.edit()
                self.dns_content = self.textbox.contents

                # Check for errors
                dns_content = self.dns_content
                dns_servers = dns_content.split("\n")

                # Throws error if no servers were entered
                if len(dns_servers) < 1:
                    scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 21),
                               "[!] Please enter at least one DNS Server!",
                               curses.A_REVERSE)

                # Checks if IPs are valid and format them
                i = 0
                valid_ips = True

                # Remove whitespaces and removes empty elements
                for x in dns_servers:
                    dns_servers[i] = x.strip()
                    if dns_servers[i] == "":
                        del dns_servers[i]
                    i += 1

                # Check if IPs are valid
                for x in dns_servers:
                    if not is_valid_ip(x):
                        valid_ips = False

                if not valid_ips:
                    scr.addstr(ceil(rows / 1.5), ceil(cols / 4 - 7),
                               "[!] Please enter valid IPv4 addresses!",
                               curses.A_REVERSE)

                scr.refresh()

            # Reset Terminal
            curses.curs_set(0)
            tips.set_tip()
            self.write_configuration(dns_servers)

        def write_configuration(self, dns_servers):
            set_config_value("USER", "custom_dns", ", ".join(dns_servers))
            rows, cols = self.window.getmaxyx()
            self.window.addstr(ceil(rows / 1.5), ceil(cols - 10),
                            "DNS Management Settings Updated", curses.A_REVERSE) # noqa
            self.window.refresh()

    class killswitch(menu):
        """ Draws the right side window for managing killswitch."""
        killswitch_options = ["Disable Kill Switch",
                              "Enable Kill Switch (Block access to/from LAN)",
                              "Enable Kill Switch (Allow access to/from LAN)"]
        window = None
        selection = 0
        name = "Killswitch Configuration"

        def show(self):
            update_killswitch_menu = self.refresh
            selection = self.selection
            scr = self.window
            killswitch_options = self.killswitch_options

            tips.set_tip("Use the up and down arrows to select the option."
                         " Pressing enter saves the choice.")

            update_killswitch_menu(0)

            while True:
                char1 = scr.getch()

                if char1 not in [None, -1, 410]:
                    if char1 in [10, 13]:
                        set_config_value("USER", "killswitch",
                                         selection)
                        # Redraw the window so the asterisk moves immediately
                        update_killswitch_menu()
                        break
                    else:
                        char2 = scr.getch()
                        char3 = scr.getch()

                        if char1 == 27 and char2 == 91 and char3 == 65:
                            # Up
                            selection = (
                                selection - 1) % len(killswitch_options)
                            update_killswitch_menu(selection)
                        elif char1 == 27 and char2 == 91 and char3 == 66:
                            # Down
                            selection = (
                                selection + 1) % len(killswitch_options)
                            update_killswitch_menu(selection)
                        elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                            # left and right
                            update_killswitch_menu()
                            break
            tips.set_tip()

        def refresh(self, selection=None):
            scr = self.window
            killswitch_options = self.killswitch_options
            rows, cols = scr.getmaxyx()
            current_config = int(get_config_value("USER", "killswitch"))
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 28),
                       "Please select your preferred killswitch configuration:",  # noqa
                       curses.A_BOLD)

            # Draws each killswitch option in the right
            for i in killswitch_options:
                # Display a star and highlight if it is the selection
                # and the current killswitch config in the file
                if j - half == selection and j - half == current_config:  # noqa
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(),  # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current killswitch config
                # but not selected
                elif j - half == current_config:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper())  # noqa
                j += 1

            scr.refresh()

    class split_tunneling(menu):
        """Draws right side menu for split tunneling"""
        name = "Split Tunneling"
        options = ["Disable Split Tunneling", "Enable Split Tunneling"]
        selection = 0
        current_config = 0

        def show(self):
            refresh = self.refresh
            options = self.options
            scr = self.window

            self.current_config = int(get_config_value("USER", "split_tunnel"))  # noqa

            scr.clear()
            scr.border()

            refresh(0)

            tips.set_tip("Use the up and down arrows to select the option."
                         " Pressing enter saves the choice.")

            while True:
                char1 = scr.getch()

                if char1 not in [None, -1, 410]:
                    if char1 in [10, 13]:
                        if self.selection == 0:
                            # Enable Split Tunneling
                            set_config_value("USER", "split_tunnel", 0)
                        else:
                            # Disable Split Tunneling
                            set_config_value("USER", "split_tunnel", 1)

                        # Redraw the window so the asterisk moves immediately
                        self.current_config = self.selection
                        refresh()
                        break
                    else:
                        char2 = scr.getch()
                        char3 = scr.getch()

                        if char1 == 27 and char2 == 91 and char3 == 65:
                            # Up
                            self.selection = (self.selection - 1) % len(options)  # noqa
                            refresh(self.selection)
                        elif char1 == 27 and char2 == 91 and char3 == 66:
                            # Down
                            self.selection = (self.selection + 1) % len(options)  # noqa
                            refresh(self.selection)
                        elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                            # left and right
                            refresh()
                            break
            tips.set_tip()

        def refresh(self, selection=None):
            scr = self.window
            options = self.options
            rows, cols = scr.getmaxyx()
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 28),
                       "Please select your preferred Split Tunneling configuration:",  # noqa
                       curses.A_BOLD)

            # Draws each killswitch option in the right
            for i in options:
                # Display a star and highlight if it is the selection
                # and the current killswitch config in the file
                if j - half == selection and j - half == self.current_config:  # noqa
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(),  # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current killswitch config
                # but not selected
                elif j - half == self.current_config:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2),
                               ("* " + i).upper(), curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper())  # noqa
                j += 1

            scr.refresh()

        def show_secondary_menu(self):
            scr = self.window
            rows, cols = scr.getmaxyx()

            self.menu_state = 1

            tips.set_tip("Enter 1 IP or IP Range per line and hit CTRL-G when done.") # noqa

            scr.clear()
            scr.border()

            scr.addstr(ceil(rows / 2 - 7), ceil(cols / 2 - 25),
                       "Please enter IP address(es) or IP ranges in CIDR"
                       "notation to Exclude:",
                       curses.A_BOLD)

            scr.refresh()

            rows, cols = stdscr.getmaxyx()
            self.surrounding_win = curses.newwin(6, 18, ceil(rows / 2 - 3),
                                                 ceil(cols - cols / 3 - 8))
            self.surrounding_win.border()
            self.surrounding_win.refresh()
            self.textbox_win = curses.newwin(4, 16, ceil(rows / 2 - 2),
                                             ceil(cols - cols / 3 - 7))
            self.textbox = curses.textpad.Textbox(self.textbox_win)

            # Enable Echoing and curser display
            curses.curs_set(2)

            valid_ips = False

            while not valid_ips:
                # Get user input
                self.textbox.edit()
                self.dns_content = self.textbox.gather()

                # Check for errors
                dns_content = self.dns_content
                dns_servers = dns_content.split("\n")

                # Throws error if no servers were entered
                if len(dns_servers) < 1:
                    scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 21),
                               "[!] Please enter at least one DNS Server!",
                               curses.A_REVERSE)

                # Checks if IPs are valid and format them
                i = 0
                valid_ips = True

                # Remove whitespaces and removes empty elements
                for x in dns_servers:
                    dns_servers[i] = x.strip()
                    if dns_servers[i] == "":
                        del dns_servers[i]
                    i += 1

                # Check if IPs are valid
                for x in dns_servers:
                    if not is_valid_ip(x):
                        valid_ips = False

                if not valid_ips:
                    scr.addstr(ceil(rows / 1.5), ceil(cols / 4 - 7),
                               "[!] Please enter valid IPv4 addresses!",
                               curses.A_REVERSE)

                scr.refresh()

            # Reset Terminal
            curses.curs_set(0)
            tips.set_tip()
            self.write_configuration(dns_servers)

        def write_configuration(self, dns_servers):
            set_config_value("USER", "custom_dns", ", ".join(dns_servers))

    class purge_configuration(menu):
        """Draws right side menu for purge configuration page"""
        name = "Purge Configuration"
        options = ["yes", "no"]
        selection = 0

        def show(self):
            update_purge_menu = self.refresh
            selection = self.selection
            options = self.options
            scr = self.window

            update_purge_menu(0)

            while True:
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

        def refresh(self, selection=None):
            scr = self.window
            options = self.options

            rows, cols = scr.getmaxyx()
            half = ceil(rows / 2 - 2)
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 24),
                       "Are you sure you want to purge the configuration?",
                       curses.A_BOLD)

            # Draws each killswitch option in the right
            for i in options:
                # Highlight if it is the current selection
                if j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper(),  # noqa
                               curses.A_REVERSE)
                # Display a star if it's the current killswitch config
                # but not selected
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i.upper())  # noqa
                j += 1

            scr.refresh()

    def redraw_screen():
        """Redraws the screen when called to make the window responsive to terminal size changes."""
        # Get the screen dimensions after terminal size changes
        rows, cols = stdscr.getmaxyx()

        # Refreshes the main screen, no need to call resize and mvwin here as
        # it automatically adapts to the new screen size
        stdscr.clear()
        stdscr.border()

        # Adds the title at the top
        stdscr.addstr(ceil(rows / 22.5), ceil(cols / 2 - 12),
                      "ProtonVPN-CLI Settings", curses.A_BOLD)
        stdscr.refresh()

        tips.update()

        # Refreshes the left and right screens to the new
        # screen size
        l_screen.update()
        r_screen.update()

    def resize_handler(signum, frame):
        """Handles the resizing by terminating the current windows and redraws the screen."""
        curses.endwin()
        stdscr.refresh()
        redraw_screen()

    # Sets the curser to invisible by default
    curses.curs_set(0)

    # Turns off echoing by default
    curses.noecho()

    # Initializes the left side menu
    l_screen = left_menu_scr(left_window)

    # Initializes the right side menu
    r_screen = right_menu_scr(l_screen, right_window)

    # Initializes the tips window
    tips = tips_scr(tips_window)

    # Add new menus here:
    uninitialized_menus = [username_password, pvpn_plan, default_protocol,
                           dns_management, killswitch, split_tunneling,
                           purge_configuration]

    # This is a list of menu objects that are used
    menus = []

    # Initializes the menu objects
    for menu in uninitialized_menus:
        menus.append(menu(r_screen))

    signal(SIGWINCH, resize_handler)
    curses.initscr()
    scr = l_screen

    try:
        # Initial drawing of screen
        redraw_screen()
        l_screen.set_hovered_line(0)
        l_screen.update()

        temp_row = 0

        while True:
            assert temp_row <= len(menus) and temp_row >= 0

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
                        temp_row = (temp_row - 1) % len(menus)
                        scr.set_hovered_line(temp_row)
                        scr.update_home_page()
                    elif char1 == 27 and char2 == 91 and char3 == 66:
                        # Down button
                        temp_row = (temp_row + 1) % len(menus)
                        scr.set_hovered_line(temp_row)
                        scr.update_home_page()
                    elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                        # Left and Right Button
                        scr.set_hovered_line(None)
                        scr.update_home_page()
                        r_screen.launch_current_menu()

    except (KeyboardInterrupt, SystemExit):
        curses.endwin()
    except Exception as e:
        # Catches errors and reraise them after restoring the window
        # to its original state, so the terminal doesn't get screwed up
        curses.endwin()
        raise e
