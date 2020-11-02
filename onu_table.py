# -*- coding: utf-8 -*-
"""
Created on Wed Sep 21 20:23:50 2016

@author: Tsvika
"""
#TODO: docstrings!
#TODO: debug with other users
#TODO: write testcases?

from random import shuffle
from collections import OrderedDict, Counter
from copy import copy
from contextlib import contextmanager
import time
from tabulate import tabulate
from onu_game.onu_roles import onu_roles, onu_night_roles, RoleType, get_random_roles, verify_roles
from onu_game.onu_roles import WerewolfRole  #pylint: disable=unused-import
from onu_game.onu_narrator import Narrator  #pylint: disable=unused-import


class ONUTable(object):
    ### sorting the board ###
    def __init__(self, narrator: Narrator, roles):
        # does not verify narrator
        self.narrator = narrator
        self.players = {i: player.name for i, player in narrator.players.items()}
        # verify roles
        verify_roles(roles, len(self.players))
        # announce game
        start_t = int(time.time())
        self.narrator.public_msg('[{}] new game'.format(start_t))
        self.narrator.private_msg(self.players.keys(), '[{}] new game'.format(start_t))
        self.narrator.log('[{}] new game'.format(start_t))
        self.narrator.public_msg('Players: ' + ' '.join(
            ['[{}: {}]'.format(i, v) for i, v in self.players.items()]))
        self.narrator.public_msg('Roles: ' + ' '.join(
            sorted(["'{}'".format(onu_roles[r].colored_name()) for r in roles])))
        # shuffle roles
        shuffled_roles = list(roles)
        shuffle(shuffled_roles)
        # assign roles
        self.assigned_roles = OrderedDict()  # type: Dict[Union[int, str], WerewolfRole]
        center_cards_names = ['LEFT', 'MIDDLE', 'RIGHT']
        for i, role in zip(list(self.players) + center_cards_names, shuffled_roles):
            self.assigned_roles[i] = copy(onu_roles[role])
            if isinstance(i, int):
                self.narrator.private_msg([i], 'your role is ' + self.assigned_roles[i].name)
            else:
                pass  #self.narrator.log('{} card is {}'.format(i, self.assigned_roles[i].name))
        if 'Alpha Wolf' in [r.name for (p, r) in self.assigned_roles.items()]:
            self.assigned_roles['ALPHA'] = copy(onu_roles['wolf_token'])
            center_cards_names.append('ALPHA')
        # log assigned roles
        self.narrator.log(' '.join(
            ["[{num}: {name}]={role}".format(
                num=i, name=player, role=self.assigned_roles[i].name)
             for i, player in self.players.items()] +
            ["[{card}]={role}".format(
                card=card, role=self.assigned_roles[card].name)
             for card in self.center_cards_names]))
        # create a working copy
        self.current_roles = OrderedDict()  # type: Dict[Union[int, str], WerewolfRole]
        for i, role in self.assigned_roles.items():
            self.current_roles[i] = role

    @property
    def center_cards_names(self):
        return [k for k in self.assigned_roles.keys() if not isinstance(k, int)]

    ### night actions ###
    def no_role(self):
        self.narrator.log("Zzz...")

    @contextmanager
    def narrator_role(self, role_name, time_factor):
        base_timeout = self.narrator.base_timeout
        timeout = base_timeout * time_factor   #TODO: change time factor to max ?
        self.narrator.public_msg("{}, wake up.".format(role_name))
        end_time = time.time() + timeout
        yield
        time.sleep(max(0, end_time - time.time()))
        self.narrator.public_msg("{}, close your eyes.".format(role_name))

    def night_actions(self):
        self.narrator.public_msg("~~~ Night ~~~")
        self.narrator.public_msg("Everyone, close your eyes.")
        for role in onu_night_roles:
            if role.name in [r.name for r in self.assigned_roles.values()]:
                # regular action
                with self.narrator_role(role.name, time_factor=role.time_factor):
                    for player in self.assigned_table_cards([role.name]):
                        role.night_action(self, player)
                    if not self.assigned_table_cards([role.name]):
                        self.no_role()
                # doppel action
                if (('Doppelganger' in [r.name for r in self.assigned_roles.values()])
                        and not role.doppel_immediately):
                    with self.narrator_role("Doppel-" + role.name, time_factor=role.time_factor):
                        did_action = False
                        for player in self.assigned_table_cards(['Doppelganger']):
                            if self.assigned_roles[player].secret_identity == role.name:
                                did_action = True
                                role.night_action(self, player)
                        if not did_action:
                            self.no_role()


    def switch_cards(self, player1, player2):
        self.current_roles[player1], self.current_roles[player2] = (
            self.current_roles[player2], self.current_roles[player1])

    ### day time - chat & votes ###
    def daytime(self, minutes=5):
        self.narrator.public_msg("~~~ Day ~~~")
        self.narrator.public_msg("Everyone, Wake up!")
        if minutes > 1:
            self.narrator.public_msg("You have {} minutes to discuss.".format(minutes))
            self.narrator.public_chat(minutes=minutes-1)
            self.narrator.public_msg("One minute remaining!")
            self.narrator.public_chat(minutes=0.5)
            self.narrator.public_msg("Only 30 seconds left!")
            self.narrator.public_chat(minutes=0.5)
        else:
            self.narrator.public_msg("You have {} seconds to discuss.".format(minutes*60))
            self.narrator.public_chat(minutes=minutes)
        self.narrator.public_msg("Time is up! Everyone, 3...2...1... VOTE!")
        #TODO: print special voting roles?
        self.votes = self.narrator.get_votes()
        # verify votes
        num_players = len(self.players)
        assert len(self.votes) == num_players
        for i, vote in self.votes.items():
            assert 1 <= vote <= num_players
            assert vote != i
        # log
        self.narrator.log(' '.join(
            ["[{}]->[{}]".format(i, vote) for i, vote in self.votes.items()]))

    def summarize(self):
        # print
        data = []
        for i in self.assigned_roles:
            # stylize identitys
            id1 = self.assigned_roles[i].colored_name()
            id2 = self.current_roles[i].colored_name(add_secret_identity=True, compare=id1)
            if isinstance(i, int):
                # styleize vote
                vote = self.votes[i]
                if (self.current_roles[i].secret_identity or self.current_roles[i].name) == 'Bodyguard':
                    vote = '|{}|'.format(vote)
                # add to table
                data.append(
                    ['{}) {}'.format(i, self.players[i]),
                     id1, id2, vote,
                     'x' if i in self.killed_players else '',
                     self.current_roles[i].winning_condition(self, i, verbose=True),
                     '*' if self.current_roles[i].winning_condition(self, i) else ''])
            else:
                data.append([i, id1, id2] + [None]*4)
        self.narrator.public_msg('\n' + tabulate(
            data, headers=['player', 'was', 'now', 'vote', 'K', 'cond', 'W']))
        self.narrator.public_msg('')
        if self.killed_players:
            self.narrator.public_msg("Killed: " + ' '.join(
                ['[{}: {}]'.format(p, self.players[p]) for p in self.killed_players]))
        else:
            self.narrator.public_msg("Killed: NO-ONE")
        if self.winners:
            self.narrator.public_msg("Won:    " + ' '.join(
                ['[{}: {}]'.format(p, self.players[p]) for p in self.winners]))
        else:
            self.narrator.public_msg("Won:    NO-ONE")

    ### analyze votes to find who died ###
    def end_game(self, ignore_circle_tanner=False):
        reg_votes = []
        bodyguard_votes = []
        hunter_votes = []
        tanner_votes = []
        for i, vote in self.votes.items():
            if (self.current_roles[i].name == 'Bodyguard'
                    or self.current_roles[i].secret_identity == 'Bodyguard'):
                bodyguard_votes.append(vote)
            elif (self.current_roles[i].name == 'Hunter'
                  or self.current_roles[i].secret_identity == 'Hunter'):
                reg_votes.append(vote)
                hunter_votes.append((i, vote))
            elif ((self.current_roles[i].name == 'Tanner'
                   or self.current_roles[i].secret_identity == 'Tanner')
                  and ignore_circle_tanner
                  and not self.current_table_cards(RoleType.minion)
                  and not (self.current_table_cards(RoleType.werewolf)
                           and self.current_table_cards(RoleType.villager))):
                tanner_votes.append(vote)
            else:
                reg_votes.append(vote)
        self.killed_players = self.get_killed_players(
            reg_votes, bodyguard_votes, hunter_votes, tanner_votes, self.narrator.log)
        self.winners = []
        for i in self.votes.keys():  # so we only go over players
            if self.current_roles[i].winning_condition(self, i):
                self.winners.append(i)
        self.narrator.log("Won: {}".format(self.winners))
        # tell
        self.summarize()


    @staticmethod
    def get_killed_players(reg_votes, bodyguard_votes, hunter_votes, tanner_votes, log):
        # hunter_votes is a list of (hunter_player, hunter_target) tuples
        # reg_votes include the hunter targets
        epic_battle = False
        if epic_battle:
            raise NotImplementedError
        else:
            if Counter(reg_votes).most_common()[0][1] <= 1:
                log("everybody got <= 1 votes, no-one killed")
                return []  # no one is killed
            votes = Counter(reg_votes + tanner_votes)
            # intial log
            votes1 = votes.most_common()
            almost_killed_players = [player for (player, count) in votes1 if count == votes1[0][1]]
            if bodyguard_votes:
                log("players {} got {} votes each".format(almost_killed_players, votes1[0][1]))
            # change bodyguarded player(s) to -1
            for protected_player in bodyguard_votes:
                votes[protected_player] = -1
            if bodyguard_votes:
                log("players {} are protected".format(bodyguard_votes))
            # re-sort
            votes2 = votes.most_common()
            if votes2[0][1] <= 1:  # can occur with protected player
                log("everybody else got <= 1 votes, no-one killed")
                return []
            killed_players = [player for (player, count) in votes2 if count == votes2[0][1]]
            log("killing players {}, with {} votes each".format(killed_players, votes2[0][1]))
            # if hunter(s) in the list, add their targets (unless the target is -1)
            for hunter_player, hunter_target in hunter_votes:
                if hunter_player in killed_players and hunter_target not in killed_players:
                    if votes[hunter_target] != -1:
                        log("hunter player {} kills {} with him".format(
                            hunter_player, hunter_target))
                        killed_players.append(hunter_target)
                    else:
                        log("hunter player {} cannot kill {} with him".format(
                            hunter_player, hunter_target))
            return sorted(killed_players)


    ### analyze win conditions ###
    def killed_player(self, player):
        return player in self.killed_players
    def all_players(self):
        return [p for p in self.current_roles.keys() if isinstance(p, int)]
    def current_table_cards(self, role_type: RoleType):
        return [p for (p, r) in self.current_roles.items()
                if r.role_type == role_type and isinstance(p, int)]
    def assigned_table_cards(self, role_type_or_list, include_secret_identity=False):
        if isinstance(role_type_or_list, RoleType):
            return [p for (p, r) in self.assigned_roles.items()
                    if r.role_type == role_type_or_list and isinstance(p, int)]
        else:
            return [p for (p, r) in self.assigned_roles.items()
                    if ((r.name in role_type_or_list
                         or (include_secret_identity and r.secret_identity in role_type_or_list))
                        and isinstance(p, int))]
    def killed_anyone(self):
        return len(self.killed_players) > 0
    def killed_role(self, role_type: RoleType):
        return any([True for player in self.killed_players
                    if self.current_roles[player].role_type == role_type])



def get_debug_table(num_players, must_include=None):
    narrator = get_debug_narrator(num_players)
    roles = get_random_roles(num_players, must_include)
    return ONUTable(narrator, roles)


if __name__ == "__main__":
    from onu_game.onu_narrator import get_debug_narrator
    table = get_debug_table(12, must_include=['doppelganger'])
    table.night_actions()
    table.daytime()
    table.end_game()
