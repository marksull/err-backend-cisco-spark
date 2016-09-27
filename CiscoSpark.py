import sys
import time
import logging
import requests
from markdown import markdown

from errbot.errBot import ErrBot
from errbot.backends.base import Message, Person, Room, RoomOccupant

from cmlCiscoSparkSDK import sparkapi

log = logging.getLogger('errbot.backends.CiscoSpark')

CISCO_SPARK_WEBHOOK_ID = 'CiscoSparkBackend'
CISCO_SPARK_WEBHOOK_URI = 'errbot/spark'
CISCO_SPARK_MESSAGE_SIZE_LIMIT = 7439


class CiscoSparkMessage(Message):
    """
    A Cisco Spark Message
    """
    @property
    def is_direct(self) -> bool:
        return self.extras['roomType'] == 'direct'

    @property
    def is_group(self) -> bool:
        return not self.is_direct


class CiscoSparkPerson(Person):
    """
    A Cisco Spark Person
    """
    def __init__(self, bot, attributes={}):

        self._bot = bot

        if isinstance(attributes, sparkapi.Person):
            self._spark_person = attributes
        else:
            self._spark_person = sparkapi.Person(attributes)

    @property
    def id(self):
        return self._spark_person.id

    @id.setter
    def id(self, val):
        self._spark_person.id = val

    @property
    def emails(self):
        return self._spark_person.emails

    @property
    def displayName(self):
        return self._spark_person.displayName

    @property
    def created(self):
        return self._spark_person.created

    @property
    def avatar(self):
        return self._spark_person.avatar

    @staticmethod
    def build_from_json(obj):
        return CiscoSparkPerson(sparkapi.Person(obj))

    @classmethod
    def find_using_email(cls, session, value):
        """
        Return the FIRST Cisco Spark person found when searching using an email address

        :param session: The CiscoSparkAPI session handle
        :param value: the value to search for
        :return: A CiscoSparkPerson
        """
        for person in session.get_people(email=value):
            return CiscoSparkPerson(person)
        return CiscoSparkPerson()

    @classmethod
    def find_using_name(cls, session, value):
        """
        Return the FIRST Cisco Spark person found when searching using the display name

        :param session: The CiscoSparkAPI session handle
        :param value: the value to search for
        :return: A CiscoSparkPerson
        """
        for person in session.get_people(displayName=value):
            return CiscoSparkPerson(person)
        return CiscoSparkPerson()

    @classmethod
    def get_using_id(cls, session, value):
        """
        Return a Cisco Spark person when searching using an ID

        :param session: The CiscoSparkAPI session handle
        :param value: the Spark ID
        :return: A CiscoSparkPerson
        """
        return CiscoSparkPerson(session.get_person(value))

    def load(self):
        self._spark_person = self._bot.session.Person(self.id)

    # Err API

    @property
    def person(self):
        return self.id

    @property
    def client(self):
        return ''

    @property
    def nick(self):
        return ''

    @property
    def fullname(self):
        return self.displayName

    def json(self):
        return self._spark_person.json()

    def __eq__(self, other):
        return str(self) == str(other)

    def __unicode__(self):
        return self.id

    __str__ = __unicode__
    aclattr = id


class CiscoSparkRoomOccupant(CiscoSparkPerson, RoomOccupant):
    """
    A Cisco Spark Person that Occupies a Cisco Spark Room
    """
    def __init__(self, bot, room={}, person={}):

        if isinstance(room, CiscoSparkRoom):
            self._room = room
        else:
            self._room = CiscoSparkRoom(bot, room)

        if isinstance(person, CiscoSparkPerson):
            self._spark_person = person
        else:
            super().__init__(person)

    @property
    def room(self):
        return self._room


