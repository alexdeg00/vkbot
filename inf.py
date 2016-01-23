#!/usr/bin/python3

import time
import sys
from subprocess import Popen, PIPE
from vkbot import vk_bot, CONF_START
import vkapi
import captcha
import re
import check_friend
from calc import evalExpression
import log
import config


_bot_message = re.compile(r'^\(.+\)')
def isBotMessage(msg):
    return _bot_message.match(msg.strip())


class cpp_bot:
    def __init__(self, filename):
        self.bot = Popen([filename], stdout=PIPE, stdin=PIPE)

    def interact(self, msg):
        self.bot.stdin.write(msg.replace('\n', '\a').strip().encode() + b'\n')
        self.bot.stdin.flush()
        answer = self.bot.stdout.readline().rstrip().replace(b'\a', b'\n')
        return answer.decode().strip()

bot = cpp_bot('./chat.exe')

class ban_manager:
    def __init__(self, filename, user_cache):
        self.filename = filename
        self.users = user_cache
        banign = open(filename).read().split()
        self.banned = set(int(i[1:]) for i in banign if i.startswith('$'))
        self.ignored = set(int(i) for i in banign if not i.startswith('$'))

    def write(self):
        s = ['$' + str(i) for i in sorted(self.banned)] + list(map(str, sorted(self.ignored)))
        with open(self.filename, 'w') as f:
            f.write('\n'.join(s))

    # {name} - first_name last_name
    # {id} - id
    def printableName(self, pid, user_fmt = '{name}', conf_fmt = 'Conf {id}'):
        if pid > CONF_START:
            return conf_fmt.format(id=(pid - CONF_START))
        else:
            return user_fmt.format(id=(pid), name=self.users[pid]['first_name'] + ' ' + self.users[pid]['last_name'])

    def ban(self, pid):
        if pid in self.banned:
            return 'Already banned!'
        self.banned.add(pid)
        self.write()
        return self.printableName(pid) + ' banned'

    def ignore(self, pid):
        if pid in self.ignored:
            return 'Already ignored!'
        self.ignored.add(pid)
        self.write()
        return self.printableName(pid) + 'ignored'

    def unban(self, pid):
        if pid == '*':
            ret = '{} unbanned'.format(', '.join(self.banned))
            self.banned = set()
        elif pid not in self.banned:
            return 'Not banned!'
        else:
            self.banned.discard(pid)
            ret = self.printableName(pid) + ' unbanned'
        self.write()
        return ret

    def unignore(self, pid):
        if pid == '*':
            ret = '{} unignored'.format(', '.join(self.ignored))
            self.ignored = set()
        elif pid not in self.ignored:
            return 'Not ignored!'
        else:
            self.ignored.discard(pid)
            ret = self.printableName(pid) + ' unignored'
        self.write()
        return ret


_timeto = {}
def timeto(name, interval):
    if time.time() > _timeto.get(name, 0) + interval:
        _timeto[name] = time.time()
        return 1
    return 0


# conf_id == -1: comment
def getBotReply(uid, message, conf_id, method=''):
    if message is None:
        return None

    message = message.replace('\u0401', '\u0415').replace('\u0451', '\u0435')  # yo
    message = message.replace('\u0490', '\u0413').replace('\u0491', '\u0433')  # g
    message = message.replace('\u0404', '\u042d').replace('\u0454', '\u044d')  # e
    message = message.replace('\u0406', '\u0418').replace('\u0456', '\u0438')  # i
    message = message.replace('\u0407', '\u0418').replace('\u0457', '\u0438')  # i

    if conf_id == 0:
        answer = bot.interact('user {} {}'.format(uid, message))
    elif conf_id > 0:
        answer = bot.interact('conf {} {}'.format(uid, message))
    elif conf_id == -1:
        answer = bot.interact('flat {}'.format(message))
        bl = (answer == '$blacklisted')
        return bl

    if message == message.lower() and message != message.upper():
        answer = answer.lower()
    console_message = ''

    if '{' in answer:
        answer, gender = applyGender(answer, uid)
        console_message += ' (' + gender + ')'

    if answer.startswith('\\'):
        res = preprocessReply(answer[1:], uid)
        log.write('preprocess', '{}: {} ({} -> {})'.format(uid, answer, message, res))
        if res is None:
            log.error('Unknown reply:', answer)
            res = ''
        console_message += ' (' + answer + ')'
        answer = res

    if method:
        console_message += ' (' + method + ')'
    if conf_id > 0:
        print('({}) {} : {}{}'.format(banign.printableName(uid, user_fmt='Conf %c, {name}').replace('%c', str(conf_id)), message, answer, console_message))
    else:
        print('({}) {} : {}{}'.format(banign.printableName(uid), message, answer, console_message))
    return answer

