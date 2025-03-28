import re

import emoji
from bson.objectid import ObjectId
from loguru import logger
from src import constants
from src.bot import bot
from src.constants import (inline_keys, keyboards, post_status, post_types,
                           states)
from src.data import DATA_DIR
from src.data_models.base import BasePost
from src.handlers.base import BaseHandler
from src.user import User
from src.utils.keyboard import create_keyboard


class CallbackHandler(BaseHandler):
    def register(self):
        @self.stackbot.bot.middleware_handler(update_types=['callback_query'])
        def init_callback_handler(bot_instance, call):
            """
            Initialize user to use in other callback handlers.

            1. Get user object.
            2. Demojize call data and call message text.
            """
            # Every message sent with inline keyboard is stored in database with callback_data and
            # post_type (question, answer, comment, ...). When user clicks on an inline keyboard button,
            # we get the post type to know what kind of post we are dealing with.
            call_info = self.get_call_info(call)
            post_id = call_info.get('post_id')

            print(call_info)


            if post_id is None:
                logger.warning('post_id is None!')

            self.stackbot.user = User(
                chat_id=call.message.chat.id, first_name=call.message.chat.first_name,
                db=self.db, stackbot=self.stackbot, post_id=post_id
            )
            # register user if not exists
            if not self.stackbot.user.is_registered:
                self.stackbot.user.register(call.message)

            # update post info
            gallery_filters = self.get_gallery_filters(
                call.message.chat.id, call.message.message_id,
                self.stackbot.user.post.post_id
            )
            self.stackbot.user.post.is_gallery = call_info.get('is_gallery', False)
            self.stackbot.user.post.gallery_filters = gallery_filters

            # Demojize text
            call.data = emoji.demojize(call.data)
            call.message.text = emoji.demojize(call.message.text)

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.actions)
        def actions_callback(call):
            """Actions >> inline key callback.
            Post actions include follow/unfollow, answer, comment, open/close, edit, ...

            1. Create actions keyboard according to the current post type.
            2. Get post text content.
            3. Edit message with post text and actions keyboard.
            """
            self.answer_callback_query(call.id, text=call.data)
            keyboard = self.stackbot.user.post.get_actions_keyboard()
            self.stackbot.user.edit_message(call.message.message_id, reply_markup=keyboard)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.answer, inline_keys.comment])
        def answer_comment_callback(call):
            """
            Answer/Comment inline key callback.

            1. Update user state.
            2. Store replied to post_id in user tracker for storing the answer/comment when user is done.
                When user sends a reply to a post, there will be replied_to_post_id key stored in the user tracker
                to store the post_id of the post that the user replied to in the answer/comment or any other reply type.
            3. Send start typing message.
            """
            self.answer_callback_query(call.id, text=call.data)
            current_post_type = post_types.COMMENT if call.data == inline_keys.comment else post_types.ANSWER

            self.stackbot.user.update_state(states.ANSWER_QUESTION if call.data == inline_keys.answer else states.COMMENT_POST)
            self.stackbot.user.track(replied_to_post_id=self.stackbot.user.post.post_id)

            self.stackbot.user.send_message(
                constants.POST_START_MESSAGE.format(
                    first_name=self.stackbot.user.first_name,
                    post_type=current_post_type
                ),
                reply_markup=keyboards.send_post,
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.back)
        def back_callback(call):
            """
            Back inline key callback.

            1. Check if back is called on a post or on settings.
                - For a post: Edit message with post keyboard.
                - For settings: Edit message with settings keyboard.
            """
            self.answer_callback_query(call.id, text=call.data)

            # main menu keyboard
            if self.stackbot.user.post.post_id is not None:
                # back is called on a post (question, answer or comment
                self.stackbot.user.edit_message(call.message.message_id, reply_markup=self.stackbot.user.post.get_keyboard())
            else:
                # back is called in settings
                self.stackbot.user.edit_message(call.message.message_id, reply_markup=self.stackbot.get_settings_keyboard())

        @bot.callback_query_handler(
            func=lambda call: call.data in [
                inline_keys.like,
                inline_keys.follow, inline_keys.unfollow,
            ]
        )
        def toggle_callback(call):
            """
            Toggle callback is used for actions that toggle between pull and push data, such as like, follow, ...

            1. Process callback according to the toggle type.
                - Like: Push/Pull user chat_id from post likes.
                - Follow: Push/Pull user chat_id from post followers.
                - ...
            2. Edit message with new keyboard that toggles based on pull/push.
            """
            self.answer_callback_query(call.id, text=call.data)

            if call.data == inline_keys.like:
                self.stackbot.user.post.like()
                keyboard = self.stackbot.user.post.get_keyboard()

            elif call.data in [inline_keys.follow, inline_keys.unfollow]:
                self.stackbot.user.post.follow()
                keyboard = self.stackbot.user.post.get_actions_keyboard()

            # update main menu keyboard
            self.stackbot.user.edit_message(call.message.message_id, reply_markup=keyboard)

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.open, inline_keys.close, inline_keys.delete, inline_keys.undelete]
        )
        def toggle_post_field_values_callback(call):
            """
            Open/Close Delete/Undelete or any other toggling between two values.
            Open means that the post is open for new answers, comments, ...

            1. Open/Close Delete/Undelete post with post_id.
            2. Edit message with new keyboard and text
                - New post text reflects the new open/close status.
            """
            self.answer_callback_query(call.id, text=call.data)

            if call.data in [inline_keys.open, inline_keys.close]:
                field = 'status'
                values = [post_status.OPEN, post_status.CLOSED]
            elif call.data in [inline_keys.delete, inline_keys.undelete]:
                field = 'status'

                # toggle between deleted and current post status
                other_status = self.stackbot.user.post.post_status
                if other_status == post_status.DELETED:
                    other_status = post_status.OPEN
                values = list({post_status.DELETED, other_status})

            self.stackbot.user.post.switch_field_between_multiple_values(field=field, values=values)
            self.stackbot.user.edit_message(
                call.message.message_id,
                text=self.stackbot.user.post.get_text(),
                reply_markup=self.stackbot.user.post.get_actions_keyboard()
            )

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.bookmark, inline_keys.unbookmark]
        )
        def toggle_user_field_values_callback(call):
            """
            """
            self.answer_callback_query(call.id, text=call.data)
            self.stackbot.user.toggle_user_field(field='bookmarks', field_value=self.stackbot.user.post.post_id)
            self.stackbot.user.edit_message(
                call.message.message_id,
                text=self.stackbot.user.post.get_text(),
                reply_markup=self.stackbot.user.post.get_actions_keyboard()
            )

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.accept, inline_keys.unaccept]
        )
        def accept_answer(call):
            """
            Accept/Unaccept answer callback.
            """
            self.answer_callback_query(call.id, text=call.data)

            self.stackbot.user.post.accept_answer()
            self.stackbot.user.edit_message(
                call.message.message_id,
                text=self.stackbot.user.post.get_text(),
                reply_markup=self.stackbot.user.post.get_actions_keyboard()
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.change_identity)
        def change_identity_callback(call):
            """
            Change identity inline key callback.

            1. Update settings with change identity keys.
                - User can choose identity between:
                    - Anonymous
                    - Username
                    - First name
            """
            self.answer_callback_query(call.id, text=call.data)

            keyboard = create_keyboard(
                inline_keys.ananymous, inline_keys.first_name, inline_keys.username,
                is_inline=True
            )
            self.stackbot.user.edit_message(call.message.message_id, reply_markup=keyboard)

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.ananymous, inline_keys.first_name, inline_keys.username]
        )
        def set_identity_callback(call):
            """
            Set new user identity.

            1. Update settings with new identity.
            2. Edit message with new settings text and main keyboard.
            """
            self.answer_callback_query(call.id, text=call.data)

            self.stackbot.user.update_settings(identity_type=call.data)
            self.stackbot.user.edit_message(
                call.message.message_id,
                text=self.get_settings_text(), reply_markup=self.get_settings_keyboard()
            )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.original_post)
        def original_post(call):
            """
            Original post inline key callback.

            Get the original post from a reply.

            1. Get the current post.
            2. Get the original post from replied_to_post_id.
            3. Edit message with original post keyboard and text.
            4. Update callback data with original post_id.
            """
            self.answer_callback_query(call.id, text=call.data)

            post = self.stackbot.user.post.as_dict()
            original_post_id = self.db.post.find_one({'_id': post['replied_to_post_id']})['_id']

            original_post_info = self.db.callback_data.find_one(
                {'chat_id': call.message.chat.id, 'message_id': call.message.message_id, 'post_id': original_post_id}
            ) or {}

            is_gallery = original_post_info.get('is_gallery')
            gallery_filters = original_post_info.get('gallery_filters')

            self.stackbot.user.post = BasePost(
                db=self.stackbot.user.db, stackbot=self.stackbot,
                post_id=original_post_id, chat_id=self.stackbot.user.chat_id,
                gallery_filters=gallery_filters, is_gallery=is_gallery
            )
            # Edit message with new gallery
            post_text, post_keyboard = self.stackbot.user.post.get_text_and_keyboard()
            self.stackbot.user.edit_message(
                call.message.message_id,
                text=post_text,
                reply_markup=post_keyboard
            )

        @bot.callback_query_handler(
            func=lambda call: call.data in [inline_keys.show_comments, inline_keys.show_answers]
        )
        def show_posts(call):
            """
            Show comments and answers of a post.
            """
            self.answer_callback_query(call.id, text=call.data)

            post = self.stackbot.user.post.as_dict()

            gallery_post_type = post_types.ANSWER if call.data == inline_keys.show_answers else post_types.COMMENT
            gallery_filters = {'replied_to_post_id': post['_id'], 'type': gallery_post_type, 'status': post_status.OPEN}
            posts = self.db.post.find(gallery_filters).sort('date', -1)

            num_posts = self.db.post.count_documents(gallery_filters)
            next_post = next(posts)

            is_gallery = True if num_posts > 1 else False
            self.edit_gallery(call, next_post['_id'], is_gallery, gallery_filters)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.next_post, inline_keys.prev_post])
        def next_prev_callback(call):
            """
            Next/Prev post inline key callback.
            """
            self.answer_callback_query(call.id, text=call.data)

            post = self.stackbot.user.post.as_dict()
            operator = '$gt' if call.data == inline_keys.next_post else '$lt'
            asc_desc = 1 if call.data == inline_keys.next_post else -1

            # Get basic filters and gallery filters
            filters = {'date': {operator: post['date']}}
            gallery_filters = self.db.callback_data.find_one(
                {'chat_id': call.message.chat.id, 'message_id': call.message.message_id, 'post_id': ObjectId(post['_id'])}
            )['gallery_filters']
            filters.update(gallery_filters)

            # Get relevant posts
            posts = self.db.post.find(filters).sort('date', asc_desc)

            try:
                next_post = next(posts)
            except StopIteration:
                self.answer_callback_query(
                    call.id,
                    constants.GALLERY_NO_POSTS_MESSAGE.format(post_type=gallery_filters.get('type', 'post'))
                )
                return

            is_gallery = True
            self.edit_gallery(call, next_post['_id'], is_gallery, gallery_filters)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.first_page, inline_keys.last_page])
        def gallery_first_last_page(call):
            """
            First and last page of a gallery button.
            """
            self.answer_callback_query(call.id, text=constants.GALLERY_NO_POSTS_MESSAGE.format(post_type='post'))

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.show_more, inline_keys.show_less])
        def show_more_less(call):
            """
            Show more or less text for a long post.
            """
            self.answer_callback_query(call.id, text=call.data)

            if call.data == inline_keys.show_more:
                truncate = False
            elif call.data == inline_keys.show_less:
                truncate = True

            # check if it's a preview or a full post
            preview = False
            if self.stackbot.user.state == states.ASK_QUESTION:
                preview = True

            # update text and keyboard
            text, keyboard = self.stackbot.user.post.get_text_and_keyboard(truncate=truncate, preview=preview)
            self.stackbot.user.edit_message(call.message.message_id, text=text, reply_markup=keyboard)

        @bot.callback_query_handler(func=lambda call: call.data in [inline_keys.export_gallery])
        def export_gallery(call):
            """
            Show more or less text for a long post.
            """
            self.answer_callback_query(call.id, text=call.data)
            chat_id = self.stackbot.user.chat_id
            gallery_filters = self.get_call_info(call)['gallery_filters']

            # Send html file to user
            file_content = self.export_gallery(gallery_filters=gallery_filters, format='html')
            with open(DATA_DIR / 'export' / f'{chat_id}.html', 'w') as f:
                f.write(file_content)

            with open(DATA_DIR / 'export' / f'{chat_id}.html', 'r') as f:
                self.stackbot.bot.send_document(
                    self.stackbot.user.chat_id, f
                )

        @bot.callback_query_handler(func=lambda call: call.data == inline_keys.attachments)
        def show_attachments(call):
            """
            Show attached files.
            """
            self.answer_callback_query(call.id, text=call.data)
            keyboard = self.stackbot.user.post.get_attachments_keyboard()
            self.stackbot.user.edit_message(call.message.message_id, reply_markup=keyboard)

        @bot.callback_query_handler(func=lambda call: re.match(r'[a-zA-Z0-9-]+', call.data))
        def send_file(call):
            """
            Send file callback. Callback data is file_unique_id. We use this to get file from telegram database.
            """
            self.answer_callback_query(call.id, text=f'Sending file: {call.data}...')
            self.stackbot.send_file(call.message.chat.id, call.data, message_id=call.message.message_id)

        @bot.callback_query_handler(func=lambda call: True)
        def not_implemented_callback(call):
            """
            Raises not implemented callback answer for buttons that are not working yet.
            """
            self.answer_callback_query(call.id, text=f':cross_mark: {call.data} not implemented.')

    def answer_callback_query(self, call_id, text, emojize=True):
        """
        Answer to a callback query.
        """
        if emojize:
            text = emoji.emojize(text)
        self.stackbot.bot.answer_callback_query(call_id, text=text)

    def get_call_info(self, call):
        """
        Get call info from call data.

        Every message with inline keyboard has information stored in database, particularly the post_id.

        We store the post_id in the database to use it later when user click on any inline button.
        For example, if user click on 'answer' button, we know which post_id to store answer for.
        This post_id is stored in the database as 'replied_to_post_id' field.

        We also store post_type in the database to use the right handler in user object (Question, Answer, Comment).
        """
        post_id = self.stackbot.retrive_post_id_from_message_text(call.message.text)

        print(post_id)
        callback_data = self.db.callback_data.find_one(
            {'chat_id': call.message.chat.id, 'message_id': call.message.message_id, 'post_id': ObjectId(post_id)}
        )

        print(list(self.db.callback_data.find(
            {'chat_id': call.message.chat.id, 'message_id': call.message.message_id}
        )))

        return callback_data or {}

    def get_gallery_filters(self, chat_id, message_id, post_id):
        result = self.db.callback_data.find_one({'chat_id': chat_id, 'message_id': message_id, 'post_id': post_id}) or {}
        return result.get('gallery_filters', {})

    def edit_gallery(self, call, next_post_id, is_gallery=False, gallery_fiters=None):
        """
        Edit gallery of posts to show next or previous post. Next post to show is the one
        with post_id=next_post_id.

        :param chat_id: Chat id to send gallery to.
        :param next_post_id: post_id of the next post to show.
        :param is_gallery: If True, send gallery of posts. If False, send single post.
            Next and previous buttions will be added to the message if is_gallery is True.
        """
        self.stackbot.user.post = BasePost(
            db=self.stackbot.user.db, stackbot=self.stackbot,
            post_id=next_post_id, chat_id=self.stackbot.user.chat_id,
            is_gallery=is_gallery, gallery_filters=gallery_fiters
        )

        # Edit message with new gallery
        post_text, post_keyboard = self.stackbot.user.post.get_text_and_keyboard()
        self.stackbot.user.edit_message(
            call.message.message_id,
            text=post_text,
            reply_markup=post_keyboard
        )

    def export_gallery(self, gallery_filters, format='html'):
        """
        Export gallery data.
        """
        user_identity = self.stackbot.user.identity
        if format != 'html':
            return

        with open(DATA_DIR / 'posts.html') as f:
            template_html = f.read()

        BODY = ''
        num_posts = self.db.post.count_documents(gallery_filters)
        posts = self.db.post.find(gallery_filters).sort('date', -1)
        for post_ind, post in enumerate(posts):
            post_ind = num_posts - post_ind
            BODY += self.post_to_html(post['_id'], post_ind, user_identity)

            # Add replies
            replies_filter = {'replied_to_post_id': post['_id'], 'type': post_types.ANSWER}
            replies = self.db.post.find(replies_filter).sort('date', -1)
            num_replies = self.db.post.count_documents(replies_filter)

            if num_replies > 0:
                BODY += (
                    '<button class="btn btn-primary" type="button" data-toggle="collapse" data-target=".{{{collapse_id}}}" '
                    'aria-expanded="false" >Replies</button>'.replace(r'{{{collapse_id}}}', f'collapse_{post["_id"]}')
                )
                BODY += '<div class="card-columns collapse {{{collapse_id}}} py-3">'.replace(r'{{{collapse_id}}}', f'collapse_{post["_id"]}')
            for reply_ind, reply in enumerate(replies):
                reply_ind = num_replies - reply_ind
                BODY += self.post_to_html(reply['_id'], reply_ind, user_identity)

            if num_replies > 0:
                BODY += '</div>'

        return template_html.replace(r'{{{POSTS-CARDS}}}', BODY)

    def post_to_html(self, post_id, post_number, user_identity):
        post = BasePost(
            db=self.stackbot.user.db, stackbot=self.stackbot,
            post_id=post_id, chat_id=self.stackbot.user.chat_id
        )
        post_html = post.export(format='html')
        post_html = post_html.replace(r'{{{user_identity}}}', str(user_identity))
        post_html = post_html.replace(r'{{{post_number}}}', str(post_number))

        return post_html