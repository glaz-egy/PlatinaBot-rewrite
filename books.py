# -*- coding: utf-8 -*-

from datetime import datetime, date
from hashlib import md5
import pickle

class BookData:
    def __init__(self, Name, Author, Release=None):
        self.__name = Name
        self.__author = Author
        self.__release = Release
        self.__registerdate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.__LendingUserName = None
        self.__LendingUserId = 0
        codestr = self.__name + self.__registerdate
        self.__bookcode = str(md5(codestr.encode()).hexdigest())
        self.UpdateDate = self.__registerdate
        self.LendingFlag = False
    
    def LendingBook(self, UserName, UserId):
        if not self.LendingFlag:
            self.LendingFlag = True
            self.__LendingUserName = UserName
            self.__LendingUserId = UserId
            self.UpdateDate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return 0
        else:
            return -1
    
    def ReturnBook(self, UserName, UserId):
        if self.LendingFlag and UserId == self.__LendingUserId:
            self.LendingFlag = False
            self.__LendingUserName = None
            self.__LendingUserId = 0
            self.UpdateDate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return 0
        elif not self.LendingFlag:
            return -1
        elif UserId != self.__LendingUserId:
            return -10
    
    def RetouchBookInfo(self, key, value):
        if key.lower() == 'name':
            self.__name = value
        elif key.lower() == 'author':
            self.__author = value
        if key.lower() == 'release':
            self.__release = value
        self.UpdateDate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def GetBookInfo(self, data=None):
        if data is None:
            return [self.__name, self.LendingFlag]
        elif data == 'author':
            return [self.__name, self.__author, self.LendingFlag]
        elif data == 'release':
            return [self.__name, self.__release, self.LendingFlag]
        elif data == 'regist':
            return [self.__name, self.__registerdate, self.LendingFlag]
        elif data == 'update':
            return [self.__name, self.UpdateDate, self.LendingFlag]
        elif data == 'lenduser':
            return [self.__name, self.__LendingUserName, self.LendingFlag]
        elif data == 'code':
            return [self.__name, self.__bookcode, self.LendingFlag]

def SaveBooksData(FileName, Data):
    with open(FileName, 'wb') as f:
        pickle.dump(Data, f)

def LoadBooksData(FileName):
    with open(FileName, 'rb') as f:
        Data = pickle.load(f)
    return Data