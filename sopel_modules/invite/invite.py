# coding=utf-8
"""
invite.py - Invite all the things
Copyright 2016 Max Gurela

Licensed under the Eiffel Forum License 2.
"""
from __future__ import unicode_literals, absolute_import, print_function, division

from sopel.config.types import StaticSection, ValidatedAttribute
from sopel.logger import get_logger
from sopel.module import (commands, event, rule, priority, interval, 
    require_privilege, require_chanmsg, require_privmsg, require_admin, OP)
from sopel.tools import events, SopelMemory

from threading import Timer

LOGGER = get_logger(__name__)


class InviteSection(StaticSection):
    minimum_users = ValidatedAttribute('minimum_users', parse=int, default=2)
    delay = ValidatedAttribute('delay', parse=int, default=1)


def configure(config):
    config.define_section('invite', InviteSection, validate=False)
    config.invite.configure_setting(
        'minimum_users',
        'Enter the minimum number of users required for Sopel to stay in the channel'
    )
    config.invite.configure_setting(
        'delay',
        'Enter the number of minutes Sopel should stay in a channel after it falls below the minimum user population'
    )


def setup(bot):
    bot.config.define_section('invite', InviteSection)
    if not bot.memory.contains('departure_scheduler'):
        bot.memory['departure_scheduler'] = SopelMemory()
    # Module has been hot-loaded, join now.
    if bot.connection_registered:
        join_known(bot)


def join_known(bot):
    """
    Auto-join invited channels
    """
    try:
        cursor = bot.db.execute('SELECT DISTINCT channel, value FROM channel_values WHERE key="autojoin";')
    except:
        return
    channels_joined = 0
    for row in cursor.fetchall():
        try:
            channel = str(row[0])
            autojoin = str(row[1]).lower() == 'true'
            if autojoin and channel not in bot.channels.keys():
                LOGGER.info('Auto-joining {}'.format(channel))
                # If we aren't yet authenticated with NickServ, coretasks handles re-attempting join
                if bot.config.core.throttle_join:
                    throttle_rate = int(bot.config.core.throttle_join)
                    channels_joined += 1
                    if not channels_joined % throttle_rate:
                        time.sleep(1)
                bot.join(channel)
        except:
            pass


@event(events.RPL_WELCOME, events.RPL_LUSERCLIENT)
@rule('.*')
@priority('low')
def agressive_join(bot, trigger):
    join_known(bot)


@interval(60)
def check_empty_chan(bot):
    for channel in bot.channels.values():
        if channel.name in bot.config.core.channels:
            # Don't ever leave force-joined channels
            continue

        if channel.name in bot.memory['departure_scheduler'].keys():
            # Already messaged channel and started timer
            continue

        user_count = len(channel.users)
        if user_count < bot.config.invite.minimum_users:
            LOGGER.info('Scheduling {} for departure, below minimum user count ({}<{})'
                .format(channel.name, user_count, bot.config.invite.minimum_users))
            if (bot.config.invite.delay > 0):
                bot.say('{} is below my minimum user population, scheduling departure for {} minutes from now.'
                    .format(channel.name, bot.config.invite.delay, channel.name), channel.name)
            else:
                bot.say('{} is below my minimum user population, departing now.'.format(channel.name), channel.name)
            timer = Timer(bot.config.invite.delay * 60, depart_channel, (bot, channel.name))
            timer.daemon = True
            timer.start()
            bot.memory['departure_scheduler'][channel.name] = timer


def depart_channel(bot, name):
    channel = bot.channels[name]
    if len(channel.users) >= bot.config.invite.minimum_users:
        LOGGER.info('Departure from {} cancelled, population has reached the minimum user count.'.format(name))
        bot.say('Cancelling departure, population has reached acceptable minimum.', name)
        return
    LOGGER.info('Departing from {}, population did not reach minimum in delay period.'.format(name))
    
    bot.part(name, 'Goodbye {}!'.format(name))
    bot.db.set_channel_value(name, 'autojoin', False)
    del bot.memory['departure_scheduler'][name]


@event('INVITE')
@rule('.*')
@priority('low')
def invite_join_chan(bot, trigger):
    """
    Join a channel Sopel is invited to, allows anyone to have the bot in their chan.
    """
    if trigger.args[1].lower() in [chan.lower() for chan in bot.channels]:
        return

    bot.db.set_channel_value(trigger.args[1], 'autojoin', True)
    bot.join(trigger.args[1])
    bot.msg(trigger.args[1], 'Hi {}! I was invited by {}. If you need assistance, please use \'.help\'. I may respond to other '
                             'bots in specific circumstances, though I will prevent myself from repeating the same message 6 '
                             'times in a row.'.format(trigger.args[1], trigger.nick))
    bot.msg(trigger.args[1], 'If my presence is unwanted, simply have a chanop say \'.part\' and I will gladly leave you alone.')


@commands('part')
@require_privilege(OP, 'You are not a channel operator.')
@require_chanmsg
@priority('low')
def part_chanop(bot, trigger):
    bot.part(trigger.sender, 'Part requested by {}'.format(trigger.nick))
    bot.db.set_channel_value(trigger.sender, 'autojoin', False)


@commands('channels')
@require_privmsg
@require_admin
@priority('low')
def channel_list(bot, trigger):
    bot.say('My connected channels ({}): {}'.format(len(bot.channels), ', '.join(bot.channels)), max_messages=3)
