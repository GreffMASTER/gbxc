import os
from typing import io


class Counter:
    """
    A general purpose counter class. It can increment or decrement
    the counter value by a set amount or by default amount set when
    initializing the object.
    """
    __value = 0
    __default_incr_value = 1
    __default_decr_value = 1

    def __init__(self, init_value: int = 0, default_incr_value: int = 1, default_decr_value: int = 1):
        self.__value = init_value
        self.__default_incr_value = default_incr_value
        self.__default_decr_value = default_decr_value

    def __call__(self, *args, **kwargs) -> int:
        return int(self.__value)

    def __getitem__(self, item):
        pass

    def __str__(self):
        return str(self.__value)

    def __int__(self):
        return self.__value

    def __add__(self, other):
        if isinstance(other, int):
            return Counter(other + int(self.__value))

    def __iadd__(self, other):
        if isinstance(other, int):
            self.__value += other

    def increment(self, incr_value: int = None):
        """
        Increments the counter by a set value or by a default value.

        :param incr_value:
        :return:
        """
        if incr_value:
            self.__value += incr_value
        else:
            self.__value += self.__default_incr_value

    def decrement(self, decr_value: int = None):
        """
        Decrements the counter by a set value or by a default value.

        :param decr_value:
        :return:
        """
        if decr_value:
            self.__value -= decr_value
        else:
            self.__value -= self.__default_decr_value

    def set_value(self, value: int):
        """
        Sets the counter value.

        :param value:
        :return:
        """
        self.__value = value

    def get_value(self) -> int:
        """
        Gets the counter value.

        :return:
        """
        return self.__value

    def set_default_incr_value(self, incr_value: int):
        """
        Sets the default increment value.

        :param incr_value:
        :return:
        """
        self.__default_incr_value = incr_value

    def set_default_decr_value(self, decr_value: int):
        """
        Sets the default decrement value.

        :param decr_value:
        :return:
        """
        self.__default_decr_value = decr_value
