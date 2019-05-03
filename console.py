# -*- coding: utf-8 -*-

import sys
import os

defa = 'D:/Users/amida/Documents/DiscordBot'

if __name__=='__main__':
    while True:
        AllFlag = False
        inputstr = input()
        sp = inputstr.split()
        s = './'
        for s in sp[1:]:
            if not '-' in s: path = s
        if '-a' in sp: AllFlag = True
        if sp[0] == ';ls':
            lis = os.listdir(s)
            for fil in lis:
                if fil[0] != '.' or AllFlag:
                    print(fil, end=' ')
            print('')
        if sp[0] == ';pwd':
            print(os.getcwd())
        if sp[0] == ';cd':
            if len(sp) == 1:
                os.chdir(defa)
            for s in sp[1:]:
                if not '-' in s: os.chdir(s)
        if sp[0] == ';exit':
            exit(0)