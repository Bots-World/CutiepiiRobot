"""
BSD 2-Clause License

Copyright (C) 2017-2019, Paul Larsen
Copyright (C) 2021-2022, Awesome-RJ, <https://github.com/Awesome-RJ>
Copyright (c) 2021-2022, Yūki • Black Knights Union, <https://github.com/Awesome-RJ/CutiepiiRobot>

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import threading

from sqlalchemy import String, Column, Integer, UnicodeText
from sqlalchemy.sql.sqltypes import BigInteger

from Cutiepii_Robot.modules.sql import SESSION, BASE

DEF_COUNT = 1
DEF_LIMIT = 0
DEF_OBJ = (None, DEF_COUNT, DEF_LIMIT)


class FloodControl(BASE):
    __tablename__ = "antiflood"
    chat_id = Column(String(14), primary_key=True)
    user_id = Column(BigInteger)
    count = Column(Integer, default=DEF_COUNT)
    limit = Column(Integer, default=DEF_LIMIT)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)  # ensure string

    def __repr__(self):
        return "<flood control for %s>" % self.chat_id


class FloodSettings(BASE):
    __tablename__ = "antiflood_settings"
    chat_id = Column(String(14), primary_key=True)
    flood_type = Column(Integer, default=1)
    value = Column(UnicodeText, default="0")

    def __init__(self, chat_id, flood_type=1, value="0"):
        self.chat_id = str(chat_id)
        self.flood_type = flood_type
        self.value = value

    def __repr__(self):
        return f"<{self.chat_id} will executing {self.flood_type} for flood.>"


FloodControl.__table__.create(checkfirst=True)
FloodSettings.__table__.create(checkfirst=True)

INSERTION_FLOOD_LOCK = threading.RLock()
INSERTION_FLOOD_SETTINGS_LOCK = threading.RLock()

CHAT_FLOOD = {}


def set_flood(chat_id, amount):
    with INSERTION_FLOOD_LOCK:
        flood = SESSION.query(FloodControl).get(str(chat_id))
        if not flood:
            flood = FloodControl(str(chat_id))

        flood.user_id = None
        flood.limit = amount

        CHAT_FLOOD[str(chat_id)] = (None, DEF_COUNT, amount)

        SESSION.add(flood)
        SESSION.commit()


def update_flood(chat_id: str, user_id) -> bool:
    if str(chat_id) in CHAT_FLOOD:
        curr_user_id, count, limit = CHAT_FLOOD.get(str(chat_id), DEF_OBJ)

        if limit == 0:  # no antiflood
            return False

        if user_id != curr_user_id or user_id is None:  # other user
            CHAT_FLOOD[str(chat_id)] = (user_id, DEF_COUNT, limit)
            return False

        count += 1
        if count > limit:  # too many msgs, kick
            CHAT_FLOOD[str(chat_id)] = (None, DEF_COUNT, limit)
            return True

        # default -> update
        CHAT_FLOOD[str(chat_id)] = (user_id, count, limit)
        return False


def get_flood_limit(chat_id):
    return CHAT_FLOOD.get(str(chat_id), DEF_OBJ)[2]


def set_flood_strength(chat_id, flood_type, value):
    # for flood_type
    # 1 = ban
    # 2 = kick
    # 3 = mute
    # 4 = tban
    # 5 = tmute
    with INSERTION_FLOOD_SETTINGS_LOCK:
        curr_setting = SESSION.query(FloodSettings).get(str(chat_id))
        if not curr_setting:
            curr_setting = FloodSettings(
                chat_id, flood_type=int(flood_type), value=value,
            )

        curr_setting.flood_type = int(flood_type)
        curr_setting.value = str(value)

        SESSION.add(curr_setting)
        SESSION.commit()


def get_flood_setting(chat_id):
    try:
        setting = SESSION.query(FloodSettings).get(str(chat_id))
        if setting:
            return setting.flood_type, setting.value
        return 1, "0"

    finally:
        SESSION.close()


def migrate_chat(old_chat_id, new_chat_id):
    with INSERTION_FLOOD_LOCK:
        flood = SESSION.query(FloodControl).get(str(old_chat_id))
        if flood:
            CHAT_FLOOD[str(new_chat_id)] = CHAT_FLOOD.get(str(old_chat_id), DEF_OBJ)
            flood.chat_id = str(new_chat_id)
            SESSION.commit()

        SESSION.close()


def __load_flood_settings():
    global CHAT_FLOOD
    try:
        all_chats = SESSION.query(FloodControl).all()
        CHAT_FLOOD = {chat.chat_id: (None, DEF_COUNT, chat.limit) for chat in all_chats}
    finally:
        SESSION.close()


__load_flood_settings()
