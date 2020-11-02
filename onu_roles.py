# -*- coding: utf-8 -*-
"""
Created on Wed Sep 21 14:41:37 2016

@author: Tsvika
"""
#TODO: docstrings!
#TODO: more roles! sentinal+revealer (add a what_you_see function; curator?; BONUS 1/2; ONUV
#TODO: FIX the werewolves/masons meeting. 
#      also: thumbs putting should be clear (minion, dream wolf, aura seer, ...)
#      also: make sure P-werewolves and D-witch/robber-werewolf does not wake up with the pack!!
#TODO: add a field for card quantity, and use it for valid_roles instead of the current method

from operator import attrgetter
from enum import Enum
from random import shuffle, choice
from copy import copy
from typing import Dict  #pylint: disable=unused-import
from collections import Counter


############################## Role types ##############################

# used for win-conditions logic & werewolf night action
class RoleType(Enum):
    villager = 1
    werewolf = 2
    minion = 3
    tanner = 4


############################## win conditions ##############################
KILL_STR = 'killed'
NOT_KILL_STR = 'alive_'
def village_win_cond(table, player, verbose=False):  #pylint: disable=unused-argument
    # Wins if at least one Werewolf dies (even if a player on the village team dies).
    # If no player is a Werewolf, only wins if no one (not even the Tanner or Minion) dies.
    if table.current_table_cards(RoleType.werewolf):
        if verbose:
            return '{}{}'.format(KILL_STR, table.current_table_cards(RoleType.werewolf))
        return table.killed_role(RoleType.werewolf)
    else:
        if verbose:
            return '{}{}'.format(
                NOT_KILL_STR,
                table.current_table_cards(RoleType.villager)
                + table.current_table_cards(RoleType.tanner)
                + table.current_table_cards(RoleType.minion))
        return not table.killed_anyone()

def werewolf_win_cond(table, player, verbose=False):  #pylint: disable=unused-argument
    # Wins if no werewolves die and (if the Tanner is in play) the Tanner is still alive.
    if verbose:
        return '{}{}'.format(
            NOT_KILL_STR,
            table.current_table_cards(RoleType.werewolf)
            + table.current_table_cards(RoleType.tanner))
    return not (table.killed_role(RoleType.werewolf) or table.killed_role(RoleType.tanner))
    # so they can kill a villager, a minion, or no-one

def minion_win_cond(table, player, verbose=False):
    # Wins with the werewolves even if he dies.
    # If no player is a werewolf, wins if any player dies as long as he does not die and the Tanner
    # is still alive.
    if table.current_table_cards(RoleType.werewolf):
        return werewolf_win_cond(table, player, verbose=verbose)
    else:
        # here he can kill another minion
        if verbose:
            return '{}{} & {}[anyone]'.format(
                NOT_KILL_STR, [player] + table.current_table_cards(RoleType.tanner), KILL_STR)
        return (table.killed_anyone()
                and not table.killed_player(player) and not table.killed_role(RoleType.tanner))

def tanner_win_cond(table, player, verbose=False):
    # Wins if he dies.
    if verbose:
        return '{}{}'.format(KILL_STR, [player])
    return table.killed_player(player)


############################## night actions help funcs ##############################

def format_selection(table, key):
    if key in table.center_cards_names:
        return 'the {}'.format(key)
    return '[{}: {}]'.format(key, table.players[key])

def send_msg(table, player, msg: str):
    table.narrator.private_msg([player], msg)

def choose_player(table, player, include=None, exclude=None, none=False, center=False,
                  exclude_center=None, direction=False):
    options_list = []
    if none:
        send_msg(table, player, "  0) none")
        options_list.append('0')
    if direction:
        send_msg(table, player, "  -) right")
        options_list.append('-')
        send_msg(table, player, "  +) left")
        options_list.append('+')
    # players
    all_players = table.all_players()
    if include is None:
        players_list = all_players
    else:
        for include_p in include:
            assert include_p in all_players
        players_list = include
    if exclude:
        for exclude_p in exclude:
            players_list.remove(exclude_p)
    for player2 in players_list:
        send_msg(table, player, "  {}) {}".format(player2, table.players[player2]))
    options_list.extend([str(p) for p in players_list])
    # center
    if center:
        if exclude_center is None:
            exclude_center = ''
        if 'L' not in exclude_center:
            send_msg(table, player, "  L) Left")
            options_list.append('L')
        if 'M' not in exclude_center:
            send_msg(table, player, "  M) Middle")
            options_list.append('M')
        if 'R' not in exclude_center:
            send_msg(table, player, "  R) Right")
            options_list.append('R')
        if 'ALPHA' in table.assigned_roles:
            if 'A' not in exclude_center:
                send_msg(table, player, "  A) Alpha")
                options_list.append('A')
    sel = table.narrator.get_input([player], options_list)
    center_dict = {'L':'LEFT', 'R':'RIGHT', 'M':'MIDDLE', 'A':'ALPHA'}
    if sel in ['0', '+', '-']:
        return sel
    elif sel in center_dict:
        return center_dict[sel]
    else:
        return int(sel)

