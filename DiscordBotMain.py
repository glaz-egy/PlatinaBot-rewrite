# -*- coding: utf-8 -*-

from configparser import ConfigParser
from datetime import datetime, date
from collections import OrderedDict
from random import random, randint
from youtube_dl import YoutubeDL
from copy import deepcopy
from glob import glob
import threading
import interabot
import discord
import hashlib
import asyncio
import pickle
import signal
import sched
import time
import sys
import os

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
    def __init__(self, bot):
        self.CalData = {}
        self.bot = bot

    async def CalTask(self):
        print('test')
        self.CalData['2018-11-10'] = ['test', 'korehatesoto', self.bot.get_channel('508137939491094557'), False]
        _ = str(date.today())
        embed = discord.Embed(description='2018-11-10', colour=0x000000)
        embed.add_field(name=self.CalData['2018-11-10'][0], value=self.CalData['2018-11-10'][1], inline=True)
        await self.bot.send_message(self.bot.get_channel('508137939491094557'), embed=embed)

    def CalRegister(self, eventDay, eventName, eventContent, outChannel, Loop=False):
        self.CalData[eventDay] = [eventName, eventContent, outChannel, Loop]

class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
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
            if TitleFlag: await self.bot.send_message(self.current.channel, 'Now playing **{}**'.format(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def play(self, message, *, song : str):
        state = self.get_voice_state(message.server)
        opts = {'default_search': 'auto',
                'quiet': True,}

        if state.voice is None:
            voice_channel = message.author.voice_channel
            if voice_channel is None:
                await self.bot.send_message(message.channel, 'ボイスチャネルに入ってないじゃん!')
                await log.ErrorLog('User not in voice channel')
                return False
            state.voice = await self.bot.join_voice_channel(voice_channel)

        try:
            player = await state.voice.create_ytdl_player(song, ytdl_options=opts, after=state.toggle_next)
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await self.bot.send_message(message.channel, fmt.format(type(e).__name__, e))
        else:
            player.volume = 0.3
            entry = VoiceEntry(message, player)
            await log.MusicLog('{}: {}'.format(player.title, player.url))
            await state.songs.put(entry)

    async def pause(self, message):
        state = self.get_voice_state(message.server)
        if state.is_playing():
            player = state.player
            player.pause()

    async def resume(self, message):
        state = self.get_voice_state(message.server)
        if state.is_playing():
            player = state.player
            player.resume()

    async def stop(self, message):
        server = message.server
        state = self.get_voice_state(server)

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
        state = self.get_voice_state(message.server)
        if not state.is_playing():
            await self.bot.send_message(message.channel, 'Not playing any music right now...')
            return

        state.skip()

def SavePlaylist(PLdata, FileName='playlist.plf'):
    with open(FileName, 'wb') as f:
        pickle.dump(PLdata, f)

def LoadPlaylist(FileName='playlist.plf'):
    with open(FileName, 'rb') as f:
        PLdata = pickle.load(f)
    return PLdata

MusicMessage = None
player = None
InteractiveBot = None
PlayListFiles = {}
PlayListName = []
NextList = []
RandomFlag = False
PauseFlag = False
PlayFlag = False
IbotFlag = False
TitleFlag = True
version = '''PlatinaBot version: 2.3.4
Copyright (c) 2018 Glaz egy.'''
log = LogControl('bot.log')
config = ConfigParser()
if os.path.isfile('config.ini'): config.read('config.ini', encoding='utf-8')
else:
    log.ErrorLog('Config file not exist')
    sys.exit(1)
prefix = config['BOTDATA']['cmdprefix']
with open('help.dat', 'rb') as f:
    Data = pickle.load(f)
    CommandDict = Data['JP']
if os.path.isfile('playlist.plf'): PlayListFiles = LoadPlaylist()
else:
    PlayListFiles['default'] = {}
    SavePlaylist(PlayListFiles)
    PlayListFiles = LoadPlaylist()
NowPlayList = 'default'
PlayURLs = list(PlayListFiles[NowPlayList].keys())
UnmodifiableRole = config['ROLECONF']['unmodif_role'].split('@')
maindir = os.getcwd()

client = discord.Client()
Cal = Calendar(client)

TrueORFalse = {'Enable': True,
                'Disable': False}

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
                    if title is None: title = YoutubeDL().extract_info(url=url, download=False, process=False)['title']
                    url = 'https://www.youtube.com/watch?v='+ url if not 'http' in url else url
                    URLs[-1][-1] += '-'+title+'\n'+url+'\n'
                    if len(URLs[-1][-1]) > 750:
                        OutFlag = True
                        await EmbedOut(message.channel, 'All playlist: page{}'.format(len(URLs[-1])), keys[-1], URLs[-1][-1], 0x6b8e23)
                        URLs[-1].append('')
            if not OutFlag or URLs[-1][-1] != '':
                await EmbedOut(message.channel, 'All playlist: page{}'.format(len(URLs[-1])), keys[-1], URLs[-1][-1], 0x6b8e23)
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
                if title is None: title = YoutubeDL().extract_info(url=url, download=False, process=False)['title']
                url = 'https://www.youtube.com/watch?v='+ url if not 'http' in url else url
                URLs[-1] += '-'+title+'\n'+url+'\n'
                if len(URLs[-1]) > 750:
                    OutFlag = True
                    await EmbedOut(message.channel, 'Now playlist: page{}'.format(len(URLs)), NowPlayList, URLs[-1], 0x708090)
                    URLs.append('')
        if not OutFlag or URLs[-1] != '':
            await EmbedOut(message.channel, 'Now playlist: page{}'.format(len(URLs)), NowPlayList, URLs[-1], 0x708090)

async def EmbedOut(channel, disc, playname, url, color):
    embed = discord.Embed(description=disc, colour=color)
    embed.add_field(name=playname, value=url if url != '' else 'Empty', inline=True)
    await client.send_message(channel, embed=embed)

async def PermissionErrorFunc(message):
    await client.send_message(message.channel, 'このコマンドは君じゃ使えないんだよなぁ')
    await log.ErrorLog('Do not have permissions')

async def CmdSpliter(cmd, index):
    if '"' in cmd[index]:
        tempStr = cmd[index] + ' ' + cmd[index+1]
        SplitStr = tempStr.replace('"', '')
    else: SplitStr = cmd[index]
    return SplitStr

async def OptionError(message, cmd):
    if len(cmd) > 1:
        await client.send_message(message.channel, 'オプションが間違っている気がするなぁ')
        await log.ErrorLog('The option is incorrect error')
        return
    await client.send_message(message.channel, '`'+cmd[0]+'`だけじゃ何したいのか分からないんだけど')
    await log.ErrorLog('no option error') 

@client.event
async def on_ready():
    await log.Log('Bot is Logging in!!')

@client.event
async def on_message(message):
    global MusicMessage
    global player
    global InteractiveBot
    global NowPlayList
    global PlayURLs
    global RandomFlag
    global PauseFlag
    global PlayFlag
    global IbotFlag
    global TitleFlag
    if message.content.startswith(prefix+'role'):
        AddFlag = False
        DelFlag = False
        AddAnotherFlag = False
        DelAnotherFlag = False
        CmdFlag = False
        CreateFlag = False
        RemoveFlag = False
        AdminFlag = False
        permissions = message.channel.permissions_for(message.author)
        cmd = message.content.split()
        if message.author.bot:
            await PermissionErrorFunc(message)
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
            await client.send_message(message.channel, embed=embed)
            await log.Log('Confirmation role list')
            return
        if '--del' in cmd:
            if TrueORFalse[config['ROLECONF']['del_role_me']] and not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            DelFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--del')+1)
        if '--add' in cmd:
            if TrueORFalse[config['ROLECONF']['add_role_me']] and not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            AddFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--add')+1)
        if '--add-another' in cmd:
            if not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            AddAnotherFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--add-another')+2)
            UserName = await CmdSpliter(cmd, cmd.index('--add-another')+1)
        if '--del-another' in cmd:
            if not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            DelAnotherFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--del-another')+2)
            UserName = await CmdSpliter(cmd, cmd.index('--del-another')+1)
        if '--create' in cmd:
            if not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            CreateFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--create')+1)
        if '--create-admin' in cmd:
            if TrueORFalse[config['ROLECONF']['create_role']] and not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            CreateFlag = True
            AdminFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--create-admin')+1)
        if '--remove' in cmd:
            if TrueORFalse[config['ROLECONF']['remove_role']] and not permissions.administrator:
                await PermissionErrorFunc(message)
                return
            CmdFlag = True
            RemoveFlag = True
            RoleName = await CmdSpliter(cmd, cmd.index('--remove')+1)
        if (CreateFlag or RemoveFlag) and (AddFlag or DelFlag):
            await client.send_message(message.channel, 'そのコマンドは両立出来ないなぁ')
            await log.ErrorLog('A command for the server and a command for the member are entered error')
        if CreateFlag and RemoveFlag:
            await client.send_message(message.channel, '作るのと削除と、どっちが良いの!？')
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
                        await client.send_message(message.channel, '{}には管理者権限が無いので管理者権限を含む役職を作成できません'.format(message.author.name))
                        await log.Log('Create request higher level authority')
                        return
                else:
                    await client.create_role(message.server, name=RoleName, colour=discord.Colour(randint(0, 16777215)))
                    await log.Log('Create role: {}'.format(RoleName))
                await client.send_message(message.channel, '{}は誰のものになるのかな？'.format(RoleName))
            else:
                await client.send_message(message.channel, 'あるよ！ {} あるよッ！'.format(RoleName))
                await log.Log('Role: {} is exist in this server yet'.format(RoleName))
            return
        elif RemoveFlag:
            role = discord.utils.get(message.author.server.roles, name=RoleName)
            if role.permissions.administrator and not permissions.administrator:
                await client.send_message(message.channel, '{}には管理者権限が無いので管理者権限を含む役職を削除できません'.format(message.author.name))
                await log.Log('Deleate request higher level authority')
                return
            await client.delete_role(message.server, role)
            await client.send_message(message.channel, '{}はもう消されてしまいました……'.format(RoleName))
            await log.Log('Remove role: {}'.format(RoleName))
            return
        if AddFlag and DelFlag or AddAnotherFlag and DelAnotherFlag:
            await client.send_message(message.channel, '追加するの？　消すの？　はっきりしてよ……')
            await log.ErrorLog('Add and Del command are entered')
            return
        isChange = (not RoleName in UnmodifiableRole) or (TrueORFalse[config['ROLECONF']['unmodif_admin']] and permissions.administrator)
        role = discord.utils.get(message.author.server.roles, name=RoleName)
        if role is None:
            await client.send_message(message.channel, 'そんな役職無いよ!')
            await log.ErrorLog('Role: {} is not exist in this server'.format(RoleName))
            return
        elif AddAnotherFlag:
            user = discord.utils.get(message.author.server.menbers, name=UserName)
            if user is None:
                await client.send_message(message.channel, 'そんな人はいないんだけどな')
                await log.ErrorLog('User: {} is not exist in this server'.format(UserName))
                return
            await client.add_roles(user, role)
            await client.send_message(message.channel, '{}に{}の役職が追加されたよ！'.format(UserName, RoleName))
            await log.Log('Add role: {} in {}'.format(UserName, RoleName))
        elif DelAnotherFlag:
            user = discord.utils.get(message.author.server.menbers, name=UserName)
            if user is None:
                await client.send_message(message.channel, 'そんな人はいないんだけどな')
                await log.ErrorLog('User: {} is not exist in this server'.format(UserName))
                return
            await client.remove_roles(user, role)
            await client.send_message(message.channel, '{}の{}が削除されたよ！'.format(UserName, RoleName))
            await log.Log('Del role: {}\'s {}'.format(UserName, RoleName))
        elif AddFlag:
            if role.permissions.administrator and not permissions.administrator:
                await client.send_message(message.channel, '{}には管理者権限が無いので管理者権限を含む役職には成れません'.format(message.author.name))
                await log.Log('Request higher level authority')
                return
            if isChange:
                await client.add_roles(message.author, role)
                await client.send_message(message.channel, '{}に{}の役職が追加されたよ！'.format(message.author.name, RoleName))
                await log.Log('Add role: {} in {}'.format(message.author.name, RoleName))
            else:
                await client.send_message(message.channel, '{}は変更不可能役職です'.format(RoleName))
                await log.ErrorLog('Add request Unmodifiable role: {}'.format(RoleName))
        elif DelFlag:
            if isChange:
                await client.remove_roles(message.author, role)
                await client.send_message(message.channel, '{}の{}が削除されたよ！'.format(message.author.name, RoleName))
                await log.Log('Del role: {}\'s {}'.format(message.author.name, RoleName))
            else:
                await client.send_message(message.channel, '{}は変更不可能役職です'.format(RoleName))
                await log.ErrorLog('Add request Unmodifiable role: {}'.format(RoleName))
        if not CmdFlag: await OptionError(message, cmd)
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
                await client.send_message(message.channel, 'プレイリストが{}から{}へ変更されました'.format(temp, NowPlayList))
                await log.MusicLog('Play list change {} to {}'.format(temp, NowPlayList))
            except:
                await client.send_message(message.channel, 'そのプレイリストは存在しません')
                await log.ErrorLog('Request not exist Play list ')
                NowPlayList = temp
            return
        if '--list-make' in cmd:
            try:
                PlayListName = cmd[cmd.index('--list-make')+1]
            except:
                await client.send_message(message.channel, 'オプションに引数が無いよ！')
                await log.ErrorLog('Not argment')
                return
            if PlayListName in PlayListFiles.keys():
                await client.send_message(message.channel, 'そのプレイリストはすでに存在します')
                await log.ErrorLog('Make request exist play list')
            else:
                PlayListFiles[PlayListName] = {}
                SavePlaylist(PlayListFiles)
                NowPlayList = PlayListName
                PlayURLs = list(PlayListFiles[NowPlayList].keys())
                await client.send_message(message.channel, '新しくプレイリストが作成されました')
                await log.MusicLog('Make play list {}'.format(PlayListName))
            return
        if '--list-remove' in cmd:
            try:
                PlayListName = cmd[cmd.index('--list-make')+1]
            except:
                await client.send_message(message.channel, 'オプションに引数が無いよ！')
                await log.ErrorLog('Not argment')
                return
            if PlayListName in PlayListFiles.keys() and not 'default' == PlayListName:
                del PlayListFiles[PlayListName]
                SavePlaylist(PlayListFiles)
                await client.send_message(message.channel, '{}を削除します'.format(PlayListName))
                await log.MusicLog('Remove play list {}'.format(PlayListName))
                NowPlayList = 'default'
            else:
                await client.send_message(message.channel, 'そのプレイリストは存在しません')
                await log.ErrorLog('Remove request not exist play list')
            return
        if '--list-clear' in cmd:
            if len(cmd) > 2:
                ClearPlaylist = cmd[cmd.index('--list-clear')+1]
                PlayListFiles[ClearPlaylist] = {}
                await client.send_message(message.channel, '{}をクリアしました'.format(ClearPlaylist))
                await log.MusicLog('Cleared {}'.format(ClearPlaylist))
                SavePlaylist(PlayListFiles)
            else:
                await client.send_message(message.channel, 'プレイリスト名を入力してください')
                await log.ErrorLog('Need Playlist name')
            return
        if '--list-clear-all' in cmd:
            for key in PlayListFiles.keys():
                PlayListFiles[key] = {}
                await client.send_message(message.channel, '{}をクリアしました'.format(key))
                await log.MusicLog('Cleared {}'.format(key))
            SavePlaylist(PlayListFiles)
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
                if not len(PlayURLs) == 1: music = randint(0, len(PlayURLs)-1)
                elif not len(PlayURLs) == 0: music = 0
                else:
                    await client.send_message(message.channle, 'プレイリストに曲が入ってないよ！')
                    await log.ErrorLog('Not music in playlist')
                    return
                try:
                    player = MusicPlayer(client)
                    song = PlayURLs[music if RandomFlag else 0] if not urlUseFlag else url
                    await player.play(message, song=('https://www.youtube.com/watch?v='+ song if not 'http' in song else song))
                    if not urlUseFlag: PlayURLs.remove(PlayURLs[music if RandomFlag else 0])
                    if len(PlayURLs) == 0: PlayURLs = list(PlayListFiles[NowPlayList].keys())
                    PlayFlag = True
                    await client.change_presence(game=discord.Game(name='MusicPlayer'))
                except discord.errors.InvalidArgument:
                    pass
                except discord.ClientException:
                    await log.ErrorLog('Already Music playing')
                    await client.send_message(message.channel, 'Already Music playing')
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
                await client.send_message(message.channel, '今、プレイヤーは再生してないよ！')
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
        if not cmdFlag: await OptionError(message, cmd)
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
                    PlayListFiles[ListName][link] = YoutubeDL().extract_info(url=link, download=False, process=False)['title']
                    PlayURLs.append(link)
                    await log.MusicLog('Add {}'.format(link))
                    ineed[-1] += '-{}\n'.format(PlayListFiles[ListName][link])
                    NotFound = False
                    if len(ineed[-1]) > 750:
                        await EmbedOut(message.channel, 'Wish List page {}'.format(len(ineed)), 'Music', ineed[-1], 0x303030)
                        ineed.append('')
                        NotFound = True
                except:
                    await client.send_message(message.channel, '{} なんて無いよ'.format(linkraw))
                    await log.ErrorLog('{} is Not Found'.format(linkraw))
            else:
                await log.MusicLog('Music Overlap {}'.format(link))
                await client.send_message(message.channel, 'その曲もう入ってない？')
        SavePlaylist(PlayListFiles)
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
                await client.send_message(message.channel, 'そんな曲入ってたかな？')
        SavePlaylist(PlayListFiles)
        if not notneed[-1] == '' and not NotFound: await EmbedOut(message.channel, 'Delete List page {}'.format(len(notneed)), 'Music', notneed[-1], 0x749812)
        if len(PlayURLs) == 0: PlayURLs = list(PlayListFiles[NowPlayList].keys())
    elif message.content.startswith(prefix+'help'):
        cmds = message.content.split()
        if len(cmds) > 1:
            for cmd in cmds:
                if cmd == 'role' or cmd == 'music':
                    cmdline = ''
                    for key, value in CommandDict[cmd].items():
                        cmdline += key + ': ' + value + '\n'
                    embed = discord.Embed(description=cmd+' Commmand List', colour=0x008b8b)
                    embed.add_field(name='Commands', value=cmdline, inline=True)
                    await client.send_message(message.channel, embed=embed)
        else:
            cmdline = ''
            for key, value in CommandDict['help'].items():
                cmdline += key + ': ' + value + '\n'
            embed = discord.Embed(description='Commmand List', colour=0x4169e1)
            embed.add_field(name='Commands', value=cmdline, inline=True)
            await client.send_message(message.channel, embed=embed)
    elif message.content.startswith(prefix+'version'):
        await log.Log(version)
        await client.send_message(message.channel, version)
        if IbotFlag:
            await log.Log(InteractiveBot.__version__)
            await client.send_message(message.channel, InteractiveBot.__version__)
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
            PermissionErrorFunc(message)
    elif message.content.startswith(prefix+'debag'):
        await on_member_join(message.author)
    elif message.content.startswith(prefix+'say'):
        cmds = message.content.split()[1:]
        out = ''
        for cmd in cmds: out += cmd+' '
        await client.send_message(message.channel, out)
        await log.Log('Bot say {}'.format(out))
    elif message.content.startswith(prefix+'cal'):
        cmd = message.content.split()
        if '--add' in cmd:
            EventDay = cmd[cmd.index('--add')+1]
            EventName = cmd[cmd.index('--add')+2]
            EventContent = cmd[cmd.index('--add')+3]
            Cal.CalRegister(EventDay, EventName, EventContent, message.channel)
        if '--print' in cmd:
            await Cal.CalTask()
            await client.send_message(message.channel, str(Cal.CalData))
    elif message.content.startswith(prefix+'ibot'):
        cmd = message.content.split()
        if TrueORFalse[config['BOTMODE']['ibot_mode']]:
            if '--start' in cmd:
                if not IbotFlag:
                    IbotFlag = True
                    InteractiveBot = interabot.interabot.Bot()
                    await client.send_message(message.channel, 'インタラクティブボットモードをONにしました')
                    await log.Log('Interactive bot mode is ON')
                    await client.change_presence(game=discord.Game(name='IBOT'))
                else:
                    await client.send_message(message.channel, 'インタラクティブモードはすでにONになっています')
                    await log.ErrorLog('Already interractive bot mode is ON')
            elif '--stop' in cmd:
                if IbotFlag:
                    IbotFlag = False
                    InteractiveBot = None
                    await client.send_message(message.channel, 'インタラクティブボットモードをOFFにしました')
                    await log.Log('Interactive bot mode is OFF')
                    await client.change_presence(game=(None if not PlayFlag else discord.Game(name='MusicPlayer')))
                else:
                    await client.send_message(message.channel, 'インタラクティブモードはすでにOFFになっています')
                    await log.ErrorLog('Already interractive bot mode is OFF')
            else: await OptionError(message, cmd)
        else:
            await client.send_message(message.channel, '現在このコマンドは無効化されています')
            await log.ErrorLog('Ibot mode is Disable')
    elif message.content.startswith(prefix+'pwd'):
        await client.send_message(message.channel, os.getcwd())
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
                    await client.send_message(message.channel, files[-1])
                    files.append('')
        await client.send_message(message.channel, files[-1])
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
                    await client.send_message(message.channel, lines[-1])
                    lines.append('')
            if not outFlag or not lines[-1] == '': await client.send_message(message.channel, lines[-1])
    elif message.content.startswith(prefix):
        await client.send_message(message.channel, '該当するコマンドがありません')
        await log.ErrorLog('Command is notfound')
    elif IbotFlag and not message.author.bot:
        comment = InteractiveBot.Response(message.content)
        if not comment is None:
            await client.send_message(message.channel, comment)
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
