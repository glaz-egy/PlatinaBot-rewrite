# -*- coding:utf-8 -*-

from collections import OrderedDict
from configparser import ConfigParser
import pickle
import os

config = ConfigParser()
config.read('config.ini', encoding='utf-8')
prefix = config['BOTDATA']['cmdprefix']

CommandDictJP = OrderedDict()
CommandDictJP = {'help': OrderedDict(),
                'music': OrderedDict(),
                'role': OrderedDict()}

CommandDictJP['help'] = { '`'+prefix+'role`': '役職関係のコマンド 詳しくは`{}help roleを見てね！`'.format(prefix),
                        '`'+prefix+'music`': '音楽を再生するかもしれないコマンド `{}help music`で詳しく確認できるよ！'.format(prefix),
                        '`'+prefix+'say SayText`': 'ボットがSayTextの内容を発言します それだけのコマンド',
                        '`'+prefix+'ibot option`': '`--start`でIBOTモードをON,`--stop`でOFFにします',
                        '`'+prefix+'version`': '現在のバージョンを確認できる',
                        '`'+prefix+'help`' : '今見てるのに説明いる？　ヘルプ用なんだけど',
                        '`'+prefix+'exit [ExitPassword]`': 'ボット管理者かExitPasswordを知っている人のみボットを停止できます',
                        '隠し機能': '隠し機能が有るから探してみてね'}

CommandDictJP['music'] = {'`'+prefix+'music option`': '音楽関連のコマンドです',
                        '`-r`': 'ランダム再生を有効にします `--next`または`--play`と同時に使ってもOK',
                        '`-n`': 'ランダム再生を無効にします 同上',
                        '`--list`': 'プレイリストを確認します',
                        '`--list-all`': '全てのプレイリストを確認します',
                        '`--list-make PlayListName`': 'プレイリストを作ります',
                        '`--list-change PlayListName`': '現在のプレイリストを変更します',
                        '`--list-remove PlayListName`' : 'プレイリストを削除します 現在のプレイリストはdefaultに変更されます',
                        '`--list-clear PlayListName`': 'プレイリストを初期化します',
                        '`--list-clear-all`': '全てのプレイリストを初期化します',
                        '`--no-out`': '曲名の出力をしないようにするオプションです　標準では出力される様になっています',
                        '`--next`': '次の曲へ移ります',
                        '`--stop`': '曲の再生をストップします',
                        '`--pause`': '曲の再生を一時停止します',
                        '`$url`': 'URLを優先的に再生します',
                        '`'+prefix+'addmusic url [url]...`': '音楽をプレイリストに追加',
                        '`'+prefix+'delmusic url [url]...`': 'プレイリストから削除'}

CommandDictJP['role'] = {'`'+prefix+'role option`': '`role`はオプションを必ず付けてね！',
                        '`--list`': '現在ある役職を確認できます',
                        '`--create RoleName`': '役職を新しく作れます',
                        '`--create-admin RoleName`': '管理者権限を持つ役職を作ります(管理者のみ)',
                        '`--delete RoleName`': '役職を消せます',
                        '`--add RoleName`': '自分に役職を追加します',
                        '`--rm RoleName`': '自分の役職を消します',
                        '`--add-another UserName RoleName`': '`UserName`の役職を追加します(管理者のみ)',
                        '`--rm-another UserName RoleName`': '`UserName`から役職を削除します(管理者のみ)'}

CommandDictEN = OrderedDict()
CommandDictEN = {'help': OrderedDict(),
                'music': OrderedDict(),
                'role': OrderedDict()}

CommandDictEN['help'] = { '`'+prefix+'role`': 'Role relation command  For more`{}help role`'.format(prefix),
                        '`'+prefix+'play`': 'Musci relation command  For more`{}help music`'.format(prefix),
                        '`'+prefix+'say SayText`': 'Bot speaks the contents of SayText',
                        '`'+prefix+'ibot option`': '`--start`:IBOT mode is ON,`--stop`:OFF',
                        '`'+prefix+'version`': 'Now version check',
                        '`'+prefix+'help`' : 'Now see',
                        '`'+prefix+'exit [ExitPassword]`': 'Bot exit command',
                        'easter egg': 'easter egg'}

CommandDictEN['music'] = {'`'+prefix+'music option`': '音楽関連のコマンドです',
                        '`-r`': 'ランダム再生を有効にします `--next`または`--play`と同時に使ってもOK',
                        '`-n`': 'ランダム再生を無効にします 同上',
                        '`--list`': 'プレイリストを確認します',
                        '`--list-all`': '全てのプレイリストを確認します',
                        '`--list-make PlayListName`': 'プレイリストを作ります',
                        '`--list-change PlayListName`': '現在のプレイリストを変更します',
                        '`--list-remove PlayListName`' : 'プレイリストを削除します 現在のプレイリストはdefaultに変更されます',
                        '`--list-clear PlayListName`': 'プレイリストを初期化します',
                        '`--list-clear-all`': '全てのプレイリストを初期化します',
                        '`--no-out`': '曲名の出力をしないようにするオプションです　標準では出力される様になっています',
                        '`--next`': '次の曲へ移ります',
                        '`--stop`': '曲の再生をストップします',
                        '`--pause`': '曲の再生を一時停止します',
                        '`$url`': 'URLを優先的に再生します',
                        '`'+prefix+'addmusic url [url]...`': '音楽をプレイリストに追加',
                        '`'+prefix+'delmusic url [url]...`': 'プレイリストから削除'}

CommandDictEN['role'] = {'`'+prefix+'role option`': '`role`はオプションを必ず付けてね！',
                        '`--list`': '現在ある役職を確認できます',
                        '`--create RoleName`': '役職を新しく作れます',
                        '`--create-admin RoleName`': '管理者権限を持つ役職を作ります(管理者のみ)',
                        '`--remove RoleName`': '役職を消せます',
                        '`--add RoleName`': '自分に役職を追加します',
                        '`--del RoleName`': '自分の役職を消します',
                        '`--add-another UserName RoleName`': '`UserName`の役職を追加します(管理者のみ)',
                        '`--del-another UserName RoleName`': '`UserName`から役職を削除します(管理者のみ)'}

with open('help.dat', 'wb') as f:
    OutData = {}
    OutData['JP'] = CommandDictJP
    OutData['EN'] = CommandDictEN
    pickle.dump(OutData, f)