def send_and_log(table, player, msg: str, prefix="You"):
    send_msg(table, player, prefix + msg)
    table.narrator.log(format_selection(table, player) + msg)

def view_selected_card(table, player, card):
    if card == '0':
        send_and_log(table, player, " view nothing.")
        return None
    elif card in table.center_cards_names:
        send_and_log(table, player,
                     " view the {} card. It is a {}.".format(card, table.current_roles[card].name))
        return table.current_roles[card]
    else:
        send_and_log(table, player, " view {} card. It is a {}.".format(
            format_selection(table, card), table.current_roles[card].name))
        return table.current_roles[card]

def switch_cards(table, player, card1, card2):
    table.switch_cards(card1, card2)
    send_and_log(table, player, " switched {} card with {} card.".format(
        format_selection(table, card1), format_selection(table, card2)))

def switch_cards_circle(table, player, cards_list):
    reversed_cards_list = list(reversed(cards_list))
    for i, c in enumerate(reversed_cards_list[:-1]):
        table.switch_cards(reversed_cards_list[i], reversed_cards_list[i+1])
    send_and_log(table, player, " switched {} cards.".format(' '.join(
        [format_selection(table, card) for card in cards_list])))

def infected(table, player, role_type):
    if role_type == RoleType.werewolf:
        send_and_log(table, player, " become a Werewolf.")
        table.assigned_roles[player].winning_condition = werewolf_win_cond
        table.assigned_roles[player].role_type = RoleType.werewolf
        table.assigned_roles[player].secret_identity = 'Werewolf'
    elif role_type == RoleType.tanner:
        send_and_log(table, player, " become a tanner.")
        table.assigned_roles[player].winning_condition = tanner_win_cond
        table.assigned_roles[player].role_type = RoleType.tanner
        table.assigned_roles[player].secret_identity = 'Tanner'
    else:
        raise AssertionError()

def doppel(table, player, role):
    send_and_log(table, player, " are now a {}".format(role.name))
    table.assigned_roles[player].winning_condition = role.winning_condition
    table.assigned_roles[player].role_type = role.role_type
    table.assigned_roles[player].order = (
        table.current_roles[player].order if role.doppel_immediately else role.order) + '+'
    table.assigned_roles[player].night_action = role.night_action
    table.assigned_roles[player].doppel_immediately = role.doppel_immediately
    table.assigned_roles[player].secret_identity = role.name

def see_your_card(table, player):
    send_msg(table, player, "You view your card. It is a {}.".format(
        table.current_roles[player].name))
    table.narrator.log("{} view his card. It is a {}.".format(
        format_selection(table, player), table.current_roles[player].name))

def do_nothing(table, player):
    send_and_log(table, player, " do nothing.")

def format_players_list(table, players_list):
    p_names = ['[{}: {}]'.format(p, table.players[p]) for p in players_list]
    return " ".join(p_names)


############################## night actions ##############################

def werewolf_night_action(table, player):
    werewolves = table.assigned_table_cards(RoleType.werewolf)
    if len(werewolves) > 1:
        werewolves = table.assigned_table_cards(RoleType.werewolf)
        send_msg(table, player, "You see the werewolves: " + format_players_list(table, werewolves))
    else:
        send_msg(table, player, "You don't see any other werewolves.")
        send_msg(table, player, "You may view one center card.")
        send_msg(table, player, "Choose the card:")
        sel = choose_player(table, player, include=[], exclude=None, none=True, center=True)
        view_selected_card(table, player, sel)

