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
    await message.channel.send('オプションに引数が無いよ！')
    await log.ErrorLog('Not argment')

async def EmbedOut(channel, disc, playname, url, color=0x000000):
    embed = discord.Embed(description=disc, colour=color)
    embed.add_field(name=playname, value=url, inline=True)
    await channel.send(embed=embed)

async def PermissionErrorFunc(log, client, message):
    await message.channel.send('このコマンドは君じゃ使えないんだよなぁ')
    await log.ErrorLog('Do not have permissions')

async def OptionError(log, client, message, cmd):
    if len(cmd) > 1:
        await message.channel.send('オプションが間違っている気がするなぁ')
        await log.ErrorLog('The option is incorrect error')
        return
    await message.channel.send('`'+cmd[0]+'`だけじゃ何したいのか分からないんだけど')
    await log.ErrorLog('no option error')

def SaveBinData(PLdata, FileName):
    with open(FileName, 'wb') as f:
        pickle.dump(PLdata, f)

def LoadBinData(FileName):
    with open(FileName, 'rb') as f:
        PLdata = pickle.load(f)
    return PLdata

def ArgsInit(MainCall=True):
    parser = ArgumentParser(description='Playlist, log and config set args')
    if MainCall:
        parser.add_argument('--playlist', default='playlist.plf')
        parser.add_argument('--log', default='bot.log')
        parser.add_argument('--config', default='config.ini')
        parser.add_argument('--spell', default='Spelldata.sp')
        parser.add_argument('--study', default='Studydata.sf')
        parser.add_argument('--book', default='bookfile.bf')
        parser.add_argument('--schedule', default='schedule.sd')
        parser.add_argument('--job', default='job.jf')
    else:
        parser.add_argument('--config', default='config.ini')
        parser.add_argument('--schedule', default='schedule.sd')
        parser.add_argument('--date', required=True)
    return parser.parse_args()