# -*- coding: utf-8 -*-

from configparser import ConfigParser
from collections import OrderedDict
from random import random, randint
from datetime import datetime
from copy import deepcopy
from glob import glob
import discord
import hashlib
import asyncio
import time
import sys
import os


class LogControl:
    def __init__(self, FileName):
        self.Name = FileName

    async def Log(self, WriteText, write_type='a'):
        with open(self.Name, write_type) as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Bot Log] '+WriteText+'\n')

    async def ErrorLog(self, WriteText, write_type='a'):
        with open(self.Name, write_type) as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Error Log] '+WriteText+'\n')

    async def MusicLog(self, WriteText, write_type='a'):
        with open(self.Name, write_type) as f:
            f.write(datetime.now().strftime('[%Y/%m/%d %H:%M:%S]')+'[Music Log] '+WriteText+'\n')

class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '{} uploaded by {}: `{}`'.format(self.player.title, self.player.uploader, self.player.url)
        return fmt

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
            await self.bot.send_message(self.current.channel, 'Now playing **{}**'.format(self.current))
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
        opts = {
            'default_search': 'auto',
            'quiet': True,
        }

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

MusicMessage = None
player = None
PlayListFiles = {}
PlayListName = []
NextList = []
RandomFlag = False
PauseFlag = False
PlayFlag = False
version = 'version: 2.1.3'
log = LogControl('bot.log')
config = ConfigParser()
if os.path.isfile('config.ini'):
    config.read('config.ini', encoding='utf-8')
else:
    log.ErrorLog('Config file not exist')
    sys.exit(1)
token = config['BOTDATA']['token']
prefix = config['BOTDATA']['cmdprefix']
if len(PlayListFiles) == 0:
    PLFList = glob('*.plf')
    for PLF in PLFList:
        PlayListName.append(PLF.replace('.plf', ''))
        PlayListFiles[PlayListName[-1]] = []
        with open(PLF, 'r') as f:
            temp = f.readlines()
        for play in temp:
            if not play == '':
                PlayListFiles[PlayListName[-1]].append(play.replace('\n', ''))
NowPlayList = 'default'
PlayURLs = deepcopy(PlayListFiles['default'])
UnmodifiableRole = config['ROLECONF']['unmodif_role']
client = discord.Client()

CommandDict = OrderedDict()
CommandDict = {'`'+prefix+'role`': '役職関係のコマンド 詳しくは`{}help roleを見てね！`'.format(prefix),
                '`'+prefix+'play`': '音楽を再生するかもしれないコマンド `{}help music`で詳しく確認できるよ！'.format(prefix),
                '`'+prefix+'version`': '現在のバージョンを確認できる',
                '`'+prefix+'help`' : '今見てるのに説明いる？　ヘルプ用なんだけど'}

PlayCmdDict = OrderedDict()
PlayCmdDict = {'`'+prefix+'music option`': '音楽を再生します　`-r`を付けるとランダム再生 `$[url]`でurlを優先再生 `--list`でプレイリストを確認',
                '`-r`': 'ランダム再生を有効にします `--next`または`--play`と同時に使ってもOK',
                '`-n`': 'ランダム再生を無効にします 同上',
                '`--list`': 'プレイリストを確認します',
                '`--list-all`': '全てのプレイリストを確認します',
                '`--list-make [PlayListName]`': 'プレイリストを作ります',
                '`--list-change [PlayListName]`': '現在のプレイリストを変更します',
                '`--next`': '次の曲へ移ります',
                '`--stop`': '曲の再生をストップします',
                '`--pause`': '曲の再生を一時停止します',
                '`'+prefix+'addmusic url [url]...`': '音楽をプレイリストに追加',
                '`'+prefix+'delmusic url [url]...`': 'プレイリストから削除',
                '`'+prefix+'musiclist`': 'プレイリストを確認(廃止予定)'}

RoleCmdDict = OrderedDict()
RoleCmdDict = {'`'+prefix+'role option`': '`!role`はオプションを必ず付けてね！',
                '`--list`': '現在ある役職を確認できます',
                '`--create RoleName`': '役職を新しく作れます',
                '`--create-admin RoleName`': '管理者権限を持つ役職を作ります(管理者のみ)',
                '`--remove RoleName`': '役職を消せます',
                '`--add RoleName`': '自分に役職を追加します',
                '`--del RoleName`': '自分の役職を消します',}

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
        PlayURLs = deepcopy(PlayListFiles[NowPlayList])

async def ListOut(message, all=False):
    global NowPlayList
    if all:
        await log.Log('Play list check all')
        URLs = []
        keys = []
        for key, value in PlayListFiles.items():
            URLs.append('')
            keys.append(key)
            if key == NowPlayList: keys[-1] += '(現在のプレイリスト)'
            for url in value:
                URLs[-1] += ' '+url+'\n'
        embed = discord.Embed(description='全てのプレイリスト', colour=0x6b8e23)
        for i in range(len(keys)):
            embed.add_field(name=keys[i], value=URLs[i], inline=True)
        await client.send_message(message.channel, embed=embed)
    else:
        await log.Log('Call playlist is {}'.format(PlayListFiles[NowPlayList]))
        URLs = ''
        for url in PlayListFiles[NowPlayList]:
            URLs += ' '+url+'\n'
        embed = discord.Embed(description='現在のプレイリスト', colour=0x708090)
        embed.add_field(name='プレイリスト名: '+NowPlayList, value=URLs, inline=True)
        await client.send_message(message.channel, embed=embed)
            
