# -*- coding: utf-8 -*-

from configparser import ConfigParser
from datetime import datetime, date
from collections import OrderedDict
from argparse import ArgumentParser
from random import random, randint, choice
import youtube_dl
from retainBot import retain
from copy import deepcopy
from glob import glob
from function import *
import subprocess
import threading
import schedule
import discord
import hashlib
import asyncio
import pickle
import signal
import books
import sched
import time
import sys
import os
import re

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class LogControl:
    def __init__(self, FileName):
        self.Name = FileName

    async def Log(self, WriteText, write_type='a'):
        with open(self.Name, write_type, encoding='utf-8',) as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Bot Log] '+WriteText+'\n')

    async def ErrorLog(self, WriteText, write_type='a'):
        with open(self.Name, write_type, encoding='utf-8') as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Error Log] '+WriteText+'\n')

    async def MusicLog(self, WriteText, write_type='a'):
        with open(self.Name, write_type, encoding='utf-8') as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Music Log] '+WriteText+'\n')

class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '{} uploaded by {}: `{}`'.format(self.player.title, self.player.uploader, self.player.url)
        return fmt

class Calendar:
    def __init__(self, Day, Name, Content, Flags):
        self.eventDay = Day
        self.eventName = Name
        self.eventContent = Content
        self.Flags = Flags

class VoiceState:
    def __init__(self, bot, channel):
        self.current = None
        self.voice = None
        self.channel = channel
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.skip_votes = set() # a set of user_ids that voted
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False
        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await NextSet(MusicMessage)
            if TitleFlag: await self.channel.send('Now playing **{}**'.format(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, server, channel):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot, channel)
            self.voice_states[server.id] = state

        return state

    async def play(self, message, *, song : str):
        state = self.get_voice_state(message.guild, message.channel)

        if state.voice is None:
            voice_channel = message.author.voice
            if voice_channel is None:
                await message.channel.send('ボイスチャネルに入ってないじゃん!')
                await log.ErrorLog('User not in voice channel')
                return False
            #state.voice = await self.bot.join_voice_channel(voice_channel.channel)

        try:
            VoiceClient = await voice_channel.channel.connect(timeout=100000000000000)
            player = await YTDLSource.from_url(song, stream=True)
            VoiceClient.play(source=player, after=state.toggle_next)
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await message.channel.send(fmt.format(type(e).__name__, e))
            #await NextSet(MusicMessage)
        else:
            player.volume = 0.3
            entry = VoiceEntry(message, player)
            await log.MusicLog('{}: {}'.format(player.title, player.url))
            await message.channel.send(entry)

    async def pause(self, message):
        state = self.get_voice_state(message.guild, message.channel)
        if state.is_playing():
            player = state.player
            player.pause()

    async def resume(self, message):
        state = self.get_voice_state(message.guild, message.channel)
        if state.is_playing():
            player = state.player
            player.resume()

    async def stop(self, message):
        server = message.guild
        state = self.get_voice_state(message.guild, message.channel)

        if state.current.player.is_playing():
            player = state.current.player
            player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    async def skip(self, message):
        state = self.get_voice_state(message.guild, message.channel)
        if not state.is_playing():
            await self.bot.send_message(message.channel, 'Not playing any music right now...')
            return
        state.skip()

def BookDataHashDict(Data):
    HashDict = {}
    for D in Data.values():
        HashDict[D.code] = D.name
    return HashDict

def Job():
    print('OK')

MusicMessage = None
player = None
InteractiveBot = None
QuesLen = 0
PlayListFiles = {}
AnsUserDic = {}
PlayListName = []
NextList = []
SpellDataG = []
SpellNameG = ''
RandomFlag = False
PauseFlag = False
PlayFlag = False
IbotFlag = False
TitleFlag = True
SpellInput = False
QuesDic = {}
QuesFlag = False
LockFlag = False
Q = ''
A = ''
version = '''PlatinaBot version: 2.3.5
Copyright (c) 2018 Glaz egy.'''
args = ArgsInit()
log = LogControl(args.log)
config = ConfigParser()
if os.path.isfile(args.config): config.read(args.config, encoding='utf-8')
else:
    log.ErrorLog('Config file not exist')
    sys.exit(1)
prefix = config['BOTDATA']['cmdprefix']
with open('help.dat', 'rb') as f:
    Data = pickle.load(f)
    CommandDict = Data['JP']
if os.path.isfile(args.playlist): PlayListFiles = LoadBinData(args.playlist)
else:
    PlayListFiles['default'] = {}
    SaveBinData(PlayListFiles, args.playlist)
NowPlayList = 'default'
PlayURLs = list(PlayListFiles[NowPlayList].keys())
UnmodifiableRole = config['ROLECONF']['unmodif_role'].split('@')
if os.path.isfile(args.book): BooksData = LoadBinData(args.book)
else:
    BooksData = {}
    SaveBinData(BooksData, args.book)
if os.path.isfile(args.schedule): CalData = LoadBinData(args.schedule)
else:
    CalData = {}
    SaveBinData(CalData, args.schedule)
if os.path.isfile(args.job): JobDic = LoadBinData(args.job)
else:
    JobDic = {}
    SaveBinData(JobDic, args.job)
maindir = os.getcwd()

BookDataHash = BookDataHashDict(BooksData)
Spell = retain.spell.Spell(args.spell)
Study = retain.study.Study(args.study)
client = discord.Client()

TrueORFalse = {'Enable': True,
                'Disable': False}

schedule.every(10).seconds.do(Job)
schedule.run_pending()

def JobControl(name, cmd):
    if not name in JobDic.keys():
        JobDic[name] = {'start': [],
                        'end': []}
    JobDic[name][cmd].append(datetime.now().strftime('%Y/%m/%d %H:%M:%S'))
    SaveBinData(JobDic, args.job)

