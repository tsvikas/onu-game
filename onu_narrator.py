# -*- coding: utf-8 -*-
"""
Created on Wed Sep 21 01:16:02 2016

@author: Tsvika
"""
#TODO: docstrings!
#TODO: rename to game_narrator!
#TODO: other modes to control/narrate - forums? emails? ...?
#TODO: other modes to control/narrate - telegram bot!!!
#TODO: improve logs: log to a (per game) file + log enough to recover game. don't log to screen?
#TODO: VOTE NOW! option in public_chat()

from random import choice
from time import time, sleep

############################## abstract narrator ##############################

class Player(object):
    def __init__(self, name):
        self.name = name
    def send_msg(self, msg: str):
        raise NotImplementedError

class Narrator(object):
    def __init__(self, players: Player, base_timeout):
        self.players = {i+1: p for (i, p) in enumerate(players)}
        self.base_timeout = base_timeout
        self.log_history = []
    def log(self, msg):
        self.log_history.append(msg)
    def private_msg(self, players_n, msg: str):
        for i in players_n:
            self.players[i].send_msg(msg)
    def public_msg(self, msg: str):
        raise NotImplementedError
    def public_chat(self, minutes):
        raise NotImplementedError
    def get_input(self, players_n, options_set, timeout):
        raise NotImplementedError
    def get_votes(self, timeout):
        raise NotImplementedError


############################## print narrator ##############################

class DebugPlayer(Player):
    def __init__(self, name, print_f=print):
        if not print_f:
            print_f = lambda x: None
        self.print_f = print_f
        super(DebugPlayer, self).__init__(name)
    def send_msg(self, msg: str):
        for line in '@{:10}:   {}'.format(self.name, msg).split('\n'):
            self.print_f(line)

class DebugNarrator(Narrator):
    PUBLIC_ROOM = 'PUB'
    def __init__(self, players, base_timeout=0, print_f=print):
        if print_f is None:
            print_f = lambda x: None
        self.print_f = print_f
        super(DebugNarrator, self).__init__(
            players=players,
            base_timeout=base_timeout)
    def public_msg(self, msg):
        for line in '#{:10}: {}'.format(self.PUBLIC_ROOM, msg).split('\n'):
            self.print_f(line)
    def public_chat(self, minutes):
        self.print_f('.'*int(minutes))
    def get_input(self, players_n, options_set, timeout=None):
        rand = True
        if rand:
            return choice(options_set)
        sel = None
        while sel not in options_set:
            sel = input('?' + '+'.join([self.players[i].name for i in players_n]) + ':\t')
        return sel
    def get_votes(self, timeout=None):
        votes = dict()
        for i in self.players:
            votes[i] = int(self.get_input(
                [i],
                [str(j) for j in self.players if j != i],
                timeout=timeout))
        return votes
    def log(self, msg):
        for line in '@{:10}:   {}'.format('log', msg).split('\n'):
            self.print_f(line)
        super(DebugNarrator, self).log(msg)


############################## sopel narrator ##############################

class SopelPlayer(Player):
    def __init__(self, bot, name):
        self.bot = bot
        super(SopelPlayer, self).__init__(name)
        if not bot.memory.contains('pending_reply'):
            bot.memory['pending_reply'] = dict()
        bot.memory['pending_reply'][self.name] = None
    def send_msg(self, msg):
        for line in msg.split('\n'):
            self.bot.say(line, self.name)
    def get_input(self, options_set, timeout):
        self.request_input()
        return self.recieve_input(options_set, timeout)
    def request_input(self):
        if self.bot.memory['pending_reply'][self.name] is not None:
            raise RuntimeError("can't get input before previous input arrived")
        self.bot.memory['pending_reply'][self.name] = ''
    def recieve_input(self, options_set, timeout):
        try:
            bot = self.bot
            end_time = time() + timeout
            sel = None
            while time() <= end_time:
                sel = bot.memory['pending_reply'][self.name]
                if sel != '':
                    if sel in options_set:
                        break
                    elif sel.upper() in options_set:
                        sel = sel.upper()
                        break
                    else:
                        bot.say('not a valid option, please respond again', self.name)
                        bot.memory['pending_reply'][self.name] = ''
                else:
                    sleep(timeout / 30)
            # choose in random
            if sel not in options_set:
                bot.say("time's up. random choice...", self.name)
                sel = choice(options_set)
            return sel
        finally:
            bot.memory['pending_reply'][self.name] = None


