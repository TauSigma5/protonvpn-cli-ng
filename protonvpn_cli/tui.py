import curses
from signal import signal, SIGWINCH
from time import sleep
from math import ceil

# Initializes the main window
stdscr = curses.initscr()
rows, cols = stdscr.getmaxyx()

# Initializes the left side menu
left_menu_scr = curses.newwin(ceil(rows - rows/6), ceil(cols/3), ceil(rows / 10),  # noqa
                              ceil(cols/50))

# Initializes the right side menu
right_menu_scr = curses.newwin(ceil(rows - rows / 6), ceil(cols/1.63),
                               ceil(rows/10), ceil(cols - cols/1.57))


def redraw_screen():
    '''Redraws the screen when called to make the window responsive to terminal size changes'''
    # Get the screen dimensions after terminal size changes
    rows, cols = stdscr.getmaxyx()

    # Refreshes the main screen, no need to call resize and mvwin here as it
    # automatically adapts to the new screen size
    stdscr.clear()
    stdscr.border()

    # Adds the title at the top
    stdscr.addstr(ceil(rows/22), ceil(cols/2 - 12), "ProtonVPN-CLI-NG Settings", # noqa
                  curses.A_BOLD)
    stdscr.refresh()

    # Refreshes the left and right screens to the new 
    # screen size
    resize_left_menu()
    resize_right_menu()


def resize_handler(signum, frame):
    '''Handles the resizing by terminating the current windows and redraws the screen'''
    curses.endwin()
    stdscr.refresh()
    redraw_screen()


def resize_left_menu():
    '''Resizes the left menu when terminal sizes change'''
    rows, cols = stdscr.getmaxyx()
    left_menu_scr.clear()
    left_menu_scr.resize(ceil(rows - rows/6), ceil(cols/3))
    left_menu_scr.mvwin(ceil(rows / 10), ceil(cols/50))
    left_menu_scr.border()
    left_menu_scr.refresh()


def resize_right_menu():
    '''Resizes the right menu when terminal sizes change'''
    rows, cols = stdscr.getmaxyx()
    right_menu_scr.clear()
    right_menu_scr.border()
    right_menu_scr.resize(ceil(rows - rows / 6), ceil(cols/1.63))
    right_menu_scr.mvwin(ceil(rows/10), ceil(cols - cols/1.57))
    right_menu_scr.refresh()


# "main" function
signal(SIGWINCH, resize_handler)

curses.initscr()

try:
    redraw_screen()

    while 1:
        sleep(1)

except (KeyboardInterrupt, SystemExit):
    curses.endwin()
except Exception as e:
    # Catches errors caused by resizing the window to too small of a size
    # and also terminates curses before raising the exception
    # so as not to cause breakage of terminal
    if (str(e) == "mvwin() returned ERR"):
        curses.endwin()
        print("[!] ProtonVPN Settings has crashed.")
        print("[!] Please avoid making the terminal window too small")
    else:
        curses.endwin()
        raise e
