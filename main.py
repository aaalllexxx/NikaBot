import os
import random
import uuid

from aiogram import executor
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery, InputFile
from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import markdown

from json_dict import JsonDict
from settings import dp, session, Base, engine, bot
from models.User import User
from models.Event import Event

Base.metadata.create_all(engine)

editing_groups = {}


class Form(StatesGroup):
    firstname = State()
    lastname = State()
    phone = State()
    comps = State()
    dob = State()
    group = State()


class EventState(StatesGroup):
    add = State()


class Lesson(StatesGroup):
    lesson = State()


class Find(StatesGroup):
    start = State()
    run = State()


def get_user(chat_id):
    return session.query(User).filter_by(chat_id=chat_id).first()


class LevelFilter(BoundFilter):
    key = "level"

    def __init__(self, level=0):
        self.level = level

    async def check(self, message: Message | CallbackQuery) -> bool:
        if isinstance(message, Message):
            user = get_user(message.chat.id)
        elif isinstance(message, CallbackQuery):
            user = get_user(message.message.chat.id)
        if user.level < self.level:
            await message.answer("Возможность вам недоступна.")
            return False
        return True


class IsDay(BoundFilter):
    key = "day"
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]

    async def check(self, message: Message | CallbackQuery) -> bool:
        if (message.text.lower() in self.days) and message.chat.id in list(editing_groups):
            return True
        return False


def add_buttons(keyboard: ReplyKeyboardMarkup | InlineKeyboardMarkup,
                buttons: list[KeyboardButton] | list[InlineKeyboardButton]):
    for i in buttons:
        if isinstance(i, list):
            keyboard.row(*i)
        else:
            keyboard.add(i)


default_markup = ReplyKeyboardMarkup(resize_keyboard=True)
buttons = [KeyboardButton("Профиль"),
           [KeyboardButton("Расписание"), KeyboardButton("Новости")],
           KeyboardButton("Найти команду")]
add_buttons(default_markup, buttons)
comps = ["Дизайнер",
         "Аналитик",
         "Backend разработчик",
         "Frontend разработчик",
         "Python разработчик",
         "Java разработчик",
         "C/C++ разработчик",
         "Go разработчик",
         "Инженер",
         "3D modeller",
         "Специалист по электронике",
         "Специалист по кибербезопасности"]


@dp.message_handler(lambda x: x.text.lower() == "найти команду")
async def find_team(message: Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [KeyboardButton(text) for text in comps] + [KeyboardButton("Назад")]
    add_buttons(markup, buttons)
    await Find.start.set()
    return await message.answer("Кого ищем?", reply_markup=markup)


@dp.message_handler(state=Find.run)
async def run_leobot(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if message.text.lower() == "стоп":
        user.viewed_index = 0
        user.is_finding = ""
        session.commit()
        await state.finish()
        return await message.answer("Поиск остановлен.", reply_markup=default_markup)
    users = session.query(User).all()
    curr_user = users[user.viewed_index]
    if message.text == "👍":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="Открыть в телеграм", url=curr_user.link))
        return await message.answer(f"Телефон пользователя: {curr_user.phone}", reply_markup=markup)
    else:
        for i in range(user.viewed_index + 1, len(users)):
            curr_user = users[i]
            if user.id == curr_user.id:
                continue
            if user.is_finding in curr_user.comp.split(", ") and curr_user.want_find == 1:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                buttons = [[KeyboardButton("👍"), KeyboardButton("👎")], KeyboardButton("Стоп")]
                add_buttons(markup, buttons)
                user.viewed_index = i
                session.commit()
                return await message.answer(f"__* Имя*__: {markdown.escape_md(curr_user.firstname)}\n"
                                            f"__*Фамилия*__: {markdown.escape_md(curr_user.lastname)}\n"
                                            f"__*Дата рождения*__: {markdown.escape_md(curr_user.dob)}\n"
                                            f"__*Компетенции*__: {markdown.escape_md(curr_user.comp)}",
                                            reply_markup=markup,
                                            parse_mode="MarkdownV2")
        else:
            await message.answer("Пользователи закончились(")


