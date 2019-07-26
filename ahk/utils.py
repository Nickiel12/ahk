import abc
import logging
import pathlib
import os
import threading
import win32file
import win32event
import win32con

ESCAPE_SEQUENCE_MAP = {
    '\n': '`n',
    '\t': '`t',
    '\r': '`r',
    '\a': '`a',
    '\b': '`b',
    '\f': '`f',
    '\v': '`v',
    ',': '`,',
    '%': '`%',
    '`': '``',
    ';': '`;',
    ':': '`:',
    '!': '{!}',
    '^': '{^}',
    '+': '{+}',
    '{': '{{}',
    '}': '{}}',
    '#': '{#}'
}

_TRANSLATION_TABLE = str.maketrans(ESCAPE_SEQUENCE_MAP)

def make_logger(name):
    logger = logging.getLogger(name)
    handler = logging.NullHandler()
    formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def escape_sequence_replace(s):
    """
    Replace Python escape sequences with AHK equivalent escape sequences
    Additionally escapes some other characters for AHK escape sequences.
    Intended for use with AHK Send command functions.

    Note: This DOES NOT provide ANY assurances against accidental or malicious injection. Does NOT escape quotes.

    >>> escape_sequence_replace('Hello, World!')
    'Hello`, World{!}'
    """
    return s.translate(_TRANSLATION_TABLE)

class Abstract_Communicator(metaclass=abc.ABCMeta):

    last_pass_dict = {}
    this_pass_dict = {}

    def __init__(self, directory):
        if type(directory) == str:
            self.path = pathlib.Path(directory)     
        self.path = pathlib.Path(directory)
        
        # "Cover your ass in assert statements" - Unremembered Author.
        if not type(self.path) == pathlib.Path and not type(self.path) == pathlib.WindowsPath:
            raise TypeError("Expected pathlib.path or pathlib.WindowsPath but got"+ 
                f" type {type(self.path)}")

        assert self.path.exists() == True, f"The given path doesn't exist: {str(self.path)}"
        assert self.path.is_dir() == True, ("The given path must"+
            f" be a directory: {str(self.path)}")
        
        self.stop_thread = False
        self.thread = threading.Thread(target=self.event_loop)
        self.thread.start()

    def __del__(self):
        self.stop_thread = True
        logging.debug("deleting abstract_communication") 

    def get_changed_file(self)->set:
        self.path
        # Some fancy pants dictionary comprehension that uses the path to cycle through
        # all of the files in the path, make the file path the key, and set the value
        # to the last time it was modified
        self.this_pass_dict={self.path/i:os.path.getmtime(str(self.path/i))
             for i in os.listdir(str(self.path))}

        # Compares the two dicts and copies the ones that are the same to a variable
        matching = self.last_pass_dict.items() & self.this_pass_dict.items()
        # Reconstruct a dictionary out of the returned set from above
        matching = {e[0]:e[1] for e in matching}
        # Removes the matching keys, returning only that files that have changed
        different = self.this_pass_dict.keys() - matching.keys()
        # Update the last_pass dictionary to the latest files
        self.last_pass_dict = self.this_pass_dict.copy()
        # If there are any files that have changed, return them
        if different != set():
            return different
        
    @abc.abstractmethod
    def on_event(self):
        pass

    def event_loop(self):
        change_handle = win32file.FindFirstChangeNotification (
        str(self.path),
        0,
        win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
        )

        try:
            while self.stop_thread == False:
                logging.debug("Looping")
                logging.debug(self.stop_thread)
                result = win32event.WaitForSingleObject (change_handle, 500)

                #
                # If the WaitFor... returned because of a notification (as
                #  opposed to timing out or some error) then look for the
                #  changes in the directory contents.
                #
                if result == win32con.WAIT_OBJECT_0:
                    self.on_event()
                win32file.FindNextChangeNotification (change_handle)

        finally:
            win32file.FindCloseChangeNotification (change_handle)
            logging.debug("stopping notification loop")