async def ListOut(message, all=False, List=False):
    global NowPlayList
    OutFlag = False
    if all:
        await log.Log('Play list check all')
        URLs = [[]]
        keys = []
        for key, value in PlayListFiles.items():
            OutFlag = False
            URLs[-1].append('')
            keys.append(key)
            if key == NowPlayList: keys[-1] += '(Now playlist)'
            if not len(value) == 0:
                for url, title in value.items():
                    if title is None: title = youtube_dl.YoutubeDL().extract_info(url=url, download=False, process=False)['title']
                    url = 'https://www.youtube.com/watch?v='+ url if not 'http' in url else url
                    URLs[-1][-1] += '-'+title+'\n'+url+'\n'
                    if len(URLs[-1][-1]) > 750:
                        OutFlag = True
                        await EmbedOut(message.channel, 'All playlist: page{}'.format(len(URLs[-1])), keys[-1], URLs[-1][-1], 0x6b8e23)
                        URLs[-1].append('')
            if not OutFlag or URLs[-1][-1] != '':
                await EmbedOut(message.channel, 'All playlist: page{}'.format(len(URLs[-1])), keys[-1], URLs[-1][-1] if URLs[-1][-1] != '' else 'Empty', 0x6b8e23)
    elif List:
        Keys = ['']
        for key in PlayListFiles.keys():
            if key == NowPlayList: Keys[-1] += key+'(Now playlist)\n'
            else: Keys[-1] += key+'\n'
            if len(Keys[-1]) > 750:
                OutFlag = True
                await EmbedOut(message.channel, 'Playlist List: page{}'.format(len(Keys)), 'Playlists', Keys[-1], 0x6a5acd)
                Keys.append('')
        if not OutFlag or Keys[-1] != '':
            await EmbedOut(message.channel, 'Playlist List: page{}'.format(len(Keys)), 'Playlists', Keys[-1], 0x6a5acd)
    else:
        await log.Log('Call playlist is {}'.format(PlayListFiles[NowPlayList]))
        URLs = ['']
        if not len(PlayListFiles[NowPlayList]) == 0:
            for url, title in PlayListFiles[NowPlayList].items():
                if title is None: title = youtube_dl.YoutubeDL().extract_info(url=url, download=False, process=False)['title']
                url = 'https://www.youtube.com/watch?v='+ url if not 'http' in url else url
                URLs[-1] += '-'+title+'\n'+url+'\n'
                if len(URLs[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, 'Now playlist: page{}'.format(len(URLs)), NowPlayList, URLs[-1], 0x708090)
                    URLs.append('')
        if not OutFlag or URLs[-1] != '':
            await EmbedOut(message.channel, 'Now playlist: page{}'.format(len(URLs)), NowPlayList, URLs[-1] if URLs[-1] != '' else 'Empty', 0x708090)

async def NextSet(message):
    global NowPlayList
    global player
    global PlayURLs
    if not RandomFlag: NowPlay = 0
    else:
        if not len(PlayURLs) == 0: NowPlay = randint(0, len(PlayURLs)-1)
        else: NowPlay = 0
    song = PlayURLs[NowPlay]
    await player.play(message, song=('https://www.youtube.com/watch?v='+ song if not 'http' in song else song))
    await log.MusicLog('Set {}'.format(PlayURLs[NowPlay]))
    PlayURLs.remove(PlayURLs[NowPlay])
    if len(PlayURLs) == 0:
        PlayURLs = list(PlayListFiles[NowPlayList].keys())

async def ScoreOut(message):
    global AnsUserDic
    tmpvalue = 0
    try:
        for key, value in AnsUserDic.items():
            await message.channel.send('{}:{}問正解'.format(key, value))
            if value > tmpvalue:
                tmpvalue = value
                tmpuser = key
        await message.channel.send('成績優秀者は{}でした'.format(tmpuser))
    except:
        await message.channel.send('成績がありません')


@client.event
async def on_ready():
    await log.Log('Bot is Logging in!!')

@client.event
async def on_message(message):
    global MusicMessage, player, InteractiveBot
    global NowPlayList, PlayURLs, RandomFlag
    global PauseFlag, PlayFlag, IbotFlag, TitleFlag
    global SpellInput, SpellDataG, SpellNameG
    global QuesDic, QuesFlag, Q, A, QuesLen, AnsUserDic
    global LockFlag, BooksData, BookDataHash, CalData
    if SpellInput:
        SpellDataG.append(message.content)
        if SpellDataG[-1] == 'end':
            SpellInput = False
            await log.Log('Create spell {}'.format(SpellNameG))
            SpellDataG.remove('end')
            await message.channel.send('入力を終了しました')
            if IbotFlag: InteractiveBot.Spell.AddSpell(SpellDataG, SpellNameG)
            else: Spell.AddSpell(SpellDataG, SpellNameG)
            print(Spell.SpellDic)
            SpellNameG = ''
            SpellDataG = []
    elif message.content.startswith(prefix+'role'):
        AddFlag = False
        RemoveFlag = False
        AddAnotherFlag = False
        RmAnotherFlag = False
        CmdFlag = False
        CreateFlag = False
        DeleteFlag = False
        AdminFlag = False
        permissions = message.channel.permissions_for(message.author)
        cmd = message.content.split()
        if message.author.bot:
            await PermissionErrorFunc(log, client, message)
            return
        if '--list' in cmd:
            CmdFlag = True
            RoleList = message.server.roles
            AdminRoles = ''
            NomalRoles = ''
            for Role in RoleList:
                if '@everyone' == Role.name: pass
                elif Role.permissions.administrator:
                    RoleName = Role.name + '(unmodifiable)' if Role.name in UnmodifiableRole else Role.name
                    AdminRoles += RoleName+'\n'
                else:
                    RoleName = Role.name + '(unmodifiable)' if Role.name in UnmodifiableRole else Role.name
                    NomalRoles += RoleName+'\n'
            embed = discord.Embed(description='Role List', colour=0x228b22)
            embed.add_field(name='Admin', value=AdminRoles, inline=True)
            embed.add_field(name='Local', value=NomalRoles, inline=True)
            await message.channel.send(embed=embed)
            await log.Log('Confirmation role list')
            return
        if '--rm' in cmd:
            if TrueORFalse[config['ROLECONF']['del_role_me']] and not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            RemoveFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--rm')+1)
        if '--add' in cmd:
            if TrueORFalse[config['ROLECONF']['add_role_me']] and not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            AddFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--add')+1)
        if '--add-another' in cmd:
            if not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            AddAnotherFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--add-another')+2)
            UserName = CmdSpliter(cmd, cmd.index('--add-another')+1)
        if '--rm-another' in cmd:
            if not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            RmAnotherFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--rm-another')+2)
            UserName = CmdSpliter(cmd, cmd.index('--rm-another')+1)
        if '--create' in cmd:
            if not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            CreateFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--create')+1)
        if '--create-admin' in cmd:
            if TrueORFalse[config['ROLECONF']['create_role']] and not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            CreateFlag = True
            AdminFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--create-admin')+1)
        if '--delete' in cmd:
            if TrueORFalse[config['ROLECONF']['remove_role']] and not permissions.administrator:
                await PermissionErrorFunc(log, client, message)
                return
            CmdFlag = True
            DeleteFlag = True
            RoleName = CmdSpliter(cmd, cmd.index('--delete')+1)
        if (CreateFlag or DeleteFlag) and (AddFlag or RemoveFlag):
            await message.channel.send('そのコマンドは両立出来ないなぁ')
            await log.ErrorLog('A command for the server and a command for the member are entered error')
        if CreateFlag and RemoveFlag:
            await message.channel.send('作るのと削除と、どっちが良いの!？')
            await log.ErrorLog('Create and Remove command are entered error')
            return
        elif CreateFlag:
            role = discord.utils.get(message.author.server.roles, name=RoleName)
            if role == None:
                if AdminFlag:
                    if permissions.administrator:
                        per = discord.Permissions()
                        per.administrator = True
                        await client.create_role(message.server, permissions=per,name=RoleName, colour=discord.Colour(randint(0, 16777215)))
                        await log.Log('Create admin role: {}'.format(RoleName))
                    else:
                        await message.channel.send('{}には管理者権限が無いので管理者権限を含む役職を作成できません'.format(message.author.name))
                        await log.Log('Create request higher level authority')
                        return
                else:
                    await client.create_role(message.server, name=RoleName, colour=discord.Colour(randint(0, 16777215)))
                    await log.Log('Create role: {}'.format(RoleName))
                await message.channel.send('{}は誰のものになるのかな？'.format(RoleName))
            else:
                await message.channel.send('あるよ！ {} あるよッ！'.format(RoleName))
                await log.Log('Role: {} is exist in this server yet'.format(RoleName))
            return
        elif DeleteFlag:
            role = discord.utils.get(message.author.server.roles, name=RoleName)
            if role.permissions.administrator and not permissions.administrator:
                await message.channel.send('{}には管理者権限が無いので管理者権限を含む役職を削除できません'.format(message.author.name))
                await log.Log('Deleate request higher level authority')
                return
            await client.delete_role(message.server, role)
            await message.channel.send('{}はもう消されてしまいました……'.format(RoleName))
            await log.Log('Delete role: {}'.format(RoleName))
            return
        if AddFlag and RemoveFlag or AddAnotherFlag and RmAnotherFlag:
            await message.channel.send('追加するの？　消すの？　はっきりしてよ……')
            await log.ErrorLog('Add and Del command are entered')
            return
        isChange = (not RoleName in UnmodifiableRole) or (TrueORFalse[config['ROLECONF']['unmodif_admin']] and permissions.administrator)
        role = discord.utils.get(message.author.server.roles, name=RoleName)
        if role is None:
            await message.channel.send('そんな役職無いよ!')
            await log.ErrorLog('Role: {} is not exist in this server'.format(RoleName))
            return
        elif AddAnotherFlag:
            user = discord.utils.get(message.author.server.menbers, name=UserName)
            if user is None:
                await message.channel.send('そんな人はいないんだけどな')
                await log.ErrorLog('User: {} is not exist in this server'.format(UserName))
                return
            await client.add_roles(user, role)
            await message.channel.send('{}に{}の役職が追加されたよ！'.format(UserName, RoleName))
            await log.Log('Add role: {} in {}'.format(UserName, RoleName))
        elif RmAnotherFlag:
            user = discord.utils.get(message.author.server.menbers, name=UserName)
            if user is None:
                await message.channel.send('そんな人はいないんだけどな')
                await log.ErrorLog('User: {} is not exist in this server'.format(UserName))
                return
            await client.remove_roles(user, role)
            await message.channel.send('{}の{}が削除されたよ！'.format(UserName, RoleName))
            await log.Log('Remove role: {}\'s {}'.format(UserName, RoleName))
        elif AddFlag:
            if role.permissions.administrator and not permissions.administrator:
                await message.channel.send('{}には管理者権限が無いので管理者権限を含む役職には成れません'.format(message.author.name))
                await log.Log('Request higher level authority')
                return
            if isChange:
                await client.add_roles(message.author, role)
                await message.channel.send('{}に{}の役職が追加されたよ！'.format(message.author.name, RoleName))
                await log.Log('Add role: {} in {}'.format(message.author.name, RoleName))
            else:
                await message.channel.send('{}は変更不可能役職です'.format(RoleName))
                await log.ErrorLog('Add request Unmodifiable role: {}'.format(RoleName))
        elif RemoveFlag:
            if isChange:
                await client.remove_roles(message.author, role)
                await message.channel.send('{}の{}が削除されたよ！'.format(message.author.name, RoleName))
                await log.Log('Remove role: {}\'s {}'.format(message.author.name, RoleName))
            else:
                await message.channel.send('{}は変更不可能役職です'.format(RoleName))
                await log.ErrorLog('Add request Unmodifiable role: {}'.format(RoleName))
        if not CmdFlag: await OptionError(log, client, message, cmd)
    elif message.content.startswith(prefix+'music'):
        urlUseFlag = False
        cmdFlag = False
        cmd = message.content.split()
        if '--list' in cmd:
            await ListOut(message)
            return
        if '--list-all' in cmd:
            await ListOut(message, all=True)
            return
        if '--list-list' in cmd:
            await ListOut(message, List=True)
            return
        if '--list-change' in cmd:
            temp = NowPlayList
            try:
                NowPlayList = cmd[cmd.index('--list-change')+1]
            except:
                NowPlayList = 'default'
            try:
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await message.channel.send('プレイリストが{}から{}へ変更されました'.format(temp, NowPlayList))
                await log.MusicLog('Play list change {} to {}'.format(temp, NowPlayList))
            except:
                await message.channel.send('そのプレイリストは存在しません')
                await log.ErrorLog('Request not exist Play list ')
                NowPlayList = temp
            return
        if '--list-make' in cmd:
            try:
                PlayListName = cmd[cmd.index('--list-make')+1]
            except:
                await NotArgsment(log, client, message)
                return
            if PlayListName in PlayListFiles.keys():
                await message.channel.send('そのプレイリストはすでに存在します')
                await log.ErrorLog('Make request exist play list')
            else:
                PlayListFiles[PlayListName] = {}
                SaveBinData(PlayListFiles, args.playlist)
                NowPlayList = PlayListName
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await message.channel.send('新しくプレイリストが作成されました')
                await log.MusicLog('Make play list {}'.format(PlayListName))
            return
        if '--list-delete' in cmd:
            try:
                PlayListName = cmd[cmd.index('--list-delete')+1]
            except:
                await NotArgsment(log, client, message)
                return
            if PlayListName in PlayListFiles.keys() and not 'default' == PlayListName:
                del PlayListFiles[PlayListName]
                SaveBinData(PlayListFiles, args.playlist)
                await message.channel.send('{}を削除します'.format(PlayListName))
                await log.MusicLog('Remove play list {}'.format(PlayListName))
                if NowPlayList == PlayListName:
                    NowPlayList = 'default'
                    PlayURLs = list(PlayListFiles[NowPlayList].keys())
            else:
                await message.channel.send('そのプレイリストは存在しません')
                await log.ErrorLog('Delete request not exist play list')
            return
        if '--list-rename' in cmd:
            try:
                prePlayListName = cmd[cmd.index('--list-rename')+1]
                sufPlayListName = cmd[cmd.index('--list-rename')+2]
            except:
                await NotArgsment(log, client, message)
                return
            if sufPlayListName in PlayListFiles.keys() and not 'default' == prePlayListName:
                await message.channel.send('そのプレイリストはすでに存在します')
                await log.ErrorLog('Make request exist play list')
            elif prePlayListName in PlayListFiles.keys() and not 'default' == prePlayListName:
                PlayListFiles[sufPlayListName] = deepcopy(PlayListFiles[prePlayListName])
                if NowPlayList == prePlayListName: NowPlayList = sufPlayListName
                del PlayListFiles[prePlayListName]
                SaveBinData(PlayListFiles, args.playlist)
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await message.channel.send('{}の名前を{}に変更します'.format(prePlayListName, sufPlayListName))
                await log.MusicLog('Rename play list {}'.format(prePlayListName))
            elif 'default' == prePlayListName:
                await message.channel.send('defaultを変更することは出来ません')
                await log.ErrorLog('Cannot renaem default')
            else:
                await message.channel.send('そのプレイリストは存在しません')
                await log.ErrorLog('Rename request not exist play list')
            return
        if '--list-clear' in cmd:
            try:
                ClearPlaylist = cmd[cmd.index('--list-clear')+1]
            except:
                await NotArgsment(log, client, message)
            if ClearPlaylist in PlayListFiles.keys():
                PlayListFiles[ClearPlaylist] = {}
                await message.channel.send('{}をクリアしました'.format(ClearPlaylist))
                await log.MusicLog('Cleared {}'.format(ClearPlaylist))
                SaveBinData(PlayListFiles, args.playlist)
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
            else:
                await message.channel.send('そのプレイリストは存在しません')
                await log.ErrorLog('Clear request not exist play list')
            return
        if '--list-clear-all' in cmd:
            for key in PlayListFiles.keys():
                PlayListFiles[key] = {}
                await message.channel.send('{}をクリアしました'.format(key))
                await log.MusicLog('Cleared {}'.format(key))
            SaveBinData(PlayListFiles, args.playlist)
            return
        if len(cmd) >= 2:
            for cmdpar in cmd:
                if '$' in cmdpar:
                    urlUseFlag = True
                    url = cmdpar.replace('$', '')
        MusicMessage = message
        if '--play' in cmd:
            RandomFlag = False
            TitleFlag = True
            if '-r' in cmd: RandomFlag = True
            if PauseFlag: await player.resume(message)
            else:
                if len(PlayURLs) >= 1: music = randint(0, len(PlayURLs)-1)
                elif len(PlayURLs) == 0: music = 0
                else:
                    await message.channel.send('プレイリストに曲が入ってないよ！')
                    await log.ErrorLog('Not music in playlist')
                    return
                try:
                    player = MusicPlayer(client)
                    song = PlayURLs[music if RandomFlag else 0] if not urlUseFlag else url
                    await player.play(message, song=('https://www.youtube.com/watch?v='+ song if not 'http' in song else song))
                    if not urlUseFlag: PlayURLs.remove(PlayURLs[music if RandomFlag else 0])
                    if len(PlayURLs) == 0: PlayURLs = list(PlayListFiles[NowPlayList].keys())
                    PlayFlag = True
                    #await client.change_presence(game=discord.Game(name='MusicPlayer'))
                except discord.errors.InvalidArgument:
                    pass
                except discord.ClientException:
                    await log.ErrorLog('Already Music playing')
                    await message.channel.send('Already Music playing')
            cmdFlag = True
        if '-r' in cmd:
            RandomFlag = True
            cmdFlag = True
        if '-n' in cmd:
            RandomFlag = False
            cmdFlag = True
        if '--no-out' in cmd:
            TitleFlag = False
            cmdFlag = True
        if '--next' in cmd:
            await log.MusicLog('Music skip')
            await player.skip(message)
            cmdFlag = True
        if '--stop' in cmd:
            if player is None:
                await message.channel.send('今、プレイヤーは再生してないよ！')
                await log.ErrorLog('Not play music')
                return
            await client.change_presence(game=(None if not IbotFlag else discord.Game(name='IBOT')))
            await log.MusicLog('Music stop')
            await player.stop(message)
            PlayFlag = False
            player = None
            PlayURLs = list(PlayListFiles[NowPlayList].keys())
            cmdFlag = True
        if '--pause' in cmd:
            await log.MusicLog('Music pause')
            await player.pause(message)
            PauseFlag = True
            cmdFlag = True
        if not cmdFlag: await OptionError(log, client, message, cmd)
    elif message.content.startswith(prefix+'addmusic'):
        NotFound = True
        links = message.content.split()[1:]
        if links[0] in PlayListFiles.keys():
            ListName = links[0]
            links.remove(links[0])
        else: ListName = NowPlayList
        ineed = ['']
        for link in links:
            linkraw = deepcopy(link)
            link = link.replace('https://www.youtube.com/watch?v=', '')
            link = link.replace('https://youtu.be/', '')
            if not link in PlayListFiles[ListName]:
                try:
                    PlayListFiles[ListName][link] = youtube_dl.YoutubeDL().extract_info(url=link, download=False, process=False)['title']
                    PlayURLs.append(link)
                    await log.MusicLog('Add {}'.format(link))
                    ineed[-1] += '-{}\n'.format(PlayListFiles[ListName][link])
                    NotFound = False
                    if len(ineed[-1]) > 750:
                        await EmbedOut(message.channel, 'Wish List page {}'.format(len(ineed)), 'Music', ineed[-1], 0x303030)
                        ineed.append('')
                        NotFound = True
                except:
                    await message.channel.send('{} なんて無いよ'.format(linkraw))
                    await log.ErrorLog('{} is Not Found'.format(linkraw))
            else:
                await log.MusicLog('Music Overlap {}'.format(link))
                await message.channel.send('その曲もう入ってない？')
        SaveBinData(PlayListFiles, args.playlist)
        if not ineed[-1] == '' and not NotFound: await EmbedOut(message.channel, 'Wish List page {}'.format(len(ineed)), 'Music', ineed[-1], 0x303030)
    elif message.content.startswith(prefix+'delmusic'):
        NotFound = True
        links = message.content.split()[1:]
        if links[0] in PlayListFiles.keys():
            ListName = links[0]
            links.remove(links[0])
        else: ListName = NowPlayList
        notneed = ['']
        for link in links:
            link = link.replace('https://www.youtube.com/watch?v=', '')
            link = link.replace('youtube.com/watch?v=', '')
            link = link.replace('https://youtu.be/', '')
            try:
                print(link)
                Title = PlayListFiles[ListName][link]
                del PlayListFiles[ListName][link]
                try:
                    PlayURLs.remove(link)
                except:
                    pass
                NotFound = False
                notneed[-1] += '-{}\n'.format(Title)
                await log.MusicLog('Del {}'.format(link))
                if len(notneed[-1]) > 750:
                    await EmbedOut(message.channel, 'Delete List page {}'.format(len(notneed)), 'Music', notneed[-1], 0x749812)
                    notneed.append('')
                    NotFound = True
            except:
                await log.ErrorLog('{} not exist list'.format(link))
                await message.channel.send('そんな曲入ってたかな？')
        SaveBinData(PlayListFiles, args.playlist)
        if not notneed[-1] == '' and not NotFound: await EmbedOut(message.channel, 'Delete List page {}'.format(len(notneed)), 'Music', notneed[-1], 0x749812)
        if len(PlayURLs) == 0: PlayURLs = list(PlayListFiles[NowPlayList].keys())
    elif message.content.startswith(prefix+'help'):
        cmds = message.content.split()
        if len(cmds) > 1:
            for cmd in cmds:
                if cmd == 'role' or cmd == 'music' or cmd == 'spell' or cmd == 'study' or cmd == 'book':
                    cmdline = ''
                    for key, value in CommandDict[cmd].items():
                        cmdline += key + ': ' + value + '\n'
                    embed = discord.Embed(description=cmd+' Commmand List', colour=0x008b8b)
                    embed.add_field(name='Commands', value=cmdline, inline=True)
                    await message.channel.send(embed=embed)
        else:
            cmdline = ''
            for key, value in CommandDict['help'].items():
                cmdline += key + ': ' + value + '\n'
            embed = discord.Embed(description='Commmand List', colour=0x4169e1)
            embed.add_field(name='Commands', value=cmdline, inline=True)
            await message.channel.send(embed=embed)
    elif message.content.startswith(prefix+'spell'):
        cmd = message.content.split()
        if '--list' in cmd:
            SpellName = ['']
            OutFlag = False
            for spell in Spell.SpellDic.keys():
                if not spell == 'SpellList': SpellName[-1] += spell + '\n'
                if len(SpellName[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, disc='Spell List', playname='Spells', url=SpellName[-1], color=0x000000)
                    SpellName.append('')
            if not OutFlag or SpellName[-1]:
                await EmbedOut(message.channel, disc='Spell List', playname='Spells', url=SpellName[-1], color=0x000000)
            return
        elif '--spell' in cmd:
            SpellName = CmdSpliter(cmd, cmd.index('--spell')+1)
            Spelltext = ['']
            OutFlag = False
            for spell in Spell.SpellDic[SpellName]:
                if not spell == 'SpellList': Spelltext[-1] += spell + '\n'
                if len(Spelltext[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, disc='Spell', playname='Spells text', url=Spelltext[-1], color=0x000000)
                    Spelltext.append('')
            if not OutFlag or Spelltext[-1]:
                await EmbedOut(message.channel, disc='Spell', playname='Spell text', url=Spelltext[-1], color=0x000000)
            return
        elif '--del' in cmd:
            SpellName = CmdSpliter(cmd, cmd.index('--del')+1)
            if IbotFlag: InteractiveBot.Spell.DelSpell(SpellName)
            else: Spell.DelSpell(SpellName)
        elif '--add' in cmd:
            SpellName, index = CmdSpliter(cmd, cmd.index('--add')+1, sufIndex=True)
            SpellData = cmd[index+1:]
            if IbotFlag: InteractiveBot.Spell.AddSpell(SpellData, SpellName)
            else: Spell.AddSpell(SpellData, SpellName)
            await log.Log('Create spell {}'.format(SpellName))
            print(Spell.SpellDic)
        elif '--add-line' in cmd:
            SpellNameG = CmdSpliter(cmd, cmd.index('--add-line')+1)
            SpellInput = True
    elif message.content.startswith(prefix+'study'):
        cmd = message.content.split()
        CmdFlag = False
        if '--list-subject' in cmd:
            CmdFlag = True
            Subject = ['']
            OutFlag = False
            for sub in Study.StudyDic.keys():
                Subject[-1] += sub + '\n'
                if len(Subject[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, disc='Subject List', playname='Subject', url=Subject[-1], color=0x000000)
                    Subject.append('')
            if not OutFlag or Subject[-1]:
                await EmbedOut(message.channel, disc='Subject List', playname='Subject', url=Subject[-1], color=0x000000)
            return
        elif '--list-unit' in cmd:
            CmdFlag = True
            Subject = CmdSpliter(cmd, cmd.index('--list-unit')+1)
            Unit = ['']
            OutFlag = False
            for unit in Study.StudyDic[Subject].keys():
                Unit[-1] += unit + '\n'
                if len(Unit[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, disc='Unit List', playname='Unit', url=Unit[-1], color=0x000000)
                    Unit.append('')
            if not OutFlag or Unit[-1]:
                await EmbedOut(message.channel, disc='Unit List', playname='Unit', url=Unit[-1], color=0x000000)
            return
        elif '--list-ques' in cmd:
            CmdFlag = True
            Subject, index = CmdSpliter(cmd, cmd.index('--list-ques')+1, sufIndex=True)
            Unit = CmdSpliter(cmd, index+1)
            QuesAns = ['']
            OutFlag = False
            for ques, ans in Study.StudyDic[Subject][Unit].items():
                QuesAns[-1] += ques + '  -  Ans:' + ans + '\n'
                if len(QuesAns[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, disc='Question List', playname='Question & Answer', url=QuesAns[-1], color=0x000000)
                    QuesAns.append('')
            if not OutFlag or QuesAns[-1]:
                await EmbedOut(message.channel, disc='Question List', playname='Question & Answer', url=QuesAns[-1], color=0x000000)
            return
        elif '--del' in cmd:
            CmdFlag = True
            DelKey = cmd[cmd.index('--del')+1]
            if DelKey == 'Ques':
                DelObj = [cmd[cmd.index('--del')+2]]
                DelObj.append(cmd[cmd.index('--del')+3])
                DelObj.append(cmd[cmd.index('--del')+4])
            else:DelObj = cmd[cmd.index('--del')+2]
            backunm = Study.DelStudy(DelObj, DelKey)
            if backunm == 0:
                await message.channel.send('問題を削除します')
                await log.Log("Delete {}: {}".format(DelKey, DelObj))
            elif backunm == -1:
                await log.ErrorLog("Question:{} is wrong".format(DelObj))
                await message.channel.send('Question名: {} は見つかりませんでした'.format(DelObj))
            elif backunm == -2:
                await log.ErrorLog("Unit:{} is wrong".format(DelObj))
                await message.channel.send('Unit名: {} は見つかりませんでした'.format(DelObj))
            elif backunm == -3:
                await log.ErrorLog("Subject:{} is wrong".format(DelObj))
                await message.channel.send('Subject名: {} は見つかりませんでした'.format(DelObj))
            elif backunm == -4:
                await log.ErrorLog("DelKey:{} is wrong".format(DelKey))
                await message.channel.send('DelKeyの指定が間違っています')
        elif '--add' in cmd:
            CmdFlag = True
            Subject, index = CmdSpliter(cmd, cmd.index('--add')+1, sufIndex=True)
            try:
                Unit, index = CmdSpliter(cmd, index+1, sufIndex=True)
                Ques, index = CmdSpliter(cmd, index+1, sufIndex=True)
                Ans, index = CmdSpliter(cmd, index+1, sufIndex=True)
                Study.AddStudy(Subject, Unit, [Ques,], [Ans,])
                await log.Log("Unit:{} Ques:{} - ans:{}".format(Unit, Ques, Ans))
                await message.channel.send('問題を追加します')
            except:
                await log.ErrorLog("Input ques and ans is wrong type")
                await message.channel.send('入力の形式が違います')
        elif '--add-m' in cmd:
            CmdFlag = True
            Qs = []
            As = []
            await message.channel.send('問題を複数追加します')
            Subject, index = CmdSpliter(cmd, cmd.index('--add-m')+1, sufIndex=True)
            Unit, index = CmdSpliter(cmd, index+1, sufIndex=True)
            for QuesAns in cmd[index+1:]:
                try:
                    Ques, Ans = QuesAns.split(';')
                    Qs.append(Ques)
                    As.append(Ans)
                    await log.Log("Unit:{} Ques:{} - ans:{}".format(Unit, Ques, Ans))
                except:
                    await log.ErrorLog("[{}] is wrong type".format(QuesAns))
                    await message.channel.send('入力の形式が違います')
            Study.AddStudy(Subject, Unit, Qs, As)
        elif '--score' in cmd:
            CmdFlag = True
            await message.channel.send('前回の成績')
            await ScoreOut(message)
        elif '--start' in cmd:
            CmdFlag = True
            Subject, index = CmdSpliter(cmd, cmd.index('--start')+1, sufIndex=True)
            if index+1 >= len(cmd):
                UnitList = Study.StudyDic[Subject].keys()
                QuesDic = {}
                for unit in UnitList:
                    QuesDic.update(deepcopy(Study.StudyDic[Subject][unit]))
            else:
                Unit, index = CmdSpliter(cmd, index+1, sufIndex=True)
                if not cmd[index+1:] == []:
                    QuesDic = deepcopy(Study.StudyDic[Subject][Unit])
                    for unit in cmd[index+1:]:
                        QuesDic.update(deepcopy(Study.StudyDic[Subject][unit]))
                else: QuesDic = deepcopy(Study.StudyDic[Subject][Unit])
            QuesFlag = True
            QuesLen = len(QuesDic)
            Q = choice(list(QuesDic.keys()))
            A = QuesDic.pop(Q)
            AnsUserDic = {}
            await message.channel.send('それではスタート')
            await message.channel.send('問題です\n残り{}/全問{}\n{} '.format(len(QuesDic)+1, QuesLen, Q))
        if not CmdFlag: await OptionError(log, client, message, cmd)
    elif message.content.startswith(prefix+'book'):
        cmd = message.content.split()[1:]
        if cmd[0] == '--add':
            if cmd[1] in BooksData.keys():
                await message.channel.send('すでに書籍が登録してあります。別の名前で登録してください')
            else:
                BooksData[cmd[1]] = books.BookData(cmd[1], cmd[2], cmd[3])
                SaveBinData(BooksData, args.book)
                await message.channel.send('書籍の登録が完了しました')
                BookDataHash[BooksData[cmd[1]].code] = cmd[1]
        elif cmd[0] == '--del':
            if not cmd[1] in BooksData.keys():
                await message.channel.send('同名の書籍が存在しません。再度確認をしてください')
            else:
                del BookDataHash[BooksData[cmd[1]].code]
                del BooksData[cmd[1]]
                SaveBinData(BooksData, args.book)
                await message.channel.send('書籍の削除が完了しました')
        elif '--borrow' in cmd[0]:
            if '-hash' in cmd[0]: name = BookDataHash[cmd[1]]
            elif cmd[0] == '--borrow': name = cmd[1]
            else: await message.channel.send('オプションの選択が間違っています')
            if not name in BooksData.keys():
                await message.channel.send('同名の書籍が存在しません。再度確認をしてください')
                return
            status = BooksData[name].LendingBook(message.author.name, message.author.id)
            if status == 0:
                await message.channel.send('正常に貸出処理が完了しました')
            elif status == -1:
                await message.channel.send('只今貸出中です。返却処理が終わってから再度貸出処理を行ってください')
            SaveBinData(BooksData, args.book)
        elif cmd[0] == '--return':
            if '-hash' in cmd[0]: name = BookDataHash[cmd[1]]
            elif cmd[0] == '--return': name = cmd[1]
            else: await message.channel.send('オプションの選択が間違っています')
            if not name in BooksData.keys():
                await message.channel.send('同名の書籍が存在しません。再度確認をしてください')
                return
            status = BooksData[name].ReturnBook(message.author.name, message.author.id)
            if status == 0:
                await message.channel.send('正常に返却処理が完了しました')
            elif status == -1:
                await message.channel.send('貸出処理が行われていません。貸出処理を行ってから返却処理を行ってください')
            elif status == -10:
                await message.channel.send('貸出ユーザとIDが違います。返却処理は本人が行ってください')
            SaveBinData(BooksData, args.book)
        elif cmd[0] == '--list':
            listbook = ''
            outFlag = False
            for key in BooksData.keys():
                datalist = BooksData[key].GetBookInfo(data = (None if (len(cmd) == 1) else cmd[1]))
                if datalist == 0:
                    await message.channel.send('表示項目の指定が間違っています')
                    return
                if len(datalist) == 2:
                    listbook += datalist[0] + ': ' + ('貸出中' if datalist[1] else '貸出可')+'\n'
                elif len(datalist) == 3:
                    listbook += datalist[0] + ': ' + ('N/A' if datalist[1] is None else datalist[1]) + ': '+ ('貸出中' if datalist[2] else '貸出可')+'\n'
                if len(listbook) > 750:
                    if len(cmd) == 1:
                        await EmbedOut(message.channel, disc='Books List', playname='Book name', url=listbook, color=0x5042f4)
                    listbook = ''
                    outFlag = True
            if not outFlag:
                await EmbedOut(message.channel, disc='Books List', playname='Book name', url=listbook, color=0x5042f4)
    elif message.content.startswith(prefix+'exit'):
        AdminCheck = (message.author.id == config['ADMINDATA']['botowner'] if config['ADMINDATA']['botowner'] != 'None' else False)
        if TrueORFalse[config['ADMINDATA']['passuse']] and not AdminCheck:
            HashWord = hashlib.sha256(message.content.split()[1].encode('utf-8')).hexdigest()
            AdminCheck = (HashWord == config['ADMINDATA']['passhash'] if config['ADMINDATA']['passhash'] != 'None' else False)
        if AdminCheck:
            await log.Log('Bot exit')
            await client.close()
            await sys.exit(0)
        else:
            PermissionErrorFunc(log, client, message)
    elif QuesFlag and (message.content.startswith(prefix+'ans') or (message.channel.id == config['BOTDATA']['studych'] and not message.author.bot)):
        cmd = message.content.split()
        if not message.author.name in AnsUserDic:
            AnsUserDic[message.author.name] = 0
        if '--exit' in cmd:
            await message.channel.send('終わります')
            QuesFlag = False
            QuesDic = []
            return
        elif '--next' in cmd:
            await message.channel.send('正解は{}でしたー'.format(A))
        else:
            if message.content.startswith(prefix+'ans'): ans = CmdSpliter(cmd, 1)
            else: ans = message.content
            await log.Log('Input {}'.format(ans))
            if not LockFlag:
                if re.match(A, ans):
                    LockFlag = True
                    await message.channel.send('正解！')
                    AnsUserDic[message.author.name] += 1
                else:
                    await message.channel.send('は、こんなんも分からんのか\nもう一回やって')
                    return 
            else: return
        try:
            Q = choice(list(QuesDic.keys()))
            A = QuesDic.pop(Q)
            await message.channel.send('はい、次')
            await message.channel.send('張り切ってどうぞ')
            await message.channel.send('残り{}/全問{}\n{}'.format(len(QuesDic)+1, QuesLen, Q))
        except:
            await message.channel.send('しゅーりょー')
            await message.channel.send('成績')
            await ScoreOut(message)
            QuesFlag = False
            QuesDic = []
        LockFlag = False
    elif message.content.startswith(prefix+'version'):
        await log.Log(version)
        await message.channel.send(version)
        if IbotFlag:
            await log.Log(InteractiveBot.__version__)
            await message.channel.send(InteractiveBot.__version__)
    elif message.content.startswith(prefix+'debug'):
        await message.channel.send(client.email)
    elif message.content.startswith(prefix+'say'):
        cmds = message.content.split()[1:]
        out = ''
        for cmd in cmds: out += cmd+' '
        await message.channel.send(out)
        await log.Log('Bot say {}'.format(out))
    elif message.content.startswith(prefix+'cal'):
        cmd = message.content.split()
        if '--add' in cmd:
            EventDay = cmd[cmd.index('--add')+1]
            EventName = cmd[cmd.index('--add')+2]
            EventContent = cmd[cmd.index('--add')+3]
            CalData[EventName] = Calendar(EventDay, EventName, EventContent)
            print(CalData[EventName])
            SaveBinData(CalData, args.schedule)
            await message.channel.send('イベントを追加しました\n{}\n{}\n{}'.format(EventDay, EventName, EventContent))
        if '--print' in cmd:
            await message.channel.send(str(CalData))
    elif message.content.startswith(prefix+'ibot'):
        cmd = message.content.split()
        if TrueORFalse[config['BOTMODE']['ibot_mode']]:
            if '--start' in cmd:
                if not IbotFlag:
                    IbotFlag = True
                    InteractiveBot = retain.retain.Bot(Spell)
                    await message.channel.send('インタラクティブボットモードをONにしました')
                    await log.Log('Interactive bot mode is ON')
                    await client.change_presence(game=discord.Game(name='IBOT'))
                else:
                    await message.channel.send('インタラクティブモードはすでにONになっています')
                    await log.ErrorLog('Already interractive bot mode is ON')
            elif '--stop' in cmd:
                if IbotFlag:
                    IbotFlag = False
                    InteractiveBot = None
                    await message.channel.send('インタラクティブボットモードをOFFにしました')
                    await log.Log('Interactive bot mode is OFF')
                    await client.change_presence(game=(None if not PlayFlag else discord.Game(name='MusicPlayer')))
                else:
                    await message.channel.send('インタラクティブモードはすでにOFFになっています')
                    await log.ErrorLog('Already interractive bot mode is OFF')
            else: await OptionError(log, client, message, cmd)
        else:
            await message.channel.send('現在このコマンドは無効化されています')
            await log.ErrorLog('Ibot mode is Disable')
    elif message.content.startswith(prefix+'job'):
        cmd = message.content.split()
        if cmd[1] == '--start':
            JobControl(config['USER'][str(message.author.id)], 'start')
        elif cmd[1] == '--end':
            JobControl(config['USER'][str(message.author.id)], 'end')
        elif cmd[1] == '--print':
            if config['OUTFILE']['cmd'] == 'sh':
                subprocess.call(['sh', 'jobout.sh'])
            elif config['OUTFILE']['cmd'] == 'bat':
                subprocess.call('jobout.bat')
    elif message.content.startswith(prefix+'pwd'):
        await message.channel.send(os.getcwd())
    elif message.content.startswith(prefix+'ls'):
        cmds = message.content.split()
        AllFlag = False
        LineFlag = False
        nowdir = './'
        for cmd in cmds[1:]:
            if not '-' in cmd: nowdir = cmd
        if '-a' in cmds: AllFlag = True
        if '-l' in cmds: LineFlag = True
        listfile = os.listdir(nowdir)
        listfile.sort()
        files = ['']
        for fil in listfile:
            if not fil[0] == '.' or AllFlag:
                if LineFlag: files[-1]  += '{}\n'.format(fil) if os.path.isfile(nowdir+'/'+fil) else '**{}**\n'.format(fil)
                else:files[-1] += '{}\t'.format(fil) if os.path.isfile(nowdir+'/'+fil) else '**{}**\t'.format(fil)
                if len(files[-1]) > 750:
                    files[-1] += '\n'
                    await message.channel.send(files[-1])
                    files.append('')
        await message.channel.send(files[-1])
    elif message.content.startswith(prefix+'cd'):
        cmds = message.content.split()
        if len(cmds) == 1:
                os.chdir(maindir)
        for cmd in cmds[1:]:
                if not '-' in cmd: os.chdir(cmd)
    elif message.content.startswith(prefix+'cat') and message.author.id == config['ADMINDATA']['botowner']:
        cmds = message.content.split()
        outFlag = False
        if not len(cmds) == 1:
            with open(cmds[1], 'r', encoding='utf-8') as f:
                files = f.readlines()
            lines = ['']
            for line in files:
                outFlag = True
                if len(line) == 1: lines[-1] += line
                else: lines[-1] += '`{}`\n'.format(line.replace('\n', ''))
                if len(lines[-1]) > 750:
                    await message.channel.send(lines[-1])
                    lines.append('')
            if not outFlag or not lines[-1] == '': await message.channel.send(lines[-1])
    elif message.content.startswith(prefix):
        await message.channel.send('該当するコマンドがありません')
        await log.ErrorLog('Command is notfound')
    elif IbotFlag and not message.author.bot:
        comment = InteractiveBot.Response(message.content)
        if not comment is None:
            await message.channel.send(comment)
            await log.Log('ibot return {}'.format(comment))

@client.event
async def on_member_join(member):
    if TrueORFalse[config['JOINCONF']['joinevent']]:
        jointexts = config['JOINCONF']['jointext'].replace('\n', '')
        jointexts = jointexts.split('@/')
        text = jointexts[randint(0, len(jointexts)-1)].strip()
        channel = client.get_channel(config['BOTDATA']['mainch'])
        readme = client.get_channel(config['BOTDATA']['readmech'])
        if channel is None or readme is None: return
        text = text.replace('[MenberName]', member.name)
        text = text.replace('[ChannelName]', readme.name)
        await client.send_message(channel, text)
    await log.Log('Join {}'.format(member.name))
    print('Join {}'.format(member.name))

client.run(config['BOTDATA']['token'])