def minion_night_action(table, player):
    werewolves = table.assigned_table_cards(RoleType.werewolf)
    if len(werewolves) > 0:
        werewolves = table.assigned_table_cards(RoleType.werewolf)
        send_msg(table, player, "You see the werewolves: " + format_players_list(table, werewolves))
    else:
        send_msg(table, player, "You don't see any werewolves.")

def mason_night_action(table, player):
    masons = table.assigned_table_cards(['Mason'], include_secret_identity=True)
    if len(masons) > 1:
        send_msg(table, player, "You see the masons: " + format_players_list(table, masons))
    else:
        send_msg(table, player, "You don't see any other masons.")

def insomniac_night_action(table, player):
    see_your_card(table, player)

def alpha_wolf_night_action(table, player):
    werewolf_night_action(table, player)
    send_msg(table, player, "You must exchange the Center Werewolf card with any other "
             "non-werewolf player's card.")
    werewolves = table.assigned_table_cards(RoleType.werewolf)
    send_msg(table, player, "Choose the player:")
    sel = choose_player(table, player, exclude=werewolves)
    switch_cards(table, player, 'ALPHA', sel)

def mystic_wolf_night_action(table, player):
    werewolf_night_action(table, player)
    send_msg(table, player, "You may look at another player's card.")
    send_msg(table, player, "Choose the player:")
    sel = choose_player(table, player, exclude=[player], none=True)
    view_selected_card(table, player, sel)

def seer_night_action(table, player):
    send_msg(table, player, "You may look at another player's card or two of the center cards.")
    send_msg(table, player, "Choose the first card:")
    sel = choose_player(table, player, exclude=[player], none=True, center=True)
    view_selected_card(table, player, sel)
    if sel in table.center_cards_names:
        send_msg(table, player, "Choose the second card:")
        sel2 = choose_player(table, player, include=[], center=True, exclude_center=[sel])
        view_selected_card(table, player, sel2)

def appr_seer_night_action(table, player):
    send_msg(table, player, "You may look at one of the center cards.")
    send_msg(table, player, "Choose the card:")
    sel = choose_player(table, player, include=[], none=True, center=True)
    view_selected_card(table, player, sel)

def troublemaker_night_action(table, player):
    send_msg(table, player, "You may exchange cards between two other players.")
    send_msg(table, player, "Choose the first player:")
    sel = choose_player(table, player, exclude=[player], none=True)
    if sel == '0':
        do_nothing(table, player)
    else:
        send_msg(table, player, "Choose the second player:")
        sel2 = choose_player(table, player, exclude=[player, sel])
        switch_cards(table, player, sel, sel2)

def drunk_night_action(table, player):
    send_msg(table, player, "Exchange your card with a card from the center.")
    send_msg(table, player, "Choose the card:")
    card = choose_player(table, player, include=[], center=True)
    switch_cards(table, player, player, card)

def robber_night_action(table, player):
    send_msg(table, player, "You may exchange your card with another player's card, "
             "and then view your new card.")
    send_msg(table, player, "Choose the player:")
    card = choose_player(table, player, exclude=[player], none=True)
    if card == '0':
        do_nothing(table, player)
    else:
        switch_cards(table, player, player, card)
        see_your_card(table, player)

def pi_night_action(table, player):
    send_msg(table, player, "You may look at up to two cards of other players. "
             "If you see a Werewolf or a Tanner, you must stop, and you become a Werewolf or a "
             "Tanner.")
    send_msg(table, player, "Choose the first player:")
    sel1 = choose_player(table, player, exclude=[player], none=True)
    role1 = view_selected_card(table, player, sel1)
    if role1 is None:
        pass
    elif role1.secret_identity is None and role1.role_type in [RoleType.werewolf, RoleType.tanner]:
        infected(table, player, role1.role_type)
    else:
        send_msg(table, player, "Choose the second player:")
        sel2 = choose_player(table, player, exclude=[player, sel1], none=True)
        role2 = view_selected_card(table, player, sel2)
        if role2 and role2.role_type in [RoleType.werewolf, RoleType.tanner]:
            infected(table, player, role2.role_type)

def witch_night_action(table, player):
    send_msg(table, player, "You may look at one of the center cards. "
             "If you do, you must exchange that card with any player's card.")
    send_msg(table, player, "Choose the card:")
    sel1 = choose_player(table, player, include=[], none=True, center=True)
    role1 = view_selected_card(table, player, sel1)
    if role1 is None:
        pass
    else:
        send_msg(table, player, "Choose the player:")
        sel2 = choose_player(table, player)
        switch_cards(table, player, sel1, sel2)