def processCommand(cmd, *p):
    if cmd == 'reload':
        bot.interact('reld')
        vk.initSelf()
        print('Reloaded!')
        return 'Reloaded!'

    elif cmd == 'banned':
        if banign.banned:
            result = sorted(banign.banned)
            result = [banign.printableName(j, user_fmt='https://vk.com/id{id}') for j in result]
            return '\n'.join(result)
        else:
            return 'No one banned!'

    elif cmd == 'ignored':
        if banign.ignored:
            result = sorted(banign.ignored)
            result = [banign.printableName(j, user_fmt='https://vk.com/id{id}') for j in result]
            return '\n'.join(result)
        else:
            return 'No one ignored!'

    elif cmd == 'ban':
        if not p:
            return 'Not enough parameters'
        user = vk.getUserId(p[-1])
        if user is None:
            return 'No such user'
        if user == admin:
            return 'Cannot ban admin!'
        return banign.ban(user)

    elif cmd == 'unban':
        if not p:
            return 'Not enough parameters'
        user = p[-1]
        if user != '*':
            user = vk.getUserId(user)
        return banign.unban(user)

    elif cmd == 'ignore':
        if not p:
            return 'Not enough parameters'
        user = vk.getUserId(p[-1])
        if user is None:
            return 'No such user'
        if user == admin:
            return 'Cannot ignore admin!'
        return banign.ignore(user)

    elif cmd == 'unignore':
        if not p:
            return 'Not enough parameters'
        user = p[-1]
        if user != '*':
            user = vk.getUserId(user)
        return banign.unignore(user)

    elif cmd == 'leave':
        if not p:
            return 'Not enough parameters'
        if not p[-1].isdigit():
            return 'Invalid conf id'
        cid = int(p[-1])
        if vk.leaveConf(cid):
            return 'Ok'
        else:
            return 'Fail'

    elif cmd == 'noadd':
        if not p:
            return 'Not enough parameters'
        users = vk.getUserId(p)
        if not users:
            return 'No such users'
        if admin in users:
            return 'Cannot delete admin!'
        noaddUsers(users)
        return 'Noadd ' +  str(users)

    else:
        return 'Unknown command'


# returns (text, mode)
# mode=0: default, mode=1: no delay, mode=2: friendship request
def reply(message):
    if vk.getSender(message) in banign.banned:
        return None
    if vk.getSender(message) in banign.ignored or message['user_id'] in banign.ignored:
        return ('', 0)
    if vk.users[message['user_id']]['blacklisted'] or vk.users[message['user_id']]['blacklisted_by_me']:
        return ('', 0)

    if 'body' not in message:
        message['body'] = ''

    if 'id' not in message:  # friendship request
        return (getBotReply(message['user_id'], message['message'], 0), 2)
    message['body'] = preprocessMessage(message)

    if message['body']:
        if message['body'].startswith('\\') and len(message['body']) > 1:
            cmd = message['body'][1:].split()
            if cmd:
                if reset_command and cmd[0] == reset_command:
                    cmd = cmd[1:]
                    vk.sendMessage(admin, '{} from {}'.format(cmd, message['user_id']))
                    return (processCommand(*cmd), 1)
                elif message['user_id'] == admin:
                    return (processCommand(*cmd), 1)

        if isBotMessage(message['body']):
            print(message['body'], '- ignored (bot message)')
            return ('', 0)

        t = evalExpression(message['body'])
        if t:
            if getBotReply(None, message['body'], -1):
                return ('', 0)
            print(message['body'], '=', t, '(calculated)')
            log.write('calc', '"{}" = {}'.format(message['body'], t))
            return (t, 0)

    if message['body'] and message['body'].upper() == message['body'] and len([i for i in message['body'] if i.isalpha()]) > 1:
        print(message['body'], '- ignored (caps)')
        return ('', 0)

    return (getBotReply(message['user_id'], message['body'] , message.get('chat_id', 0), message.get('_method', '')), 0)


