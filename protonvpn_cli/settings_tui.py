import curses
import curses.textpad
import os
from signal import signal, SIGWINCH
from math import ceil
from time import sleep
from .utils import set_config_value, get_config_value
from .constants import PASSFILE
from .logger import logger

def settings_tui():
    # Initializes the main window
    stdscr = curses.initscr()
    rows, cols = stdscr.getmaxyx()

    current_row = 0
    focused_row = 0
    username = ""
    password = ""

    # Sets the curser to invisible by default
    curses.curs_set(0)

    # Turns off echoing by default
    curses.noecho()

    # Initializes the left side menu
    left_menu_scr = curses.newwin(ceil(rows - rows/6), ceil(cols/3), ceil(rows / 10),  # noqa
                                  ceil(cols/50))

    # Initializes the right side menu
    right_menu_scr = curses.newwin(ceil(rows - rows / 6), ceil(cols/1.63),
                                   ceil(rows/10), ceil(cols - cols/1.57))

    # Menu options
    menu = ["Username and Password", "ProtonVPN Plan", "Default Protocol",
            "DNS Management", "Kill Switch", "Split Tunneling", "Purge Configuration"]


    def redraw_screen():
        '''Redraws the screen when called to make the window responsive to terminal size changes'''
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
        draw_left_menu()
        draw_right_menu()


    def resize_handler(signum, frame):
        '''Handles the resizing by terminating the current windows and redraws the screen'''
        curses.endwin()
        stdscr.refresh()
        redraw_screen()


    def draw_left_menu():
        '''Redraws the left menu when terminal sizes change'''
        rows, cols = stdscr.getmaxyx()
        left_menu_scr.clear()
        left_menu_scr.resize(ceil(rows - rows/6), ceil(cols/3))
        left_menu_scr.mvwin(ceil(rows / 10), ceil(cols/50))
        left_menu_scr.border()
        draw_home_page()
        left_menu_scr.refresh()


    def draw_right_menu():
        '''Redraws the right menu when terminal sizes change'''
        rows, cols = stdscr.getmaxyx()
        right_menu_scr.clear()
        right_menu_scr.border()
        right_menu_scr.resize(ceil(rows - rows / 6), ceil(cols/1.63))
        right_menu_scr.mvwin(ceil(rows/10), ceil(cols - cols/1.57))
        right_menu_scr.refresh()


    def draw_home_page(selected_row=current_row, focused_row=current_row):
        '''Draws the left side menu and highlights selections'''
        assert selected_row >= 0 & selected_row < len(menu)

        # Everything here is going in the left side menu
        scr = left_menu_scr
        rows, cols = scr.getmaxyx()
        j = 2

        scr.clear()
        scr.border()
        # Draws each element in the settings menu
        for i in menu:
            if j - 2 == selected_row and selected_row == focused_row:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), "* " + i, curses.A_REVERSE)
            elif j - 2 == focused_row:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i, curses.A_REVERSE)
            elif j - 2 == selected_row:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), "* " + i, curses.A_BOLD)
            else:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i)
            j += 1

        scr.refresh()


    def username_password():
        '''Draws the right side window for username and password menu'''
        scr = right_menu_scr
        current_username = get_config_value("USER", "username")
        rows, cols = scr.getmaxyx()

        scr.clear()
        scr.border()

        # Writes in Username and Password Texts
        scr.addstr(ceil(rows / 3.80), ceil(cols / 2 - 9), "OpenVPN Username:", curses.A_BOLD)
        scr.addstr(ceil(rows / 2.3), ceil(cols / 2 - 9), "OpenVPN Password:", curses.A_BOLD)
        scr.refresh()

        # Creates the two text boxes for user input
        username_box = curses.newwin(3, ceil(cols / 3), ceil(rows / 2 - rows/12), ceil(cols / 1.09))
        password_box = curses.newwin(3, ceil(cols / 3), ceil(rows / 2 + rows/12), ceil(cols / 1.09))
        username_box.border()
        password_box.border()
        username_box.refresh()
        password_box.refresh()

        # Enable Echoing and curser display
        curses.echo()
        curses.curs_set(2)

        username = ""

        while true:
            input = username_box.getch(y, x)
            if input > 31 and input < 126:
                username = username + chr(input)

        #Disable echoing and curser display again
        curses.noecho()
        curses.curs_set(0)


        # Write configuration
        set_config_value("USER", "username", username)

        with open(PASSFILE, "w") as f:
            f.write("{0}\n{1}".format(username, password))
            logger.debug("Passfile updated")
            scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15), "Username and Password Updated", curses.A_REVERSE)
            scr.refresh()
            os.chmod(PASSFILE, 0o600)


    def pvpn_plan():
        '''Draws the right side window for choosing ProtonVPN Plans'''
        protonvpn_plans = ['ProtonVPN Free', 'ProtonVPN Basic', 'ProtonVPN Plus', 'ProtonVPN Visionary']
        scr = right_menu_scr
        selection = 0

        def update_tier_menu(selection=None):
            rows, cols = scr.getmaxyx()
            current_plan = int(get_config_value("USER", "tier"))
            half = ceil(rows / 2 - len(protonvpn_plans))
            j = half

            scr.clear()
            scr.border()
            scr.addstr(half - 3, ceil(cols / 2 - 15), "Please select your ProtonVPN plan:", curses.A_BOLD)
            # Draws each tier in the right s
            for i in protonvpn_plans:
                # Display a star and highlight if it is the selection and the current tier in the config file
                if j - half == selection and j - half == current_plan:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), "* " + i, curses.A_REVERSE)
                # Highlight if it is the current selection
                elif j - half == selection:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i, curses.A_REVERSE)
                # Display a star if it's the current tier but not selected
                elif j - half == current_plan:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), "* " + i, curses.A_BOLD)
                else:
                    scr.addstr(j + j - half, ceil(cols / 2 - len(i) / 2), i)
                j += 1

            scr.refresh()

        # Initialize Screen
        update_tier_menu()

        while 1:
            char1 = scr.getch()
            if char1 in [10, 13]:
                set_config_value("USER", "tier", selection)
                scr.addstr(ceil(rows / 1.5), ceil(cols / 2 - 15), "Tier Updated", curses.A_REVERSE)
                # Redraw the window so the asterisk moves immediately
                update_tier_menu(None)
                break
            else:
                char2 = scr.getch()
                char3 = scr.getch()

                if char1 == 27 and char2 == 91 and char3 == 65:
                    selection = (selection - 1) % len(protonvpn_plans)
                    update_tier_menu(selection)
                elif char1 == 27 and char2 == 91 and char3 == 66:
                    selection = (selection + 1) % len(protonvpn_plans)
                    update_tier_menu(selection)
                elif char1 == 27 and char2 == 91 and char3 in [67, 68]:
                    # Left Button
                    update_tier_menu(None)
                    break


    def default_protocol():
        '''Draws the right side window for choosing the default OpenVPN Protocol'''
        pass


    def dns_management():
        '''Draws the right side window for choosing to turn on or off DNS leak protection or set custom servers'''
        pass


    def kill_switch():
        ''' Draws the right side window for managing killswitch'''
        pass


    def split_tunneling():
        '''Draws the right side window for configuring split tunneling'''
        pass


    def purge_configuration():
        '''Draws the right side window for clearing configuration of PVPN-CLI'''
        pass


    # Beginning of the "main" function
    signal(SIGWINCH, resize_handler)

    curses.initscr()

    try:
        # Initial drawing of screen
        redraw_screen()
        # Temporary store so that moving around selection on the left side doesn't change right side menu
        temp_row = 0

        while 1:
            assert current_row <= len(menu)
            assert temp_row <= len(menu)

            char1 = left_menu_scr.getch()

            if char1 in [10, 13]:
                # Enter key
                # Intepreted as select option
                current_row = temp_row
                # Redraw home page so that the updated variant is used
                draw_home_page(current_row, None)

                # Make sure a valid input was used
                assert current_row >= 0 & current_row < len(menu)

                if current_row == 0:
                    username_password()
                elif current_row == 1:
                    pvpn_plan()
                    draw_home_page(current_row, current_row)
                elif current_row == 2:
                    default_protocol()
                elif current_row == 3:
                    dns_management()
                elif current_row == 4:
                    kill_switch()
                elif current_row == 5:
                    split_tunneling()
                elif current_row == 6:
                    purge_configuration()
            else:
                char2 = left_menu_scr.getch()
                char3 = left_menu_scr.getch()

                if char1 == 27 and char2 == 91 and char3 == 65:
                    # Up button
                    temp_row = (temp_row - 1) % len(menu)
                    draw_home_page(current_row, temp_row)
                elif char1 == 27 and char2 == 91 and char3 == 66:
                    # Down button
                    temp_row = (temp_row + 1) % len(menu)
                    draw_home_page(current_row, temp_row)


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
            # Terminate curses before crashing so that the terminal doesn't get screwed up
            curses.endwin()
            raise e