def doppel_night_action(table, player):
    send_msg(table, player, "Look at another player's card. You are now that role.")
    send_msg(table, player, "Choose the player:")
    sel = choose_player(table, player, exclude=[player])
    role = view_selected_card(table, player, sel)
    doppel(table, player, role)
    doppel_immediately_roles = [
        role.name for role in table.assigned_roles.values()
        if (role.night_action is not None
            and role.doppel_immediately)
        ]
    table.narrator.public_msg("If your new role is {}, do it now.".format(
        ', '.join(doppel_immediately_roles)))
    if role.night_action is None:
        send_msg(table, player, "Your new role don't have a night action.")
        table.no_role()
    elif role.doppel_immediately:
        send_msg(table, player, "You do your night action immediately.")
        role.night_action(table, player)
    else:
        send_msg(table, player, "You will do your night action later.")
        table.no_role()

def idiot_night_action(table, player):
    send_msg(table, player, "You may move everyone's card but your own to the left or to the "
                            "right.")
    send_msg(table, player, "Choose the direction:")
    sel = choose_player(table, player, include=[], none=True, direction=True)
    if sel == '0':
        do_nothing(table, player)
    elif sel in ['+', '-']:
        cards_list = table.all_players()
        cards_list.remove(player)
        if sel == '-':
            cards_list = reversed(cards_list)
        switch_cards_circle(table, player, cards_list)
    else:
        raise AssertionError

def sentinel_night_action(table, player):
    send_msg(table, player, "You may place a shield token on any player's card but your own.")
    sel = choose_player(table, player, exclude=[player], none=True)
    if sel == '0':
        do_nothing(table, player)
    else:
        # place a token. don't forget to log. and to verify it's tokening
        send_and_log(table, player, " - nonimplemented action")

def revealer_night_action(table, player):
    send_msg(table, player, "You may flip over any other player's card. "
                            "If it's a Werewolf or the Tanner, flip it over face down.")
    sel = choose_player(table, player, exclude=[player], none=True)
    role = view_selected_card(table, player, sel)
    if role is None:
        pass
    else:
        if role.secret_identity is None and role.role_type in [RoleType.werewolf, RoleType.tanner]:
            # no need to flip
            send_and_log(table, player, " leave the card face down.")
        else:
            # flip it. don't forget to log. and to verify it's tokening
            send_and_log(table, player, " - nonimplemented action")


############################## Rules ##############################

class WerewolfRole(object):
    COLOR_CHARS = 'ansi'
    def __init__(self, name, desc, winning_condition, role_type,
                 order=None, night_action=None, time_factor=None,
                 doppel_immediately=True,
                 secret_identity=None):
        self.name = name
        self.desc = desc
        self.winning_condition = winning_condition
        self.role_type = role_type
        self.order = order
        self.night_action = night_action
        self.time_factor = time_factor
        self.doppel_immediately = doppel_immediately
        self.secret_identity = secret_identity

    def colored_name(self, add_secret_identity=False, compare=None, color_chars=None):
        if color_chars is None:
            color_chars = self.COLOR_CHARS
        if color_chars is '':
            colors = {'neutral': '', 'villager': '',
                      'tanner': '', 'werewolf': '',
                      'minion': '', 'clear': '',}
        elif color_chars == 'ansi':
            colors = {'neutral': '\x1b[30m', 'villager': '\x1b[34m',
                      'tanner': '\x1b[32m', 'werewolf': '\x1b[31m',
                      'minion': '\x1b[33m', 'clear': '\x1b[0m',}
        elif color_chars == 'irc':
            colors = {'neutral': '\x0301', 'villager': '\x0302',
                      'tanner': '\x0303', 'werewolf': '\x0304',
                      'minion': '\x0307', 'clear': '\x03',}
        colors_len = len(colors['neutral'])
        if add_secret_identity and self.secret_identity:
            identity = self.name[:1] + '-' + self.secret_identity
        else:
            identity = self.name
        if self.name in ["P.I.", "Doppelganger"] and not add_secret_identity:
            identity = colors['neutral'] + identity + colors['clear']
        elif self.role_type == RoleType.villager:
            identity = colors['villager'] + identity + colors['clear']
        elif self.role_type == RoleType.tanner:
            identity = colors['tanner'] + identity + colors['clear']
        elif self.role_type == RoleType.werewolf:
            identity = colors['werewolf'] + identity + colors['clear']
        elif self.role_type == RoleType.minion:
            identity = colors['minion'] + identity + colors['clear']
        if compare and (identity[colors_len:] == compare[colors_len:]):
            identity = identity[:colors_len] + '=' + colors['clear']
        return identity