def preprocessMessage(message, user=None):
    if user is not None and message.get('user_id') != user:
        return None

    if 'action' in message:
        if message['action'] == 'chat_invite_user' and message['action_mid'] == vk.self_id:
            vk.deleteFriend(message['user_id'])
        return None

    result = message['body']
    att = []
    for a in message.get('attachments', []):
        if a['type'] == 'audio':
            att.append(a['audio']['title'])
        elif a['type'] == 'video':
            att.append(a['video']['title'])
        elif a['type'] == 'wall':
            att.append(a['wall']['text'])
        elif a['type'] == 'doc':
            att.append(a['doc']['title'])
        elif a['type'] == 'gift':
            att.append('vkgift')
        elif a['type'] == 'link':
            att.append(a['link']['description'])
    for a in att:
        result += ' [' + a.lower() + ']'

    for fwd in message.get('fwd_messages', []):
        if len(message['fwd_messages']) == 1 and fwd.get('user_id') == vk.self_id and result:
            continue
        r = preprocessMessage(fwd, message.get('user_id'))
        if r is None:
            return None
        result  += ' {' + str(r) + '}'

    if user is None and 'attachments' not in message and not result:
        return None
    return result.strip()


def preprocessReply(s, uid):
    if s == 'myname':
        return vk.users[uid]['first_name']
    if s == 'mylastname':
        return vk.users[uid]['last_name']
    if s == 'curtime':
        return time.strftime("%H:%M", time.localtime())
    if s.startswith('likeava'):
        vk.likeAva(uid)
        return s.split(maxsplit=1)[1]
    if s.startswith('gosp'):
        vk.setRelation(uid)
        return s.split(maxsplit=1)[1]
    if s == 'phone':
        return vk.phone


_male_re = re.compile(r'\{m([^\{\}]*)\}')
_female_re = re.compile(r'\{f([^\{\}]*)\}')

# 1: female, 2: male
def applyGender(msg, uid):
    gender = ['male', 'female', 'male'][vk.users[uid]['sex']]
    if gender == 'female':
        msg = _male_re.sub('', msg)
        msg = _female_re.sub('\\1', msg)
    else:
        msg = _female_re.sub('', msg)
        msg = _male_re.sub('\\1', msg)
    return msg, gender

def test_friend(uid):
    try:
        fr = vk.api.users.get(user_ids=uid, fields=check_friend.fields)[0]
    except KeyError:
        return 0
    return check_friend.is_good(fr)

def noaddUsers(users):
    users = set(users)
    users.discard(admin)
    if not users:
        return
    check_friend.noadd.update(map(str, users))
    vk.deleteFriend(users)
    check_friend.writeNoadd()


if sys.argv[-1] == '-l':
    vkapi.vk_api.logging = 1
    print('Logging enabled')

cfg = list(map(str.strip, open('data.txt').read().strip().splitlines()))
admin = int(cfg[2]) if len(cfg) > 2 else -1
reset_command = cfg[3] if len(cfg) > 3 else ''

vk = vk_bot(cfg[0], cfg[1], captcha_handler=captcha.solve) # login, pass
print('My id:', vk.self_id)

banign = ban_manager('banned.txt', vk.users)

addfriends_interval = config.get('inf.addfriends_interval')
includeread_interval = config.get('inf.includeread_interval')
setonline_interval = config.get('inf.setonline_interval')
unfollow_interval = config.get('inf.unfollow_interval')
filtercomments_interval = config.get('inf.filtercomments_interval')

reply_all = False
while 1:
    try:
        vk.replyAll(reply, reply_all)
        reply_all = False
        if timeto('addfriends', addfriends_interval):
            vk.addFriends(reply, test_friend)
        if timeto('includeread', includeread_interval):
            reply_all = True
        if timeto('setonline', setonline_interval):
            vk.setOnline()
        if timeto('unfollow', unfollow_interval):
            vk.unfollow(banign.banned)
        if timeto('filtercomments', filtercomments_interval):
            noaddUsers(vk.filterComments(lambda s:getBotReply(None, s, -1), banign.printableName))
    except Exception as e:
        log.error('global {}: {}'.format(e.__class__.__name__, str(e)), True)
        reply_all = True
        time.sleep(2)