async def PermissionErrorFunc(message):
    await client.send_message(message.channel, 'このコマンドは君じゃ使えないんだよなぁ')
    await log.ErrorLog('Do not have permissions')

async def CmdSpliter(cmd, index):
    if '"' in cmd[index]:
        tempStr = cmd[index] + ' ' + cmd[index+1]
        SplitStr = tempStr.replace('"', '')
    else:
        SplitStr = cmd[index]
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
    global NowPlayList
    global PlayURLs
    global RandomFlag
    global PauseFlag
    global PlayFlag
    if message.content.startswith(prefix+'role'):
        DelFlag = False
        AddFlag = False
        CmdFlag = False
        CreateFlag = False
        RemoveFlag = False
        AdminFlag = False
        permissions = message.channel.permissions_for(message.author)
        cmd = message.content.split()
        if '--list' in cmd:
            CmdFlag = True
            RoleList = message.server.roles
            AdminRoles = ''
            NomalRoles = ''
            for Role in RoleList:
                if '@everyone' == Role.name:
                    pass
                elif Role.permissions.administrator:
                    AdminRoles += Role.name+'\n'
                else:
                    NomalRoles += Role.name+'\n'
            embed = discord.Embed(description='役職総リスト', colour=0x228b22)
            embed.add_field(name='管理役職', value=AdminRoles, inline=True)
            embed.add_field(name='非管理役職', value=NomalRoles, inline=True)
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
        if '--create' in cmd:
            if TrueORFalse[config['ROLECONF']['create_role']] and not permissions.administrator:
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
        if not CmdFlag:
            await OptionError(message, cmd)
            return
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
        if AddFlag and DelFlag:
            await client.send_message(message.channel, '追加するの？　消すの？　はっきりしてよ……')
            await log.ErrorLog('Add and Del command are entered')
            return
        isChange = (not RoleName in UnmodifiableRole) or (TrueORFalse[config['ROLECONF']['unmodif_admin']] and permissions.administrator)
        role = discord.utils.get(message.author.server.roles, name=RoleName)
        if role is None:
            await client.send_message(message.channel, 'そんな役職無いよ!')
            await log.ErrorLog('Role: {} is not exist in this server'.format(RoleName))
            return
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

    if message.content.startswith(prefix+'music'):
        urlUseFlag = False
        cmdFlag = False
        cmd = message.content.split()
        if '--list' in cmd:
            await ListOut(message)
            return
        if '--list-all' in cmd:
            await ListOut(message, all=True)
            return
        if '--list-change' in cmd:
            temp = NowPlayList
            try:
                NowPlayList = cmd[cmd.index('--list-change')+1]
            except:
                NowPlayList = 'default'
            try:
                PlayURLs = deepcopy(PlayListFiles[NowPlayList])
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
                await log.ErrorLog('Make request exit play list')
            else:
                with open(PlayListName+'.plf', 'w') as f:
                    pass
                NowPlayList = PlayListName
                PlayListFiles[NowPlayList] = []
                await client.send_message(message.channel, '新しくプレイリストが作成されました')
                await log.MusicLog('Make play list {}'.format(PlayListName))
            return
        if len(cmd) >= 2:
            for cmdpar in cmd:
                if '$' in cmdpar:
                    urlUseFlag = True
                    url = cmdpar.replace('$', '')
        MusicMessage = message
        if '--play' in cmd:
            RandomFlag = False
            if '-r' in cmd: RandomFlag = True
            if PauseFlag:
                await player.resume(message)
            else:
                if not len(PlayURLs) == 0: music = randint(0, len(PlayURLs)-1)
                else: music = 0
                try:
                    player = MusicPlayer(client)
                    song = PlayURLs[music if RandomFlag else 0] if not urlUseFlag else url
                    await player.play(message, song=('https://www.youtube.com/watch?v='+ song if not 'http' in song else song))
                    if not urlUseFlag: PlayURLs.remove(PlayURLs[music if RandomFlag else 0])
                    if len(PlayURLs) == 0: PlayURLs = deepcopy(PlayListFiles[NowPlayList])
                    PlayFlag = True
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
        if '--next' in cmd:
            await log.MusicLog('Music skip')
            await player.skip(message)
            cmdFlag = True
        if '--stop' in cmd:
            if player is None:
                await client.send_message(message.channel, '今、プレイヤーは再生してないよ！')
                await log.ErrorLog('Not play music')
                return
            await log.MusicLog('Music stop')
            await player.stop(message)
            PlayFlag = False
            player = None
            PlayURLs = deepcopy(PlayListFiles[NowPlayList])
            cmdFlag = True
        if '--pause' in cmd:
            await log.MusicLog('Music pause')
            await player.pause(message)
            PauseFlag = True
            PlayFlag = False
            cmdFlag = True
        if not cmdFlag:
            await OptionError(message, cmd)

    if message.content.startswith(prefix+'addmusic'):
        links = message.content.split()[1:]
        if links[0] in PlayListFiles.keys():
            ListName = links[0]
            links.remove(links[0])
        else: ListName = NowPlayList
        for link in links:
            link = link.replace('https://www.youtube.com/watch?v=', '')
            link = link.replace('https://youtu.be/', '')
            if not link in PlayListFiles[ListName]:
                PlayListFiles[ListName].append(link)
                PlayURLs.append(link)
                await log.MusicLog('Add {}'.format(link))
                await client.send_message(message.channel, '`{}` が欲しかった！'.format('https://www.youtube.com/watch?v='+link))
                with open(ListName+'.plf', 'a') as f:
                    f.write('{}\n'.format(link))
            else:
                await log.MusicLog('Music Overlap {}'.format(link))
                await client.send_message(message.channel, 'その曲もう入ってない？')

    if message.content.startswith(prefix+'musiclist'):
        await ListOut(message)

    if message.content.startswith('!delmusic'):
        links = message.content.split()[1:]
        if links[0] in PlayListFiles.keys():
            ListName = links[0]
            links.remove(links[0])
        else: ListName = NowPlayList
        for link in links:
            link = link.replace('https://www.youtube.com/watch?v=', '')
            link = link.replace('youtube.com/watch?v=', '')
            link = link.replace('https://youtu.be/', '')
            try:
                PlayListFiles[ListName].remove(link)
                try:
                    PlayURLs.remove(link)
                except:
                    pass
                await log.MusicLog('Del {}'.format(link))
                await client.send_message(message.channel, '`{}` なんてもういらないよね！'.format('https://www.youtube.com/watch?v='+link))
                with open(ListName+'.plf', 'w') as f:
                    for URL in PlayListFiles[ListName]:
                        f.write('{}\n'.format(URL))
            except:
                await log.ErrorLog('{} not exist list'.format(link))
                await client.send_message(message.channel, 'そんな曲入ってたかな？')

    if message.content.startswith(prefix+'version'):
        await log.Log(version)
        await client.send_message(message.channel, version)

    if message.content.startswith(prefix+'help'):
        cmds = message.content.split()
        if len(cmds) > 1:
            for cmd in cmds:
                if cmd == 'music':
                    cmdline = ''
                    for key, value in PlayCmdDict.items():
                        cmdline += key + ': ' + value + '\n'
                    embed = discord.Embed(description='playコマンド関連リスト', colour=0xe9967a)
                    embed.add_field(name='コマンドたち', value=cmdline, inline=True)
                    await client.send_message(message.channel, embed=embed)
                if cmd == 'role':
                    cmdline = ''
                    for key, value in RoleCmdDict.items():
                        cmdline += key + ': ' + value + '\n'
                    embed = discord.Embed(description='roleコマンド関連リスト', colour=0x008b8b)
                    embed.add_field(name='コマンドたち', value=cmdline, inline=True)
                    await client.send_message(message.channel, embed=embed)
        else:
            cmdline = ''
            for key, value in CommandDict.items():
                cmdline += key + ': ' + value + '\n'
            embed = discord.Embed(description='コマンド確認リスト', colour=0x4169e1)
            embed.add_field(name='コマンドたち', value=cmdline, inline=True)
            await client.send_message(message.channel, embed=embed)

    if message.content.startswith(prefix+'exit'):
        AdminCheck = (message.author.id == config['ADMINDATA']['botowner'] if config['ADMINDATA']['botowner'] != 'None' else False)
        if TrueORFalse[config['ADMINDATA']['passuse']] and not AdminCheck:
            PassWord = message.content.split()[1]
            HashWord = hashlib.sha256(PassWord.encode('utf-8')).hexdigest()
            AdminCheck = (HashWord == config['ADMINDATA']['passhash'] if config['ADMINDATA']['passhash'] != 'None' else False)
        if AdminCheck:
            await log.Log('Bot exit')
            await client.close()
            await sys.exit(0)
        else:
            PermissionErrorFunc(message)

    if message.content.startswith(prefix+'debag'):
        await on_member_join(message.author)
    
    if message.content.startswith(prefix+'say'):
        cmds = message.content.split()[1:]
        out = ''
        for cmd in cmds:
            out += cmd+' '
        await client.send_message(message.channel, out)

@client.event
async def on_member_join(member):
    if TrueORFalse[config['JOINCONF']['joinevent']]:
        jointexts = config['JOINCONF']['jointext'].replace('\n', '')
        jointexts = jointexts.split('@/')
        text = jointexts[randint(0, len(jointexts)-1)].strip()
        channel = client.get_channel(config['BOTDATA']['mainch'])
        readme = client.get_channel(config['BOTDATA']['readmech'])
        if channel is None or readme is None:
            return
        text = text.replace('[MenberName]', member.name)
        text = text.replace('[ChannelName]', readme.name)
        await client.send_message(channel, text)
    await log.Log('Join {}'.format(member.name))
    print('Join {}'.format(member.name))


client.run(token)