onu_roles = dict()  # type: Dict[str, WerewolfRole]
onu_roles['doppelganger'] = WerewolfRole(
    name='Doppelganger',
    desc="Looks at another player's card and becomes that role.",
    winning_condition=village_win_cond,  # can be changed
    role_type=RoleType.villager,  # can be changed
    order='01',
    night_action=doppel_night_action,
    time_factor=2,
    secret_identity=None,
    )
onu_roles['werewolf'] = WerewolfRole(
    name='Werewolf',
    desc="Wakes with the werewolves. If only 1 werewolf wakes up, he may look at a center card.",
    winning_condition=werewolf_win_cond,
    role_type=RoleType.werewolf,
    order='02',
    night_action=werewolf_night_action,
    time_factor=1,
    doppel_immediately=False,    # TODO: review all doppel-special-werewolves order & wakeup function
    )
onu_roles['minion'] = WerewolfRole(
    name='Minion',
    desc="Werewolves put out their thumbs for the minion so he can see who they are.",
    winning_condition=minion_win_cond,
    role_type=RoleType.minion,
    order='03',
    night_action=minion_night_action,
    time_factor=0,
    )
onu_roles['mason'] = WerewolfRole(
    name='Mason',
    desc="Wakes with the other Masons.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='04',
    night_action=mason_night_action,
    time_factor=0,
    doppel_immediately=False,
    )
onu_roles['seer'] = WerewolfRole(
    name='Seer',
    desc="May look at one other player's card or two center cards.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='05',
    night_action=seer_night_action,
    time_factor=1.5,
    )
onu_roles['robber'] = WerewolfRole(
    name='Robber',
    desc="May rob another player's card and replace it with the Robber card, "
         "than looks at his new card.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='06',
    night_action=robber_night_action,
    time_factor=1,
    )
onu_roles['troublemaker'] = WerewolfRole(
    name='Troublemaker',
    desc="May switch the cards of two other players without looking at those cards.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='07',
    night_action=troublemaker_night_action,
    time_factor=2,
    )
onu_roles['drunk'] = WerewolfRole(
    name='Drunk',
    desc="Must exchange his Drunk card for a center card without looking at his new card.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='08',
    night_action=drunk_night_action,
    time_factor=1,
    )
onu_roles['insomniac'] = WerewolfRole(
    name='Insomniac',
    desc="Looks at her own card to see if it has been changed",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='09',
    night_action=insomniac_night_action,
    time_factor=0,
    doppel_immediately=False,
    )
