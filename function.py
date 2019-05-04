# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from random import randint
import discord
import pickle


def CmdSpliter(cmd, index, sufIndex=False):
    Flag = True
    if '"' in cmd[index]:
        tempStr = cmd[index]
        while Flag:
            index += 1
            tempStr += ' ' + cmd[index]
            if '"' in cmd[index]: break
        SplitStr = tempStr.replace('"', '').strip()
    else: SplitStr = cmd[index]
    if sufIndex: return SplitStr, index
    else: return SplitStr

async def NotArgsment(log, client, message):
    await client.send_message(message.channel, 'オプションに引数が無いよ！')
    await log.ErrorLog('Not argment')

async def EmbedOut(client, channel, disc, playname, url, color):
    embed = discord.Embed(description=disc, colour=color)
    embed.add_field(name=playname, value=url if url != '' else 'Empty', inline=True)
    await client.send_message(channel, embed=embed)

async def PermissionErrorFunc(log, client, message):
    await client.send_message(message.channel, 'このコマンドは君じゃ使えないんだよなぁ')
    await log.ErrorLog('Do not have permissions')

async def OptionError(log, client, message, cmd):
    if len(cmd) > 1:
        await client.send_message(message.channel, 'オプションが間違っている気がするなぁ')
        await log.ErrorLog('The option is incorrect error')
        return
    await client.send_message(message.channel, '`'+cmd[0]+'`だけじゃ何したいのか分からないんだけど')
    await log.ErrorLog('no option error')

def SaveBinData(PLdata, FileName):
    with open(FileName, 'wb') as f:
        pickle.dump(PLdata, f)

def LoadBinData(FileName):
    with open(FileName, 'rb') as f:
        PLdata = pickle.load(f)
    return PLdata

def ArgsInit():
    parser = ArgumentParser(description='Playlist, log and config set args')
    parser.add_argument('--playlist', default='playlist.plf')
    parser.add_argument('--log', default='bot.log')
    parser.add_argument('--config', default='config.ini')
    parser.add_argument('--spell', default='Spelldata.sp')
    parser.add_argument('--study', default='Studydata.sf')
    parser.add_argument('--book', default='bookfile.bf')
    return parser.parse_args()