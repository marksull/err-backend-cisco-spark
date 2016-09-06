err-backend-cisco-spark
======

This is an errbot (http://errbot.io) backend for Cisco Spark (https://www.ciscospark.com)


## Status

This backend is currently under development.


## Installation

```
git checkout https://github.com/marksull/err-backend-cisco-spark.git
```

To your errbot config.py file add the following:

```
BACKEND = 'CiscoSpark'
BOT_EXTRA_BACKEND_DIR = '/path_to/err-backend-cisco-spark'
```

## Bot Configuration


To configure the bot you will need:

1. A Bot TOKEN. If you don't already have a bot setup on Cisco Spark details can be
   found here (https://developer.ciscospark.com/bots.html)

2. An Internet reachable URL for the Webhook. Spark uses a Spark initiated Webhooks to notify of any events. As a result
   the URL you provide must be reachable from the net. For testing/evaluation (http://ngrok.com) is a fantastic tool to expose
   a single port on a private device to Spark.

3. A webhook secret pass phrase (free text of your choosing). This secret will be included when the errbot webhooks
   are created and then used to validate and webhooks initiated from Spark. Further details can be found here:
   (https://communities.cisco.com/community/developer/spark/blog/2016/07/25/using-a-webhook-secret)


```
BOT_IDENTITY = {
    'TOKEN': '<insert your token in here>x',
    'WEBHOOK_DESTINATION': 'http://<your-host.some.domain>/',
    'WEBHOOK_SECRET': '<insert your webhook pass phrase in here>'
}
```

## Joining Rooms

As the backend starts, for each room listed in CHATROOM_PRESENCE it will automatically:

1. Send a room join request
2. Create a webhook

Once the backend shuts down, all created webhooks will be cleaned up.

When configuring CHATROOM_PRESENCE use the Spark ID for each room. For example, your config.py might look like:

```
DEV_ROOM = 'Y2lxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1'
MY_ROOM = 'Y2lxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2'

CHATROOM_PRESENCE = (DEV_ROOM, MY_ROOM)
```

## Requirements

This backend requires:

1. The errbot plugin err-webhook-cisck-spark (https://github.com/marksull/err-webhook-cisco-spark).

2. The library cmlCiscoSparkSDK (https://github.com/cmlccie/cmlCiscoSparkSDK)

cmlCiscoSparkSDK uses versioneer to version the package but unfortunately this has not worked reliably for me in
later versions of pip. As per the recommendations on versioneer (https://github.com/warner/python-versioneer) install
cmlCiscoSparkSDK with the following command as a workaround:

```
pip install --editable .
```

## Credit

I unrestrainedly plagiarized from most of the already existing errbot backends.


## Contributing

1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request :D