### NO-WAKE ROLES ###
onu_roles['hunter'] = WerewolfRole(
    name='Hunter',
    desc="If he dies, the player that he is pointing to also dies.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    )
onu_roles['tanner'] = WerewolfRole(
    name='Tanner',
    desc="Only wins if he dies.",
    winning_condition=tanner_win_cond,
    role_type=RoleType.tanner,
    )
onu_roles['villager'] = WerewolfRole(
    name='Villager',
    desc="No special power",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    )
### ONUW
#onu_roles['sentinel'] = WerewolfRole(
#    name='Sentinel',
#    desc="Put a shield token on any other player's card. "
#         "A shield prevents a card from being moved or viewed by anyone.",  #TODO: prevents selection or self usage (ie drunk, idiot)
#    winning_condition=village_win_cond,
#    role_type=RoleType.villager,
#    order='00',
#    night_action=sentinel_night_action,
#    time_factor=1,
#    )
onu_roles['alpha_wolf'] = WerewolfRole(
    name='Alpha Wolf',
    desc="Wakes with the Werewolves. "
         "Must exchange the center Werewolf card with another non-Werewolf player's card.",
    winning_condition=werewolf_win_cond,
    role_type=RoleType.werewolf,
    order='02B',
    night_action=alpha_wolf_night_action,
    time_factor=1,
    )
onu_roles['mystic_wolf'] = WerewolfRole(
    name='Mystic Wolf',
    desc="Wakes with the Werewolves. May look at one other player's card.",
    winning_condition=werewolf_win_cond,
    role_type=RoleType.werewolf,
    order='02C',
    night_action=mystic_wolf_night_action,
    time_factor=1,
    )
onu_roles['appr_seer'] = WerewolfRole(
    name='Apprentice Seer',
    desc="May look at one of the center cards.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='05B',
    night_action=appr_seer_night_action,
    time_factor=1,
    )
onu_roles['pi'] = WerewolfRole(
    name='P.I.',
    desc="May look at up to two other player's cards. "
         "If he sees a Tanner or a Werewolf, he becomes what he sees and must stop looking.",
    winning_condition=village_win_cond,  # can be changed
    role_type=RoleType.villager,  # can be changed
    order='05C',
    night_action=pi_night_action,
    secret_identity=None,
    time_factor=1.5,
    )
onu_roles['witch'] = WerewolfRole(
    name='Witch',
    desc="May look at a center card. "
         "If she does, she must exchange that card with any player's card (including her own).",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='06B',
    night_action=witch_night_action,
    time_factor=2,
    )
onu_roles['idiot'] = WerewolfRole(
    name='Village Idiot',
    desc="May move all players' cards except his own 1 space to the left or to the right.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    order='07B',
    night_action=idiot_night_action,
    time_factor=1,
    )
#onu_roles['revealer'] = WerewolfRole(
#    name='Revealer',
#    desc="May turn one other player's card face up, "
#         "but if he sees a Tanner or a Werewolf he must turn it back over face down.",
#    winning_condition=village_win_cond,
#    role_type=RoleType.villager,
#    order='10',
#    night_action=revealer_night_action,
#    doppel_immediately=False,
#    time_factor=1,
#    )
#onu_roles['curator'] = WerewolfRole(
#    name='Curator',
#    desc="May give any player (including himself) an Artifact token",
#    winning_condition=village_win_cond,
#    role_type=RoleType.villager,
#    order='11',
#    night_action=curator_night_action,
#    doppel_immediately=False,
#    )
### NO-WAKE ROLES ###
onu_roles['dream_wolf'] = WerewolfRole(
    name='Dream Wolf',
    desc="Does NOT wake up with the other werewolves, but instead sticks out his thumb.",
    winning_condition=werewolf_win_cond,
    role_type=RoleType.werewolf,
    )
onu_roles['bodyguard'] = WerewolfRole(
    name='Bodyguard',
    desc="Does not wake up at night. When voting, the player the Bodyguard points at cannot die."
         "Recommended for five or more players.",
    winning_condition=village_win_cond,
    role_type=RoleType.villager,
    )
### token roles ###
onu_roles['wolf_token'] = WerewolfRole(
    name='Werewolf',
    desc="The Alpha Wolf exchange this card with another player card.",
    winning_condition=werewolf_win_cond,
    role_type=RoleType.werewolf,
    )
### Bonus pack 1 ###
    # aura seer  # late doppel
    # prince  <
    # cursed
### Bonus pack 2 ###
    # appr. tanner  # late doppel
    # thing  <
    # squire  <  # late doppel
    # beholder  <  # late doppel
### ONUV & ONUA ###
    # copycat
    # mortician

onu_night_roles = sorted([r for r in onu_roles.values() if r.order is not None],
                         key=attrgetter('order'))

ONU_ROLES = list(onu_roles.keys()) + ['villager'] * 2 + ['werewolf']
ONU_ROLES.remove('wolf_token')
#also the 'mason' should come in pair

def get_random_roles(num_players, include=None, exclude=None, *,
                     min_werewolf=0, min_village=0, min_other=0,
                     max_werewolf=None, max_village=None, max_other=None):
    # definitions
    werewolves_r = [r for r in ONU_ROLES
                    if onu_roles[r].role_type in [RoleType.werewolf, RoleType.minion]]
    other_r = ['tanner', 'doppelganger', 'pi', 'idiot', 'curator']
    # this show the roles that are not excluded and not used already
    available_roles = copy(ONU_ROLES)
    if exclude:
        for role in exclude:
            available_roles.remove(role)
            while role in available_roles:
                available_roles.remove(role)
    # in this case, just select 1
    if num_players == 0:
        return [choice(available_roles)]
    # input checking, to prevent infinite loops
    if not all([max_werewolf is None or min_werewolf <= max_werewolf,
                max_village is None or min_village <= max_village,
                max_other is None or min_other <= max_other]):
        raise ValueError("min > max")
    if not (max_werewolf is None or max_village is None or max_other is None
            or max_werewolf + max_village + max_other >= num_players + 3):
        raise ValueError("total max < number of cards")
    if not min_werewolf + min_village + min_other <= num_players + 3:
        raise ValueError("total min > number of cards")
    if not all([min_werewolf <= len(werewolves_r),
                min_village <= len(available_roles) - len(werewolves_r) - len(other_r),
                min_other <= len(other_r)]):
        raise ValueError("min > available roles")

    # counters of role types
    n_werewolf, n_village, n_other = 0, 0, 0
    def add_role(role):
        nonlocal n_werewolf, n_village, n_other, available_roles, roles
        assert role in ONU_ROLES
        available_roles.remove(role)
        if role in werewolves_r:
            if max_werewolf is None or n_werewolf < max_werewolf:
                n_werewolf += 1
                roles.append(role)
        elif role in other_r:
            if max_other is None or n_other < max_other:
                n_other += 1
                roles.append(role)
        elif role == 'mason':
            if max_village is None or n_village + 1 < max_village:
                n_village += 2
                roles.append(role)
                roles.append(role)
        else:
            if max_village is None or n_village < max_village:
                n_village += 1
                roles.append(role)
    # create the roles list
    roles = []
    # 1. add the roles from include.
    if include:
        # if there are more roles in include than cards, just randommly select a subset
        shuffle(include)
        for role in include:
            add_role(role)
    # 2. add roles of each type, up to the min required, from non-exclude
    while n_werewolf < min_werewolf:
        role = choice([r for r in available_roles if r in werewolves_r])
        add_role(role)
    while n_village < min_village:
        role = choice([r for r in available_roles
                       if r in available_roles and r not in werewolves_r + other_r])
        add_role(role)
    while n_other < min_other:
        role = choice([r for r in available_roles if r in other_r])
        add_role(role)
    # 3. add more, up to the required number.
    while len(roles) < num_players + 3:
        role = choice(available_roles)
        add_role(role)
        # remove mason if it's too much
        if len(roles) > num_players + 3:
            assert len(roles) == num_players + 3 + 1
            assert roles[-2:] == ['mason', 'mason']
            roles = roles[:-2]
    assert len(roles) == num_players + 3
    return sorted(roles)

def get_random_roles2(num_players, include=None, exclude=('villager',),
                      min_werewolf=2, min_village=2, min_other=0,
                      max_werewolf=3, max_village=None, max_other=1):
    return get_random_roles(num_players, include, exclude,
                            min_werewolf=min_werewolf, min_village=min_village, min_other=min_other,
                            max_werewolf=max_werewolf, max_village=max_village, max_other=max_other)

def get_beginner_roles(num_players):
    if num_players < 3:
        raise ValueError("not enough players")
    if num_players == 3:
        return 'alpha_wolf mystic_wolf appr_seer witch troublemaker revealer'.split()
    if num_players <= 5:
        return 'werewolf werewolf seer robber troublemaker tanner villager villager'.split()[:num_players + 3]
    if num_players <= 9:
        return 'werewolf werewolf seer robber troublemaker tanner villager drunk minion villager hunter villager'.split()[:num_players + 3]
    if num_players == 10:
        return 'werewolf werewolf seer robber troublemaker tanner villager drunk minion villager hunter mason mason'.split()
    raise ValueError("too many players")

def verify_roles(roles, num_players, ignore_count=True):
    if num_players and len(roles) != num_players + 3:
        raise ValueError("incorrect number of roles")
    for role in roles:
        if role not in onu_roles:
            raise ValueError("unsupported role: {}".format(role))
    if ignore_count:
        return
    count_roles = Counter(roles)
    for role, count in count_roles.items():
        if role == 'mason':
            if count == 1:
                raise ValueError("masons should be in a pair")
            # max. amount of cards
        if role in ['mason', 'werewolf']:
            if count > 2:
                raise ValueError("too many {}".format(role))
        elif role == 'villager':
            if count_roles[role] > 3:
                raise ValueError("too many {}".format(role))
        else:
            if count > 1:
                raise ValueError("too many {}".format(role))


if __name__ == "__main__":
    print(get_random_roles2(5))
