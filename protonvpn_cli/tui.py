import curses
from signal import signal, SIGWINCH
from math import ceil

def settings_tui():
    # Initializes the main window
    stdscr = curses.initscr()
    rows, cols = stdscr.getmaxyx()

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

    # current_row is the one user has selected and determines the menu displayed
    # on the right side Menu
    global current_row
    # focused_row keeps track of what the user is hovering over on the left side
    # menu.
    global focused_row
    # Keeps tracking of which one is selected and which windows should be taking
    # inputs
    global focused_window
    current_row = 0
    focused_row = 0
    focused_window = "left"
    windows = ["left", "right"]

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
        stdscr.addstr(ceil(rows/22.5), ceil(cols/2 - 12), "ProtonVPN-CLI-NG Settings",  # noqa
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
        draw_home_page(current_row)
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
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i, curses.A_REVERSE)
            elif j - 2 == focused_row:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i, curses.A_REVERSE)
            elif j - 2 == selected_row:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i, curses.A_BOLD)
            else:
                scr.addstr(j * 2, ceil(cols / 2 - len(i) / 2), i)
            j += 1

        scr.refresh()


    def username_password():
        '''Draws the right side window for username and password menu'''
        scr = right_menu_scr
        rows, cols = scr.getmaxyx()

        scr.addstr(rows / 4, cols / 2 - 9, "Username:")
        username_tb = curses.textpad.Textbox(scr, rows / 3.5, cols / 1.5, rows / 2, cols / 1.5)
        username = tb.edit()


    signal(SIGWINCH, resize_handler)

    curses.initscr()

    try:
        # Redraws the screen when there are window updates
        redraw_screen()
        # Temporary store so that moving around selection on the left side doesn't change right side menu
        temp_row = 0
        while 1:
            assert focused_window in windows
            if focused_window == "left":
                key = left_menu_scr.getch()

                if key == 65:
                    # Up button
                    temp_row = temp_row - 1
                    draw_home_page(current_row, (temp_row) % len(menu))
                elif key == 66:
                    # Down button
                    temp_row = temp_row + 1
                    draw_home_page(current_row, (temp_row) % len(menu))
                elif key == 68:
                    # Left button
                    focused_window = "right"
                    draw_home_page(current_row, None)
                elif key == 67:
                    # Right button
                    focused_window = "right"
                    draw_home_page(current_row, None)
                elif key in [10, 13]:
                    # Enter key
                    # Intepreted as select option
                    focused_window = "right"
                    current_row = temp_row
                    # Redraw home page so that the updated font variant is used
                    draw_home_page(current_row, None)
            elif focused_window == "right":
                key = left_menu_scr.getch()

                if key == 68:
                    # Left button
                    focused_window = "left"
                    draw_home_page(current_row, current_row)
                    temp_row = current_row
                elif key == 67:
                    # Right button
                    focused_window = "right"
                    draw_home_page(current_row, current_row)
                    temp_row = current_row

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


settings_tui()