class SopelNarrator(Narrator):
    def __init__(self, bot, players, room_name, base_timeout, vote_timeout):
        self.bot = bot
        self.room_name = room_name
        self.bot.join(self.room_name)
        self.vote_timeout = vote_timeout
        super(SopelNarrator, self).__init__(players=players, base_timeout=base_timeout)
    def public_msg(self, msg):
        for line in msg.split('\n'):
            self.bot.say(line, self.room_name)
    def public_chat(self, minutes):
        sleep(60*minutes)
    def get_input(self, players_n, options_set, timeout=None):
        if timeout is None:
            timeout = self.base_timeout
        if len(players_n) == 1:  #TODO: maybe transfer this case to SopelPlayer?
            return self.players[players_n[0]].get_input(options_set, timeout)
        else:     #TODO: how does we ask many players for input?
            raise NotImplementedError
    def get_votes(self, timeout=None):
        try:
            self.bot.memory['onu'][self.room_name]['voting'] = True
            # make the channel +m
            self.bot.write(['MODE', self.room_name, '+m'])
            # tell everyone
            for player in self.players:
                self.players[player].send_msg('~~~ voting ~~~')
                self.players[player].send_msg('players list:')
            # print players list
            for player in self.players:
                for player2 in self.players:
                    if player2 != player:
                        self.players[player].send_msg("  {}) {}".format(
                            player2, self.players[player2].name))
            for player in self.players:
                self.players[player].send_msg('use .vote [player_number] to make a vote')
                self.players[player].send_msg('you have {} seconds'.format(self.vote_timeout))
            # while incomplete and time < end_time: get current votes from memory.
            end_time = time() + self.vote_timeout
            votes = dict()
            player_names = {v.name: k for k, v in self.players.items()}
            while (self.bot.memory['onu'][self.room_name]['votes']
                   or (time() <= end_time and votes.keys() != self.players.keys())):
                mem_votes = self.bot.memory['onu'][self.room_name]['votes'].copy()
                for player_name, vote_str in mem_votes.items():
                    self.bot.memory['onu'][self.room_name]['votes'].pop(player_name)
                    player = player_names[player_name]
                    try:
                        vote_i = int(vote_str)
                    except ValueError:
                        self.players[player].send_msg('this is not a number')
                    else:
                        if vote_i == player:
                            self.players[player].send_msg("can't vote to yourself")
                        elif vote_i not in self.players.keys():
                            self.players[player].send_msg("this is not a player's number")
                        else:
                            votes[player] = vote_i
                            self.players[player].send_msg("you voted to [{}: {}]".format(
                                vote_i, self.players[vote_i].name))
                sleep(0.5)
        finally:
            self.bot.memory['onu'][self.room_name]['voting'] = False
            # make the channel -m
            self.bot.write(['MODE', self.room_name, '-m'])
        for player in self.players:
            if player not in votes:
                self.public_msg("{} didn't vote, randomizing".format(self.players[player].name))
                opt = list(self.players.keys())
                opt.remove(player)
                votes[player] = choice(opt)
        return votes

    def log(self, msg):
        print(msg)
        super(SopelNarrator, self).log(msg)


############################## testing ##############################

def get_debug_narrator(players_n=3, players_print=None, narrator_print=print):
    player_names = ('Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India '
                    'Juliett Kilo Lima Mike November Oscar Papa Quebec Romeo'
                    'Sierra Tango Uniform Victor Whiskey X-ray Yankee Zulu'
                   ).split(' ')[:players_n]
    players = [DebugPlayer(p, print_f=players_print) for p in player_names]
    return DebugNarrator(players, print_f=narrator_print)

if __name__ is '__main__':
    nar = get_debug_narrator()
    nar.log('logging')
    nar.private_msg([1], 'hi alice')
    nar.private_msg([1, 2], 'hi alice & bob')
    nar.public_msg('hi all')
    nar.public_chat(minutes=5)
#    nar.get_input([1], ['a','b'], 'ask alice')
#    nar.get_input([1,2], ['a','b'], 'ask alice & bob')
    print(nar.get_votes())