@dp.message_handler(state=Find.start)
async def find(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if message.text.lower() == "назад":
        user.is_finding = ""
        session.commit()
        await state.finish()
        return await message.answer("вы возвращены в главное меню.", reply_markup=default_markup)
    users = session.query(User).all()
    if message.text in comps:
        user.is_finding = message.text
        session.commit()
        for i in range(user.viewed_index, len(users)):
            curr_user = users[i]
            if user.id == curr_user.id:
                continue
            if user.is_finding in curr_user.comp.split(", ") and curr_user.want_find == 1:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                buttons = [[KeyboardButton("👍"), KeyboardButton("👎")], KeyboardButton("Стоп")]
                add_buttons(markup, buttons)
                await message.answer(f"__* Имя*__: {markdown.escape_md(curr_user.firstname)}\n"
                                     f"__*Фамилия*__: {markdown.escape_md(curr_user.lastname)}\n"
                                     f"__*Дата рождения*__: {markdown.escape_md(curr_user.dob)}\n"
                                     f"__*Компетенции*__: {markdown.escape_md(curr_user.comp)}", reply_markup=markup,
                                     parse_mode="MarkdownV2")
                user.viewed_index = i
                session.commit()
                return await Find.next()
        return await message.answer("Нет пользователей с такой компетенцией. Попробуйте выбрать другую.")
    else:
        await message.answer("Такой компетенции нет(\nВыберите компетенцию из перечисленных снизу.")


def get_new_by_tags(tags, user):
    events = session.query(Event).all()
    tags = [i.strip() for i in tags]

    for event in events:
        event_tags = [i.lower() for i in event.tags.split(",")]
        for tag in tags:
            if tag.lower() in event_tags and event.id not in user.read_news:
                user.read_news += event.id + ", "
                session.commit()
                return event
    for event in events:
        if event.id not in user.read_news:
            user.read_news += event.id + ", "
            session.commit()
            return event

    return "Новости закончились("


@dp.message_handler(lambda x: x.text.lower() == "назад")
async def back(message: Message):
    return await message.answer("Вы возвращены в меню", reply_markup=default_markup)


@dp.message_handler(lambda x: x.text.lower() == "новости" or x.text.lower() == "показать ещё")
async def show_new(message: Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [KeyboardButton("Показать ещё"), KeyboardButton("Назад")]
    add_buttons(markup, buttons)
    user = get_user(message.chat.id)
    if user.comp is not None:
        event = get_new_by_tags(user.comp.split(","), user)
    else:
        event = get_new_by_tags([], user)
    photos = os.listdir("imgs")
    photos = [i.split(".")[0] for i in photos]
    if isinstance(event, str):
        return await message.answer(event)
    if event.id in photos:
        return await bot.send_photo(message.chat.id, InputFile(f"imgs/{event.id}.jpg"), caption=event.text,
                                    reply_markup=markup)
    else:
        return await message.answer(event.text, reply_markup=markup)


@dp.message_handler(commands=["id"])
async def get_id(message: Message):
    await message.answer(f"Ваш id: ```{str(message.chat.id)}```", parse_mode="Markdown")


@dp.message_handler(LevelFilter(5), commands=["set"])
async def set_level(message: Message):
    args = message.text.split(",")
    args[0] = args[0].split()[1]
    args = [i.strip() for i in args]
    print(args)
    if len(args) < 3:
        return await message.answer("Команда введена неверно.")
    user = get_user(args[0])
    if hasattr(user, args[1]):
        setattr(user, args[1], args[2])
        session.commit()
        return await message.answer("Значение установлено")


@dp.message_handler(state=Lesson.lesson)
async def add_lesson(message: Message, state: FSMContext):
    if message.text.lower() == "готово":
        del editing_groups[message.chat.id]
        await message.answer("Расписание изменено.", reply_markup=default_markup)
        return await state.finish()
    schedule = JsonDict("schedule.json")
    group = editing_groups[message.chat.id][0].strip()
    day = editing_groups[message.chat.id][1]
    data = message.text.split(",")
    if len(data) == 3:
        schedule[group][day].append(data)
        schedule.push(schedule.dictionary)
        return await message.answer("Пара добавлена.")
    return await message.answer("Вы ввели данные некорректно.")


@dp.message_handler(IsDay())
async def edit_day(message: Message):
    day = IsDay.days.index(message.text.lower())
    editing_groups[message.chat.id].append(day)
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Готово"))
    schedule = JsonDict("schedule.json")
    sdict = schedule.dictionary
    group = editing_groups[message.chat.id][0].strip()
    try:
        sdict[group][day] = []
        schedule.push(schedule.dictionary)
    except:
        for i in range(6 - len(sdict[group])):
            sdict[group].append([])
        schedule.push(schedule.dictionary)

    await Lesson.lesson.set()
    await message.answer("Введите пару в формате\n"
                         "Название, кабинет, время начала - время конца")
    await message.answer("Пример: Русский язык, 0305, 9:00 - 10:30", reply_markup=markup)


@dp.message_handler(LevelFilter(3), commands=["edit_schedule"])
async def edit_schedule(message: Message):
    schedule = JsonDict("schedule.json")
    groups = schedule.keys()
    markup = InlineKeyboardMarkup()
    buttons = []
    print(groups)
    for i in range(0, len(groups) // 3, 3):
        buttons.append([
            InlineKeyboardButton(groups[i], callback_data=f"edit: {groups[i]}"),
            InlineKeyboardButton(groups[i + 1], callback_data=f"edit: {groups[i + 1]}"),
            InlineKeyboardButton(groups[i + 2], callback_data=f"edit: {groups[i + 2]}")
        ])
    buttons.append([])
    for i in range(len(groups) % 3):
        buttons[-1].append(InlineKeyboardButton(groups[-1 - i], callback_data=f"edit: {groups[-1 - i]}"))
    buttons.append(InlineKeyboardButton("Добавить группу", callback_data="add"))

    add_buttons(markup, buttons)
    await message.answer("Выберите группу:", reply_markup=markup)


@dp.message_handler(commands=["start"])
async def start(message: Message):
    user = get_user(message.chat.id)
    if not user:
        user = User(firstname=message.from_user.first_name,
                    lastname=message.from_user.last_name,
                    chat_id=message.chat.id,
                    link=message.from_user.url,
                    comp="")
        session.add(user)
        session.commit()
    else:
        return await message.answer("Привет ещё раз)", reply_markup=default_markup)

    return await message.answer(
        f"Привет, {user.firstname}, я твой HelpBot!⭐️\nЯ здесь, чтобы помочь тебе с расписанием, "
        "уведомлениями от твоих любимых клубов, поиском команд для хакатонов и многим другим. "
        "\nРад видеть тебя в нашем сообществе! 😊",
        reply_markup=default_markup)


@dp.message_handler(lambda x: x.text.lower() == "расписание")
async def schedule_func(message: Message):
    user = get_user(message.chat.id)
    if user and user.group:
        shedule = JsonDict("schedule.json")
        if user.group in shedule.keys():
            answ = "Ваше расписание:\n"
            days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
            for i, day in enumerate(days):
                if i >= len(shedule[user.group]):
                    break
                answ += f"* {day}*" + ": \n"
                for n, v in enumerate(shedule[user.group][i]):
                    try:
                        answ += f"{n + 1}\. {v[0] if v[0] != '-' else 'Окно'}, каб: __ {v[1]}__\n``` {v[2] if v[2] != '-' else ''}```\n".replace(
                            "-", "\-")
                    except:
                        continue

                await message.answer(answ, parse_mode="MarkdownV2")
                answ = ""
        else:
            return await message.answer("К сожалению, вашей группы нет в списке(\n"
                                        "Проверьте корректность введённого номера группы в профиле")
    else:
        return await message.answer("Поле 'группа' не заполнено. Вы можете заполнить его во вкладке 'Профиль' в главном меню.")


class Tag(StatesGroup):
    set = State()


@dp.message_handler(LevelFilter(2), state=Tag.set)
async def set_tags(message: Message, state: FSMContext):
    if message.text.lower() == "готово":
        await state.finish()
        return await message.answer("Тэги сохранены.", reply_markup=default_markup)
    if message.text in comps:
        user = get_user(message.chat.id)
        event = session.query(Event).filter_by(id=user.last_published).first()
        if not message.text in event.tags:
            event.tags += message.text + ", "
            session.commit()
            return await message.answer("Тэг добавлен.")
        else:
            return await message.answer("Тэг уже был присвоен.")
    return await message.answer("Я не знаю такой компетенции(\nВыберите из предложенных ниже")


@dp.message_handler(LevelFilter(2), commands=["tags"])
async def add_tags(message: Message):
    user = get_user(message.chat.id)
    event = session.query(Event).filter_by(id=user.last_published).first()
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [KeyboardButton(i) for i in comps] + [KeyboardButton("Готово")]
    add_buttons(markup, buttons)
    if event is not None:
        await Tag.set.set()
        return await message.answer("Выберите компетенции, для которых подойдёт эта новость:", reply_markup=markup)


@dp.message_handler(LevelFilter(2), commands=["add_event"])
async def add_events(message: Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [KeyboardButton("отмена")]
    add_buttons(markup, buttons)
    await EventState.add.set()
    await message.answer("Пропишите новость.", reply_markup=markup)


@dp.message_handler(content_types=["photo"], state=EventState.add)
async def add_new(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    uid = uuid.uuid4().hex
    try:
        event = Event(id=uid, text=message.caption, tags="")
        session.add(event)
        session.commit()
        await message.photo[-1].download(destination_file=f"imgs/{uid}.jpg")
        await state.finish()
        user.last_published = uid
        session.commit()
        return await message.answer("Сохранено. Чтобы добавить тэги(компетенции) к новости, пропишите /tags.",
                                    reply_markup=default_markup)
    except:
        return await message.answer("Не получилось сохранить новость.")


@dp.message_handler(state=EventState.add)
async def add_text_new(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if message.text.lower() == "отмена":
        await state.finish()
        return await message.answer("Отменено.", reply_markup=default_markup)
    try:
        uid = uuid.uuid4().hex
        event = Event(id=uid, text=message.text, tags="")
        session.add(event)
        session.commit()
        await state.finish()
        user.last_published = uid
        session.commit()
        return await message.answer("Сохранено. Чтобы добавить тэги(компетенции) к новости, пропишите /tags.",
                                    reply_markup=default_markup)
    except:
        await state.finish()
        return await message.answer("Новость не сохранена.")


@dp.message_handler(lambda x: x.text.lower() == "новости")
async def events(message: Message):
    pass


@dp.message_handler(lambda x: x.text.lower() == "профиль")
async def profile(message: Message):
    user = get_user(message.chat.id)
    markup = InlineKeyboardMarkup()
    buttons = [InlineKeyboardButton("Имя", callback_data="firstname"),
               InlineKeyboardButton("Фамилия", callback_data="lastname"),
               InlineKeyboardButton("Телефон", callback_data="phone"),
               InlineKeyboardButton("Компетенции", callback_data="comps"),
               InlineKeyboardButton("Дата рождения", callback_data="dob"),
               InlineKeyboardButton("Группа", callback_data="group")
               ]
    add_buttons(markup, buttons)
    if user:
        text = f"__* Имя*__: {markdown.escape_md(user.firstname if user.firstname else 'Не указано')}\n" \
               f"__*Фамилия*__: {markdown.escape_md(user.lastname if user.lastname else 'Не указана')}\n" \
               f"__*Телефон*__: {markdown.escape_md(user.phone if user.phone else 'Не указан')}\n" \
               f"__*Компетенции*__: {markdown.escape_md(user.comp if user.comp else 'Не указаны')}\n" \
               f"__*Дата рождения*__: {markdown.escape_md(user.dob if user.dob else 'Не указана')}\n" \
               f"__*Группа*__: {markdown.escape_md(user.group if user.group else 'Не указана')}\n"
        return await message.answer(text, reply_markup=markup,
                                    parse_mode="MarkdownV2")


@dp.message_handler(state=Form.firstname)
async def set_firstname(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if user:
        user.firstname = message.text
        session.commit()
        await message.answer(f"Имя изменено на {message.text}")
    await state.finish()


@dp.message_handler(state=Form.group)
async def set_group(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if user:
        user.group = message.text
        session.commit()
        await message.answer(f"Группа изменена на {message.text}")
    await state.finish()


@dp.message_handler(state=Form.dob)
async def set_dob(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if user:
        dob = message.text.split(".")
        if len(dob) == 3 and int(dob[0]) <= 31 and len(dob[0]) == 2 and int(dob[1]) <= 12 and len(dob[1]) == 2 \
                and len(dob[2]) <= 5:
            user.dob = message.text
            session.commit()
        else:
            return await message.answer("Некорректно введена дата. Введите в формате DD.MM.YYYY")
        await message.answer(f"Дата рождения изменена на {message.text}")
    await state.finish()


@dp.message_handler(state=Form.phone)
async def set_phone(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if user:
        text = message.text.replace("-", "").replace("(", "").replace(")", "").replace("+", "").replace(" ", "")
        user.phone = text
        session.commit()
        await message.answer(f"телефон изменён на {text}")
    return await state.finish()


@dp.message_handler(state=Form.comps)
async def set_comps(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if user:
        comp = user.comp.split(", ") if user.comp else []
        text = message.text
        if text in comps and not (text in comp):
            comp.append(text)
            user.comp = ", ".join(comp)
            session.commit()
            return await message.answer(f"Компетенция добавлена")

        elif message.text == "Готово":
            await state.finish()
            return await message.answer(f"Компетенции изменены", reply_markup=default_markup)
        elif not text in comps:
            return await message.answer(f"Такой компетенции нет в списке.")


@dp.message_handler(state=Form.lastname)
async def set_lastname(message: Message, state: FSMContext):
    user = get_user(message.chat.id)
    if user:
        user.lastname = message.text
        session.commit()
        await message.answer(f"Фамилия изменена на {message.text}")
    await state.finish()


@dp.callback_query_handler()
async def callback_handler(call: CallbackQuery):
    user = get_user(call.message.chat.id)
    if "edit:" in call.data and user.level > 5:
        editing_groups[call.message.chat.id] = [call.data.split(":")[1]]
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [
            KeyboardButton("Понедельник"),
            KeyboardButton("Вторник"),
            KeyboardButton("Среда"),
            KeyboardButton("Четверг"),
            KeyboardButton("Пятница"),
            KeyboardButton("Суббота")
        ]
        add_buttons(markup, buttons)
        await call.message.answer("Выберите день недели:", reply_markup=markup)
        await call.answer(call.data.split(":")[1])
    elif call.data.lower() == "firstname":
        await Form.firstname.set()
        await call.message.answer("Введите ваше имя")
    elif call.data.lower() == "lastname":
        await Form.lastname.set()
        await call.message.answer("Введите вашу фамилию")
    elif call.data.lower() == "phone":
        await Form.phone.set()
        await call.message.answer("Введите номер телефона")
    elif call.data.lower() == "dob":
        await Form.dob.set()
        await call.message.answer("Введите дату рождения в формате DD.MM.YYYY")
    elif call.data.lower() == "group":
        await Form.group.set()
        await call.message.answer("Введите группу")
    elif call.data.lower() == "comps":
        buttons = [KeyboardButton(i) for i in comps] + [KeyboardButton("Готово")]
        markup = ReplyKeyboardMarkup()
        add_buttons(markup, buttons)
        user.comp = ""
        await Form.comps.set()
        await call.message.answer("Выберите компетенции (они понадобятся для того чтобы участвовать в проектах)",
                                  reply_markup=markup)

    await call.answer()


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
