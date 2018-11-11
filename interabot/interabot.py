# -*- coding: utf-8 -*-

import datetime
import sys
import os

GreetingDict = {'mooning': [4, 5, 6, 7, 8, 9],
                'noon': [10, 11, 12, 13, 14, 15, 16, 17, 18],
                'night': [19, 20, 21, 22, 23, 24, 0, 1, 2, 3]}
TimeZone = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

class Bot:
    def __init__(self):
        self.__version__ = 'interabot version: 0.0.2\nCopyright (c) 2018 Glaz egy.'

    def Response(self, text):
        if '今何時' in text:
            now = datetime.datetime.now(TimeZone)
            comment = '{}:{:02}だよ！'.format(now.hour, now.minute)
        elif 'おはよう' in text:
            now = datetime.datetime.now(TimeZone)
            if not now.hour in GreetingDict['mooning']:
                comment = 'おはようじゃないよ！　今、{}時だよ'.format(now.hour)
            else:
                comment = 'おはよう！'
        elif 'こんばん' in text:
            now = datetime.datetime.now(TimeZone)
            if not now.hour in GreetingDict['night']:
                comment = 'こんばんわじゃないよ！　今、{}時だよ'.format(now.hour)
            else:
                comment = 'こんばんわ！'
        elif 'こんにち' in text:
            comment = 'こんにちは！'
        return comment