import curses

stdscr = curses.initscr()
stdscr.border()
curses.curs_set(2)

while True:
    stdscr.getch()
y = 0
