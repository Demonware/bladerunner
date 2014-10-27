#coding: utf-8
"""Progress bar and terminal width functions for Bladerunner.

This file is part of Bladerunner.

Copyright (c) 2014, Activision Publishing, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of Activision Publishing, Inc. nor the names of its
  contributors may be used to endorse or promote products derived from this
  software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


from __future__ import division, unicode_literals

import os
import sys
import time
import argparse

try:
    import fcntl
    import termios
    import struct
except ImportError:
    pass


class ProgressBar(object):
    """A simple textual progress bar.

    Args::

        total_updates: an integer of how many times update() will be called
        options: a dictionary of additional options. schema:
            width: an integer for fixed terminal width printing
            style: an integer style, between 0-2
            show_counters: a boolean to declare showing the counters or not
            left_padding: a string to pad the left side of the bar with
            right_padding: a string to pad the right side of the bar with
    """

    def __init__(self, total_updates, options=None):
        """Initializes the object with the options provided."""

        self.total = total_updates

        if options is None:
            options = {}

        self.total_width = options.get('width') or get_term_width()

        self.counter = 0  # update counter
        self.chars = {
            "left": ["[", "{", ""],
            "right": ["]", "}", ""],
            "space": [" ", " ", "░"],
            25: ["/", ".", "▒"],
            50: ["-", "-", "▓"],
            75: ["\\", "+", "▊"],
            100: ["=", "*", "█"],
        }

        styl = options.get("style", 0)
        if isinstance(styl, int) and 0 <= styl <= len(self.chars["left"]) - 1:
            self.style = styl
        else:
            self.style = 0

        self.show_counters = options.get("show_counters")

        self.chars["left"][self.style] = "{0}{1}".format(
            options.get("left_padding", ""),
            self.chars["left"][self.style],
        )

        self.chars["right"][self.style] = "{0}{1}".format(
            self.chars["right"][self.style],
            options.get("right_padding", ""),
        )

        if self.show_counters:
            self.width = self.total_width - (
                (len(str(self.total)) * 2)
                + len(self.chars["left"][self.style])
                + len(self.chars["right"][self.style])
                + 2  # the space and the slash
            )
        else:
            self.width = self.total_width - (
                len(self.chars["left"][self.style])
                + len(self.chars["right"][self.style])
            )

        super(ProgressBar, self).__init__()

    def setup(self):
        """Prints an empty progress bar to the screen."""

        if self.show_counters:
            counter_diff = len(str(self.total)) - len(str(self.counter))
            spaces = self.width + counter_diff
            sys.stdout.write("{left}{space}{right} {count}/{total}".format(
                left=self.chars["left"][self.style],
                space=self.chars["space"][self.style] * spaces,
                right=self.chars["right"][self.style],
                count=self.counter,
                total=self.total,
            ))
        else:
            sys.stdout.write("{left}{space}{right}".format(
                left=self.chars["left"][self.style],
                space=self.chars["space"][self.style] * self.width,
                right=self.chars["right"][self.style],
            ))
        sys.stdout.flush()

    def update(self, increment=1):
        """Updates self.counter by increment and reprints the progress bar."""

        self.counter += increment
        if self.counter > self.total:
            return
        counter_diff = len(str(self.total)) - len(str(self.counter))
        percent = (self.counter / self.total) * (self.width + counter_diff)

        sys.stdout.write("\r{left}{spaces}".format(
            left=self.chars["left"][self.style],
            spaces=self.chars[100][self.style] * int(percent),
        ))

        try:
            if not self.total > self.width * 4:
                halfchar = self.chars[rounded(percent, 50)][self.style]
            else:
                halfchar = self.chars[rounded(percent, 25)][self.style]
        except KeyError:
            halfchar = ""

        if self.show_counters:
            sys.stdout.write("{left}{space}{right} {count}/{total}".format(
                left=halfchar,
                space=self.chars["space"][self.style] * (
                    self.width
                    + counter_diff
                    - int(percent)
                    - len(halfchar)
                ),
                right=self.chars["right"][self.style],
                count=self.counter,
                total=self.total
            ))
        else:
            sys.stdout.write("{left}{space}{right}".format(
                left=halfchar,
                space=self.chars["space"][self.style] * (
                    self.width
                    - int(percent)
                    - len(halfchar)
                ),
                right=self.chars["right"][self.style],
            ))
        sys.stdout.flush()

    def clear(self):
        """Clears the progress bar from the screen and resets the cursor."""

        sys.stdout.write("\r{spaces}".format(spaces=" " * self.total_width))
        sys.stdout.flush()
        sys.stdout.write("\r")
        sys.stdout.flush()


def rounded(number, round_to):
    """Internal function for rounding numbers.

    Args:
        number: an integer
        round_to: an integer want the number to be rounded towards

    Returns:
        number, rounded to the nearest round_to
    """

    return int(round(((number - int(number)) * 100) / round_to) * round_to)


def get_term_width():
    """Tries to get the current terminal width, returns 80 if it cannot."""

    env = os.environ

    def ioctl_try(os_fd):
        """Ask the fcntl module for the window size from the os_fd."""

        try:
            return struct.unpack(
                str("hh"),
                fcntl.ioctl(os_fd, termios.TIOCGWINSZ, "1234")
            )
        except Exception:  # pokemon!
            return None

    termsize = ioctl_try(0) or ioctl_try(1) or ioctl_try(2)

    if not termsize:
        try:
            os_fd = os.open(os.ctermid(), os.O_RDONLY)
            termsize = ioctl_try(os_fd)
            os.close(os_fd)
        except Exception:
            pass

    if not termsize:
        try:
            termsize = (env["LINES"], env["COLUMNS"])
        except (IndexError, KeyError):
            termsize = (25, 80)

    return int(termsize[1])


def cmd_line_help(name):
    """Overrides argparse's help."""

    raise SystemExit((
        "{name} -- the simple python progress bar used in Bladerunner.\n"
        "Options:\n"
        "\t-c --count=<int>\t\t\tThe number of updates (default 10)\n"
        "\t-d --delay=<seconds>\t\t\tThe seconds between updates (default 1)\n"
        "\t-h --help\t\t\t\tDisplay this help message and quit\n"
        "\t-H --hide-counters\t\t\tDo not show the counters\n"
        "\t-l --left-padding=<str>\t\t\tPad the left side of the bar\n"
        "\t-r --right-padding=<str>\t\tPad the right side of the bar\n"
        "\t-s --style=<int>\t\t\tUse an alternate style (default 0)\n"
        "\t-w --width=<int>\t\t\tThe total width (default max term width)"
    ).format(
        name=name,
    ))


