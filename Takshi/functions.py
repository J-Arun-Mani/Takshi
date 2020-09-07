import datetime
import logging
import telegram

from .constants import Message


def get_admins(chat_ids, bot):

    admins = []
    for chat_id in chat_ids:
        chat_admins = bot.get_chat_administrators(chat_id=chat_id)
        admins.extend([admin.user.id for admin in chat_admins])
    return list(set(admins))


def get_chat_title(chat_id, bot):

    chat = bot.get_chat(chat_id=chat_id)
    return chat.title


def get_user_chat_ids(text):

    splits = text.splitlines()
    user_id = splits[0].split(":")[-1]
    chat_id = splits[3].split(":")[-1]
    return (user_id, chat_id)


def leave_chats(chat_ids, bot):

    for chat_id in chat_ids:
        try:
            bot.leave_chat(chat_id=chat_id)
        except telegram.TelegramError as error:
            logging.error(error)


def refresh_invite_link(id, bot, processor):

    priv_group_id = processor.get_private_group_id(id)
    link = bot.export_chat_invite_link(chat_id=priv_group_id)
    processor.set_invite_link(id, link)


def remind_unapproved_users(id, bot, processor):

    gateway_id = processor.get_gateway_id(id)
    unapproved = processor.get_to_remind_users(id)

    notify_msg = " ".join(
        Message.MENTION.format(CAPTION=i, USER_ID=user_id)
        for i, user_id in enumerate(unapproved)
    )
    if not notify_msg.strip():
        return
    msg = bot.send_message(
        chat_id=gateway_id, text=notify_msg, parse_mode=telegram.ParseMode.HTML
    )
    msg.edit_text(text=Message.REMIND_UNAPPROVED_USERS)


def remove_users_from_chat(user_ids, chat_id, bot):

    until_date = datetime.datetime.now() + datetime.timedelta(minutes=1)

    for user_id in user_ids:
        try:
            bot.kick_chat_member(
                chat_id=chat_id, user_id=user_id, until_date=until_date
            )
        except Exception as error:
            logging.error(error)


def remove_outdated_users(id, bot, processor):

    gateway_id = processor.get_gateway_id(id)
    moderate_id = processor.get_moderate_id(id)
    outdated_users = processor.get_outdated_users(id)
    count = 0

    for user_id in outdated_users:
        try:
            bot.kick_chat_member(user_id=user_id, chat_id=gateway_id)
        except Exception as error:
            logging.error(error)
        else:
            count += 1

    bot.send_message(
        chat_id=moderate_id,
        text=Message.REMOVED_OUTDATED_USERS.format(COUNT=count),
        parse_mode=telegram.ParseMode.HTML,
    )


def periodic_job(context):

    bot = context.bot
    processor = context.bot_data["processor"]
    intervals = context.bot_data["intervals"]

    for _ in range(len(intervals)):
        id, cln_int, cur_cln_val, ref_int, cur_ref_val = intervals.pop(0)

        if cur_cln_val == cln_int // 2:
            remind_unapproved_users(id, bot, processor)
        elif cur_cln_val == cln_int:
            remove_outdated_users(id, bot, processor)
            cur_cln_val = 0
        cur_cln_val += 1

        if cur_ref_val == ref_int:
            refresh_invite_link(id, bot, processor)
            cur_ref_val = 0
        cur_ref_val += 1

        intervals.append((id, cln_int, cur_cln_val, ref_int, cur_ref_val))