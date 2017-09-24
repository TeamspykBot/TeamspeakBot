## Data Structure
The bot will unescape and normalize all messages it receives from the
teamspeak server. The event object has three members:

- args: holds the answer from the teamspeak server
- data: holds user defined data which was given in the send_command call
- bot: holds the bot instance

`args` is guaranteed to be an array. Every item in that array is a dictionary,
where the key corresponds to a field in the received query answer.
For most teamspeak query answers, this array will only be one item long ( e.g on_client_joined, on_client_left ).
An example for an array with multiple items would be `clientlist`.

### Example:

Teamspeak returns an array of clients for the command `clientlist`.
When you send the command `clientlist` via
`send_command("clientlist", callback=lambda e: print(e.args))` teamspeak
will answer with a list of all clients, looking like this:

```
clid=1 cid=1 client_database_id=2 client_nickname=Client2 client_type=0|
clid=3 cid=1 client_database_id=2 client_nickname=Client1 client_type=0
```

The bot will normalize this to the following array of dictionaries,
that is also what you find in event.args:

```
[
    {
        'clid': '1',
        'cid': '1',
        'client_database_id': '2',
        'client_nickname': 'Client2',
        'client_type': '0'
    },
    {
        'clid': '3',
        'cid': '1',
        'client_database_id': '2',
        'client_nickname': 'Client1',
        'client_type': '0'
    }
]
```

<br>
<br>  

## on_client_joined event args
```
[
    {
        'notifycliententerview': '',
        'cfid': '0',
        'ctid': '1',
        'reasonid': '0',
        'clid': '11',
        'client_unique_identifier': 'CRhMp/NFyvdP1D8DDooQIr8gAWI=',
        'client_nickname': 'ClientName',
        'client_input_muted': '0',
        'client_output_muted': '1',
        'client_outputonly_muted': '0',
        'client_input_hardware': '1',
        'client_output_hardware': '1',
        'client_meta_data': '',
        'client_is_recording': '0',
        'client_database_id': '2',
        'client_channel_group_id': '8',
        'client_servergroups': '6,7',
        'client_away': '0',
        'client_away_message': '',
        'client_type': '0',
        'client_flag_avatar': '',
        'client_talk_power': '75',
        'client_talk_request': '0',
        'client_talk_request_msg': '',
        'client_description': '',
        'client_is_talker': '0',
        'client_is_priority_speaker': '0',
        'client_unread_messages': '0',
        'client_nickname_phonetic': '',
        'client_needed_serverquery_view_power': '75',
        'client_icon_id': '0',
        'client_is_channel_commander': '0',
        'client_country': '',
        'client_channel_group_inherited_channel_id': '1',
        'client_badges': '',
        'cid': '1'
    }
]
```

<br>

## on_client_left event args
```
[
    {
        'notifyclientleftview': '',
        'cfid': '1',
        'ctid': '0',
        'reasonid': '8',
        'reasonmsg': 'leaving',
        'clid': '11'
    }
]
```

<br>

## on_client_moved event args
```
[
    {
        'notifyclientmoved': '',
        'ctid': '3',
        'reasonid': '0',
        'clid': '12',
        'cid': '2'
    }
]
```

<br>

## on_private_text event args
```
[
    {
        'notifytextmessage': '',
        'targetmode': '1',
        'msg': 'Message Body',
        'target': '14',
        'invokerid': '1',
        'invokername': 'Client2',
        'invokeruid': 'CRhMp/NFyvdP1D8DDooQIr8gAWI='
    }
]
```

<br>

## on_channel_text
```
[
    {
        'notifytextmessage': '',
        'targetmode': '2',
        'msg': 'Hello',
        'invokerid': '1',
        'invokername': 'ClientName',
        'invokeruid': 'CRhMp/NFyvdP1D8DDooQIr8gAWI=',
        'cid': 2
    }
]
```