def cmd_line_arguments(args):
    """Sets up argparse for the command line demo."""

    parser = argparse.ArgumentParser(
        prog="progressbar",
        description="progressbar -- a simple python progress bar",
        add_help=False,
    )

    parser.add_argument(
        "--count",
        "-c",
        dest="count",
        metavar="INT",
        type=int,
        nargs=1,
        default=10,
    )

    parser.add_argument(
        "--delay",
        "-d",
        dest="delay",
        metavar="SECONDS",
        type=float,
        nargs=1,
        default=1,
    )

    parser.add_argument(
        "--style",
        "-s",
        dest="style",
        metavar="INT",
        type=int,
        nargs=1,
        default=0,
    )

    parser.add_argument(
        "--width",
        "-w",
        dest="width",
        metavar="INT",
        type=int,
        nargs=1,
        default=get_term_width(),
    )

    parser.add_argument(
        "--left-padding",
        "-l",
        dest="left_padding",
        metavar="STR",
        type=str,
        nargs=1,
        default="",
    )

    parser.add_argument(
        "--right-padding",
        "-r",
        dest="right_padding",
        metavar="STR",
        type=str,
        nargs=1,
        default="",
    )

    parser.add_argument(
        "--hide-counters",
        "-H",
        dest="show_counters",
        action="store_false",
        default=True,
    )

    parser.add_argument(
        "--help",
        "-h",
        dest="helper",
        action="store_true",
        default=False,
    )

    options = parser.parse_args(args)

    if options.helper:
        cmd_line_help(os.path.splitext(__file__)[0])

    unlistings = [
        "count",
        "delay",
        "style",
        "width",
        "left_padding",
        "right_padding",
    ]

    for unlisting in unlistings:
        if isinstance(getattr(options, unlisting), list):
            setattr(options, unlisting, getattr(options, unlisting)[0])

    return options


def cmd_line_demo(args):
    """Main command line entry point for the ProgressBar demo."""

    options = cmd_line_arguments(args)

    pbar = ProgressBar(
        options.count,
        {
            "style": options.style,
            "width": options.width,
            "show_counters": options.show_counters,
            "left_padding": options.left_padding,
            "right_padding": options.right_padding,
        },
    )

    try:
        for _ in range(options.count):
            time.sleep(options.delay)
            pbar.update()
    except KeyboardInterrupt:
        pass

    sys.stdout.write("\n")


if __name__ == "__main__":
    cmd_line_demo(sys.argv[1:])
