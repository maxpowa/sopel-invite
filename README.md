# Sopel Invite

## Installation

```
git clone https://github.com/maxpowa/sopel-invite
cd sopel-invite
pip install .
```

## Out-of-the-box Functionality

Listens for `INVITE` events, joins channels when the invite event is received. Configurable to leave empty channels immediately or with a delay.

## Configuration

```
[invite]
minimum_users = 2
delay = 1
```

`minimum_users` is the minimum number of users that Sopel will remain in the channel with. Sopel is included in this count, so 2 is Sopel and one other user. If the population falls below this number for the given `delay` (in minutes), Sopel will leave the channel.