class CiscoSparkRoom(Room):
    """
    A Cisco Spark Room
    """

    def __init__(self, bot, val={}):

        self._bot = bot
        self._webhook = None
        self._occupants = []

        if isinstance(val, sparkapi.Room):
            self._spark_room = val
        else:
            self._spark_room = sparkapi.Room(val)

    @property
    def sipAddress(self):
        return self._spark_room.sipAddress

    @property
    def created(self):
        return self._spark_room.created

    @property
    def id(self):
        return self._spark_room.id

    @id.setter
    def id(self, val):
        self._spark_room.id = val

    @property
    def title(self):
        return self._spark_room.title

    @classmethod
    def get_using_id(cls, backend, val):
        return CiscoSparkRoom(backend, backend.session.get_room(val))

    def update_occupants(self):

        log.debug("Updating occupants for room {} ({})".format(self.title, self.id))
        self._occupants.clear()

        for member in self._bot.session.get_memberships(self.id):
            self._occupants.append(CiscoSparkRoomOccupant(self.id, membership=member))

        log.debug("Total occupants for room {} ({}) is {} ".format(self.title, self.id, len(self._occupants)))

    def load(self):
        self._spark_room = self._bot.session.Room(self.id)

    # Errbot API

    def join(self, username=None, password=None):

        log.debug("Joining room {} ({})".format(self.title, self.id))

        try:
            self._bot.session.create_membership(self.id, self._bot.bot_identifier.id)
            log.debug("{} is NOW a member of {} ({})".format(self._bot.bot_identifier.displayName, self.title, self.id))

        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 409:
                log.debug("{} is already a member of {} ({})".format(self._bot.bot_identifier.displayName, self.title,
                                                                     self.id))
            else:
                log.exception("HTTP Exception: Failed to join room {} ({})".format(self.title, self.id))
                return

        except Exception:
            log.exception("Failed to join room {} ({})".format(self.title, self.id))
            return

        # When errbot joins rooms we need to create a new webhook for the integration
        self.webhook_create()

    def webhook_create(self):
        """
        Create a webhook that listens to new messages for this room (id)
        """
        self._webhook = self._bot.create_webhook(filter="roomId={}".format(self.id))

    def webhook_delete(self):
        """
        Delete the webhook for this room
        """
        self._bot.delete_webhook(self._webhook)

    def leave(self, reason=None):
        log.debug("Leave room yet to be implemented")  # TODO
        pass

    def create(self):
        log.debug("Create room yet to be implemented")  # TODO
        pass

    def destroy(self):
        log.debug("Destroy room yet to be implemented")  # TODO
        pass

    exists = True  # TODO
    joined = True  # TODO

    @property
    def topic(self):
        log.debug("Topic room yet to be implemented")  # TODO
        return "TODO"

    @topic.setter
    def topic(self, topic: str) -> None:
        log.debug("Topic room yet to be implemented")  # TODO
        pass

    @property
    def occupants(self, session=None):
        return self._occupants

    def invite(self, *args) -> None:
        log.debug("Invite room yet to be implemented")  # TODO
        pass

    def __eq_(self, other):
        return str(self) == str(other)

    def __unicode__(self):
        return self.id

    __str__ = __unicode__


