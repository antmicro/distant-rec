#!/usr/bin/env python

class ScriptMangler:
    def __init__(self, path):
        self.file_handle = open(path, "r+")
        self.file_string = self.file_handle.read()
        self.file_list = self.file_string.split("\n")

    def abs_to_rel(self):

        arguments = self.file_list[13].split(" ")

        for i in range(4,7):
            arguments[i] = self.__atr_text(arguments[i])

        arguments_join = " ".join(arguments)

        self.file_list[13] = arguments_join

    def flush(self):
        self.file_string = "\n".join(self.file_list)
        self.file_handle.seek(0)
        self.file_handle.write(self.file_string)
        self.file_handle.close()

    def __atr_text(self, text):
        # Take a string with absolute path and substitute it with "./"
        start_index = text.find("vtr_flow")
        return "./{}".format(text[start_index:])