class CiscoSparkBackend(ErrBot):
    """
    This is the CiscoSpark backend for errbot.
    """

    def __init__(self, config):

        super().__init__(config)

        bot_identity = config.BOT_IDENTITY

        # Do we have the basic mandatory config needed to operate the bot

        self._bot_token = bot_identity.get('TOKEN', None)
        if not self._bot_token:
            log.fatal('You need to define the Cisco Spark Bot TOKEN in the BOT_IDENTITY of config.py.')
            sys.exit(1)

        self._webhook_destination = bot_identity.get('WEBHOOK_DESTINATION', None)
        if not self._webhook_destination:
            log.fatal('You need to define WEBHOOK_DESTINATION in the BOT_IDENTITY of config.py.')
            sys.exit(1)

        self._webhook_secret = bot_identity.get('WEBHOOK_SECRET', None)
        if not self._webhook_secret:
            log.fatal('You need to define WEBHOOK_SECRET in the BOT_IDENTITY of config.py.')
            sys.exit(1)

        self._bot_rooms = config.CHATROOM_PRESENCE
        if not self._bot_rooms:
            log.fatal('You need to define CHATROOM_PRESENCE in config.py.')
            sys.exit(1)

        log.debug("Room presence: {}".format(self._bot_rooms))

        # Adjust message size limit to cater for the non-standard size limit

        if config.MESSAGE_SIZE_LIMIT > CISCO_SPARK_MESSAGE_SIZE_LIMIT:
            log.info(
                "Capping MESSAGE_SIZE_LIMIT to {} which is the maximum length allowed by CiscoSpark".
                    format(CISCO_SPARK_MESSAGE_SIZE_LIMIT)
            )
            config.MESSAGE_SIZE_LIMIT = CISCO_SPARK_MESSAGE_SIZE_LIMIT

        # Build the complete path to the Webhook URI

        if self._webhook_destination[len(self._webhook_destination) - 1] != '/':
            self._webhook_destination += '/'

        self._webhook_destination += CISCO_SPARK_WEBHOOK_URI

        # Initialize the CiscoSparkAPI session used to manage the Spark integration

        log.debug("Fetching and building identifier for the bot itself.")
        self._session = sparkapi.CiscoSparkAPI(self._bot_token)
        self.bot_identifier = CiscoSparkPerson(self, self._session.get_person_me())
        log.debug("Done! I'm connected as {} : {} ".format(self.bot_identifier, self.bot_identifier.emails))

    @property
    def mode(self):
        return 'CiscoSpark'

    @property
    def webhook_secret(self):
        return self._webhook_secret

    def create_webhook(self, url=None, name=CISCO_SPARK_WEBHOOK_ID, resource='messages', event='created', filter=None,
                       secret=None):
        """
        Create a webhook that the bot can consume
        :param url: The URL the webhook is to publish towards (by default the bots webhook will be used)
        :param name: The name that will be given to the Webhook
        :param resource: The type of resource that we want Cisco Spark to monitor
        :param event: The type of event that we want Cisco Spark to monitor
        :param filter: Any filters that will limit to which events Cisco Spark will listen (e.g. roomId)
        :param secret: The secret used to create a signature for the JSON payload
        :return: A Webhook object
        """

        if not url:
            url = self._webhook_destination

        if not secret:
            secret = self.webhook_secret

        log.debug("Registering webhook {} with filter {}".format(url, filter))

        hook = self.session.create_webhook(name, url, resource, event, filter, secret)

        log.debug("Registration successful")
        return hook

    def delete_webhook(self, webhook):
        """
        Delete a webhook

        :param webhook: Cisco Spark Webhook ID
        """
        log.debug("Deleting webhook id {}".format(webhook.id))
        self.session.delete_webhook(webhook.id)
        log.debug("Done! Webhook deleted")

    def delete_webhooks(self):
        """
        Delete all webhooks for the bot that have the webhook name CISCO_SPARK_WEBHOOK_ID
        """
        log.debug("Deleting ALL webhooks attached to rooms")

        for hook in self.session.get_webhooks():
            if hook.name == CISCO_SPARK_WEBHOOK_ID:
                filer, filter_id = hook.filter.split("=")
                if filer == 'roomId':
                    if filter_id in self._bot_rooms:
                        self.delete_webhook(hook)

        log.debug("Done! ALL webhooks deleted")

    # The following are convenience methods to make it easier to create objects from the err-cisco-spark-webhook plugin
    def get_person_using_email(self, email):
        """
        Loads a person from Spark using the email address for the search criteria

        :param email: The email address to use for the search
        :return: CiscoSparkPerson
        """
        return CiscoSparkPerson.find_using_email(self._session, email)

    def get_person_using_id(self, id):
        """
        Loads a person from Spark using the spark id for the search criteria

        :param id: The spark id to use for the search
        :return: CiscoSparkPerson
        """
        return CiscoSparkPerson.get_using_id(self._session, id)

    def create_person_using_id(self, id):
        """
        Create a new person and sets the ID. This method DOES NOT load the person details from Spark

        :param id: The spark id of the person
        :return: CiscoSparkPerson
        """
        person = CiscoSparkPerson(self)
        person.id = id
        return person

    def get_room_using_id(self, id):
        """
        Loads a room from Spark using the id for the search criteria

        :param id: The Spark id of the room
        :return: CiscoSparkRoom
        """
        return CiscoSparkRoom.get_using_id(self, id)

    def create_room_using_id(self, id):
        """
        Create a new room and sets the ID. This method DOES NOT load the room details from Spark
        :param id:
        :return:
        """
        room = CiscoSparkRoom(self)
        room.id = id
        return room

    def create_message(self, body, frm, to, extras):
        """
        Creates a new message ready for sending

        :param body: The text that contains the message to be sent
        :param frm: A CiscoSparkPerson from whom the message will originate
        :param to: A CiscoSparkPerson to whom the message will be sent
        :param extras: A dictionary of extra items
        :return: CiscoSparkMessage
        """
        return CiscoSparkMessage(body=body, frm=frm, to=to, extras=extras)

    def get_message_using_id(self, id):
        """
        Loads a message from Spark using the id for the search criteria

        :param id: The id of the message to load
        :return: Message
        """
        return self.session.get_message(id)

    def get_occupant_using_id(self, person, room):
        """
        Builds a CiscoSparkRoomOccupant using a person and a room

        :param person: A CiscoSparkPerson
        :param room: A CiscoSparkRoom
        :return: CiscoSparkRoomOccupant
        """
        return CiscoSparkRoomOccupant(bot=self, person=person, room=room)

    @property
    def session(self):
        """
        The session handle for sparkapi.CiscoSparkAPI
        :return:
        """
        return self._session


    def follow_room(self, room):
        """
        Backend: Follow Room yet to be implemented

        :param room:
        :return:
        """
        log.debug("Backend: Follow Room yet to be implemented")  # TODO
        pass

    def rooms(self):
        """
        Backend: Rooms yet to be implemented

        :return:
        """
        log.debug("Backend: Rooms yet to be implemented")  # TODO
        pass

    def contacts(self):
        """
        Backend: Contacts yet to be implemented

        :return:
        """
        log.debug("Backend: Contacts yet to be implemented")  # TODO
        pass

    def build_identifier(self, strrep):
        """
        Build an errbot identifier using the Spark ID of the person

        :param strrep: The ID of the Cisco Spark person
        :return: CiscoSparkPerson
        """
        return self.create_person_using_id(strrep)

    def query_room(self, room):
        """
        Create a CiscoSparkRoom object identified by the ID of the room

        :param room: The Cisco Spark room ID
        :return: CiscoSparkRoom object
        """
        return CiscoSparkRoom.get_using_id(self, room)

    def send_message(self, mess):
        """
        Send a message to Cisco Spark

        :param mess: A CiscoSparkMessage
        """
        md = markdown(mess.body, extensions=['markdown.extensions.nl2br', 'markdown.extensions.fenced_code'])
        if type(mess.to) == CiscoSparkPerson:
            self.session.create_message(toPersonId=mess.to.id, text=mess.body, markdown=md)
        else:
            self.session.create_message(roomId=mess.to.room.id, text=mess.body, markdown=md)

    def build_reply(self, mess, text=None, private=False):
        """
        Build a reply in the format expected by errbot by swapping the to and from source and destination

        :param mess: The original CiscoSparkMessage object that will be replied to
        :param text: The text that is to be sent in reply to the message
        :param private: Boolean indiciating whether the message should be directed as a private message in lieu of
                        sending it back to the room
        :return: CiscoSparkMessage
        """
        response = self.build_message(text)
        response.frm = mess.to
        response.to = mess.frm
        return response

    def disconnect_callback(self):
        """
        Disconnection has been requested, lets make sure we clean up our per-room webhooks
        """
        self.delete_webhooks()
        super().disconnect_callback()

    def serve_once(self):
        """
        Signal that we are connected to the Spark Service and hang around waiting for disconnection request

        As Cisco Spark uses Webhooks for integration there is no need to kick-off threads to listen to channels/rooms.
        We just hand around relying on the err-backend-cisco-spark plugin to feed the backend.

        """
        self.connect_callback()
        try:
            while True:
                time.sleep(2)
        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down..")
            return True
        finally:
            self.disconnect_callback()

    def change_presence(self, status, message):
        """
        Backend: Change presence yet to be implemented

        :param status:
        :param message:
        :return:
        """
        log.debug("Backend: Change presence yet to be implemented")  # TODO
        pass

    def prefix_groupchat_reply(self, message, identifier):
        """
        Backend: Prefix group chat reply yet to be implemented

        :param message:
        :param identifier:
        :return:
        """
        log.debug("Backend: Prefix group chat reply yet to be implemented")  # TODO
        pass

    def remember(self, id, key, value):
        """
        Save the value of a key to a dictionary specific to a Spark room or person
        This is available in backend to provide easy access to variables that can be shared between plugins

        :param id: Spark ID of room or person
        :param key: The dictionary key
        :param value:  The value to be assigned to the key
        """
        values = self.recall(id)
        values[key] = value
        self[id] = values

    def forget(self, id, key):
        """
        Delete a key from a dictionary specific to a Spark room or person

        :param id: Spark ID of room or person
        :param key: The dictionary key
        :return: The popped value or None if the key was not found
        """
        values = self.recall(id)
        value = values.pop(key, None)
        self[id] = values
        return value

    def recall(self, id):
        """
        Access a dictionary for a room or person using the Spark ID as the key

        :param id: Spark ID of room or person
        :return: A dictionary. If no dictionary was found an empty dictionary will be returned.
        """
        values = self.get(id)
        return values if values else {}

    def recall_key(self, id, key):
        """
        Access the value of a specific key from a Spark room or person dictionary

        :param id: Spark ID of room or person
        :param key: The dictionary key
        :return: Either the value of the key or None if the key is not found
        """
        return self.recall(id).get(key)