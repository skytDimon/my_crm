import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from .models import Project, Task, Client, TaskStatus
from .states import AddProjectFSM, AddTaskFSM, AddPaymentFSM, SetHoursFSM
from .keyboards import (
    main_menu_kb,
    projects_list_kb,
    project_details_kb,
    tasks_list_kb,
    task_details_kb,
    confirm_delete_kb,
    cancel_fsm_kb,
    back_to_menu_kb,
)
from .utils import (
    format_currency,
    render_progress_bar,
    task_status_info,
    format_datetime,
)

router = Router()

async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    """Безопасное редактирование сообщения, избегая ошибки 'message is not modified'"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            await callback.message.answer(text, reply_markup=reply_markup)

# =========================================================================
# 1. ГЛАВНОЕ МЕНЮ И ОБЩИЕ КОМАНДЫ
# =========================================================================

def get_welcome_text(admin_name: str | None = None) -> str:
    name_str = f", <b>{admin_name}</b>" if admin_name else ""
    return (
        f"👋 Здравствуйте{name_str}!\n\n"
        "Добро пожаловать в систему управления проектами, задачами и финансами <b>CM-CRM</b>.\n\n"
        "Выберите раздел с помощью кнопок ниже:"
    )

@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_name = message.from_user.first_name if message.from_user else None
    await message.answer(get_welcome_text(user_name), reply_markup=main_menu_kb())

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    user_name = callback.from_user.first_name if callback.from_user else None
    await safe_edit_text(callback, get_welcome_text(user_name), reply_markup=main_menu_kb())

@router.message(Command("cancel"))
@router.callback_query(F.data == "cancel_fsm")
async def process_cancel(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    text = "❌ Действие отменено."
    if isinstance(event, CallbackQuery):
        await event.answer("Отменено")
        await safe_edit_text(event, text + "\n\n" + get_welcome_text(), reply_markup=main_menu_kb())
    else:
        await event.answer(text, reply_markup=main_menu_kb())

@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def show_help(event: Message | CallbackQuery):
    text = (
        "📖 <b>Справка и быстрые команды</b>\n\n"
        "Вы можете управлять проектами как через интерактивные инлайн-кнопки, так и быстрыми текстовыми сообщениями:\n\n"
        "⚡ <b>Быстрый парсер сообщений:</b>\n"
        "• <code>+задача [Имя проекта] [Текст задачи]</code>\n"
        "  <i>Пример:</i> <code>+задача [CM-House] Установить панорамные окна</code>\n\n"
        "• <code>+оплата [Имя проекта] [Сумма]</code>\n"
        "  <i>Пример:</i> <code>+оплата [CM-House] 150000</code>\n\n"
        "🔘 <b>Инлайн-кнопки:</b>\n"
        "• <b>Мои проекты</b> — карточки объектов, прогресс оплаты, управление задачами.\n"
        "• <b>Новый проект</b> — пошаговый мастер создания проекта и клиента.\n"
        "• <b>Статистика</b> — общая финансовая сводка, долги клиентов, статус задач."
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        await safe_edit_text(event, text, reply_markup=back_to_menu_kb())
    else:
        await event.answer(text, reply_markup=back_to_menu_kb())

# =========================================================================
# 2. СТАТИСТИКА И ФИНАНСЫ
# =========================================================================

@router.message(Command("stats"))
@router.callback_query(F.data == "stats")
async def show_statistics(event: Message | CallbackQuery, session: AsyncSession):
    if isinstance(event, CallbackQuery):
        await event.answer()

    # Загружаем проекты
    res_proj = await session.execute(select(Project).options(selectinload(Project.tasks)))
    projects = res_proj.scalars().all()

    total_projects = len(projects)
    active_projects = sum(1 for p in projects if p.is_active)
    closed_projects = total_projects - active_projects

    total_contract_sum = sum(p.total_price for p in projects)
    total_paid_sum = sum(p.paid_amount for p in projects)
    remaining_sum = max(0.0, total_contract_sum - total_paid_sum)

    # Задачи
    all_tasks = [t for p in projects for t in p.tasks]
    total_tasks = len(all_tasks)
    waiting_tasks = sum(1 for t in all_tasks if t.status == TaskStatus.waiting)
    in_progress_tasks = sum(1 for t in all_tasks if t.status == TaskStatus.in_progress)
    done_tasks = sum(1 for t in all_tasks if t.status == TaskStatus.done)
    total_hours = sum((t.hours_spent or 0.0) for t in all_tasks)

    progress = render_progress_bar(total_paid_sum, total_contract_sum, length=12)

    stats_text = (
        "📊 <b>Общая статистика и Финансы</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 <b>Проекты:</b> Всего: <b>{total_projects}</b> (🟢 Активных: {active_projects} | ⚪ Закрытых: {closed_projects})\n\n"
        "💰 <b>Финансовые показатели:</b>\n"
        f"• Общая сумма договоров: <b>{format_currency(total_contract_sum)}</b>\n"
        f"• Всего получено: <b>{format_currency(total_paid_sum)}</b>\n"
        f"• Остаток к получению: <b>{format_currency(remaining_sum)}</b>\n"
        f"• Оплачено: {progress}\n\n"
        "📋 <b>Задачи по всем проектам:</b>\n"
        f"• Всего задач: <b>{total_tasks}</b>\n"
        f"• ⏳ В ожидании: <b>{waiting_tasks}</b>\n"
        f"• 🔄 В работе: <b>{in_progress_tasks}</b>\n"
        f"• ✅ Выполнено: <b>{done_tasks}</b>\n"
        f"• ⏱ Затрачено часов: <b>{total_hours:.1f} ч.</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Перейти к проектам", callback_data="my_projects")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    if isinstance(event, CallbackQuery):
        await safe_edit_text(event, stats_text, reply_markup=kb)
    else:
        await event.answer(stats_text, reply_markup=kb)

# =========================================================================
# 3. СПИСОК ПРОЕКТОВ И КАРТОЧКА ПРОЕКТА
# =========================================================================

@router.message(Command("projects"))
@router.callback_query(F.data == "my_projects")
@router.callback_query(F.data.startswith("proj_filter:"))
async def list_projects(event: Message | CallbackQuery, session: AsyncSession):
    show_all = False
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.data == "proj_filter:all":
            show_all = True
        elif event.data == "proj_filter:active":
            show_all = False

    query = select(Project).options(selectinload(Project.client), selectinload(Project.tasks))
    if not show_all:
        query = query.where(Project.is_active == True)
    query = query.order_by(Project.id.desc())

    result = await session.execute(query)
    projects = result.scalars().all()

    if not projects and not show_all:
        # Проверяем, есть ли вообще какие-то проекты
        count_all = (await session.execute(select(func.count(Project.id)))).scalar() or 0
        if count_all > 0:
            text = "📂 Нет активных проектов. Вы можете посмотреть завершенные проекты:"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚪ Показать все проекты", callback_data="proj_filter:all")],
                [InlineKeyboardButton(text="➕ Создать проект", callback_data="add_project")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        else:
            text = "📂 У вас пока нет созданных проектов.\n\nНажмите кнопку ниже, чтобы создать первый проект!"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
    else:
        title = "📂 <b>Все проекты:</b>" if show_all else "📂 <b>Активные проекты:</b>"
        text = f"{title}\nВыберите проект из списка для подробной информации:"
        kb = projects_list_kb(projects, show_all=show_all)

    if isinstance(event, CallbackQuery):
        await safe_edit_text(event, text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("proj_view:"))
async def view_project_details(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    project_id = int(callback.data.split(":")[1])

    result = await session.execute(
        select(Project)
        .options(selectinload(Project.client), selectinload(Project.tasks))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        await callback.answer("⚠️ Проект не найден или был удален", show_alert=True)
        await list_projects(callback, session)
        return

    remaining = max(0.0, project.total_price - project.paid_amount)
    progress = render_progress_bar(project.paid_amount, project.total_price)
    status_label = "🟢 <b>В работе</b>" if project.is_active else "⚪ <b>Завершен / В архиве</b>"

    tasks = project.tasks or []
    waiting_cnt = sum(1 for t in tasks if t.status == TaskStatus.waiting)
    in_prog_cnt = sum(1 for t in tasks if t.status == TaskStatus.in_progress)
    done_cnt = sum(1 for t in tasks if t.status == TaskStatus.done)

    card_text = (
        f"🏗 Проект: <b>{project.name}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Клиент: <b>{project.client.name if project.client else 'Не указан'}</b>\n"
        f"📌 Статус: {status_label}\n\n"
        "💰 <b>Финансы:</b>\n"
        f"• Стоимость договора: <b>{format_currency(project.total_price)}</b>\n"
        f"• Оплачено: <b>{format_currency(project.paid_amount)}</b>\n"
        f"• Остаток к оплате: <b>{format_currency(remaining)}</b>\n"
        f"• Прогресс оплаты: {progress}\n\n"
        "📋 <b>Задачи ({len(tasks)}):</b>\n"
        f"• ⏳ В ожидании: <b>{waiting_cnt}</b>\n"
        f"• 🔄 В работе: <b>{in_prog_cnt}</b>\n"
        f"• ✅ Выполнено: <b>{done_cnt}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    await safe_edit_text(callback, card_text, reply_markup=project_details_kb(project))

@router.callback_query(F.data.startswith("proj_toggle:"))
async def toggle_project_status(callback: CallbackQuery, session: AsyncSession):
    project_id = int(callback.data.split(":")[1])
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project:
        project.is_active = not project.is_active
        await session.commit()
        status_msg = "Проект возобновлен" if project.is_active else "Проект завершен"
        await callback.answer(status_msg)
        await view_project_details(callback, session)
    else:
        await callback.answer("Проект не найден", show_alert=True)

@router.callback_query(F.data.startswith("proj_del_ask:"))
async def ask_delete_project(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    project_id = int(callback.data.split(":")[1])

    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        await callback.answer("Проект не найден", show_alert=True)
        return

    text = (
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы действительно хотите удалить проект <b>{project.name}</b>?\n"
        f"Все задачи и история оплат по данному проекту будут удалены безвозвратно!"
    )
    await safe_edit_text(callback, text, reply_markup=confirm_delete_kb("proj", project_id, f"proj_view:{project_id}"))

@router.callback_query(F.data.startswith("del_confirm:proj:"))
async def confirm_delete_project(callback: CallbackQuery, session: AsyncSession):
    project_id = int(callback.data.split(":")[2])
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project:
        name = project.name
        await session.delete(project)
        await session.commit()
        await callback.answer(f"Проект «{name}» удален", show_alert=True)
    else:
        await callback.answer("Проект уже удален")

    await list_projects(callback, session)

# =========================================================================
# 4. СПИСОК ЗАДАЧ И УПРАВЛЕНИЕ ЗАДАЧЕЙ
# =========================================================================

@router.callback_query(F.data.startswith("proj_tasks:"))
async def list_project_tasks(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    project_id = int(callback.data.split(":")[1])

    result = await session.execute(
        select(Project)
        .options(selectinload(Project.tasks))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        await callback.answer("Проект не найден", show_alert=True)
        return

    tasks = project.tasks or []
    if not tasks:
        text = (
            f"📋 В проекте <b>{project.name}</b> пока нет задач.\n\n"
            "Вы можете создать задачу прямо сейчас:"
        )
    else:
        text = (
            f"📋 <b>Задачи проекта {project.name}:</b>\n"
            "Нажмите на задачу для просмотра или изменения статуса:"
        )

    await safe_edit_text(callback, text, reply_markup=tasks_list_kb(project_id, tasks))

@router.callback_query(F.data.startswith("task_view:"))
async def view_task_details(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    task_id = int(callback.data.split(":")[1])

    result = await session.execute(
        select(Task).options(selectinload(Task.project)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    emoji, status_title = task_status_info(task.status)
    hours = f"{task.hours_spent:.1f} ч." if task.hours_spent is not None else "не указано"

    text = (
        f"📝 <b>Задача #{task.id}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Проект: <b>{task.project.name}</b>\n"
        f"📌 Статус: {emoji} <b>{status_title}</b>\n\n"
        f"📄 <b>Описание:</b>\n{task.description}\n\n"
        f"⏱ <b>Время:</b>\n"
        f"• Начало работы: <code>{format_datetime(task.started_at)}</code>\n"
        f"• Завершение: <code>{format_datetime(task.ended_at)}</code>\n"
        f"• Затрачено часов: <b>{hours}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Нажмите кнопку ниже для изменения статуса или времени:"
    )

    await safe_edit_text(callback, text, reply_markup=task_details_kb(task))

@router.callback_query(F.data.startswith("task_st:"))
async def change_task_status(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    task_id = int(parts[1])
    new_status_str = parts[2]

    result = await session.execute(
        select(Task).options(selectinload(Task.project)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    new_status = TaskStatus(new_status_str)
    task.status = new_status
    now = datetime.utcnow()

    if new_status == TaskStatus.in_progress:
        if not task.started_at:
            task.started_at = now
        await callback.answer("Статус: В работе 🔄")
    elif new_status == TaskStatus.done:
        if not task.started_at:
            task.started_at = now
        task.ended_at = now
        if task.hours_spent is None and task.started_at:
            diff_hours = (now - task.started_at).total_seconds() / 3600.0
            task.hours_spent = round(max(0.1, diff_hours), 1)
        await callback.answer("Статус: Выполнено! ✅")
    else:
        await callback.answer("Статус: В ожидании ⏳")

    await session.commit()
    await view_task_details(callback, session)

@router.callback_query(F.data.startswith("task_del_ask:"))
async def ask_delete_task(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    task_id = int(callback.data.split(":")[1])

    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    text = f"⚠️ Удалить задачу «<b>{task.description[:40]}...</b>»?"
    await safe_edit_text(callback, text, reply_markup=confirm_delete_kb("task", task_id, f"task_view:{task_id}"))

@router.callback_query(F.data.startswith("del_confirm:task:"))
async def confirm_delete_task(callback: CallbackQuery, session: AsyncSession):
    task_id = int(callback.data.split(":")[2])
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    project_id = None
    if task:
        project_id = task.project_id
        await session.delete(task)
        await session.commit()
        await callback.answer("Задача удалена", show_alert=True)
    else:
        await callback.answer("Задача уже удалена")

    if project_id:
        # Возвращаемся к списку задач
        callback.data = f"proj_tasks:{project_id}"
        await list_project_tasks(callback, session)
    else:
        await list_projects(callback, session)

# =========================================================================
# 5. FSM: СОЗДАНИЕ ПРОЕКТА
# =========================================================================

@router.callback_query(F.data == "add_project")
async def start_add_project(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddProjectFSM.name)
    text = (
        "➕ <b>Создание нового проекта</b>\n\n"
        "Шаг 1 из 3: Введите <b>название проекта</b>\n"
        "<i>Например: CM-House ДубльДом или Модульная баня 6х3</i>"
    )
    await safe_edit_text(callback, text, reply_markup=cancel_fsm_kb())

@router.message(AddProjectFSM.name)
async def process_project_name(message: Message, state: FSMContext, session: AsyncSession):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Название слишком короткое. Введите понятное имя проекта:", reply_markup=cancel_fsm_kb())
        return

    # Проверяем уникальность названия проекта
    existing = await session.execute(select(Project).where(Project.name == name))
    if existing.scalar_one_or_none():
        await message.answer(
            f"⚠️ Проект с названием <b>«{name}»</b> уже существует! Введите другое название:",
            reply_markup=cancel_fsm_kb()
        )
        return

    await state.update_data(project_name=name)
    await state.set_state(AddProjectFSM.client_name)
    await message.answer(
        f"Проект: <b>{name}</b> ✅\n\n"
        "Шаг 2 из 3: Введите <b>имя или компанию клиента</b>:\n"
        "<i>Например: ООО Сан-Донато или Иван Иванов</i>",
        reply_markup=cancel_fsm_kb()
    )

@router.message(AddProjectFSM.client_name)
async def process_project_client(message: Message, state: FSMContext):
    client_name = message.text.strip()
    if not client_name:
        await message.answer("⚠️ Имя клиента не может быть пустым. Введите имя клиента:", reply_markup=cancel_fsm_kb())
        return

    await state.update_data(client_name=client_name)
    await state.set_state(AddProjectFSM.total_price)
    await message.answer(
        f"Клиент: <b>{client_name}</b> ✅\n\n"
        "Шаг 3 из 3: Введите <b>сумму договора</b> (в рублях, только число):\n"
        "<i>Например: 450000 или 1200000</i>",
        reply_markup=cancel_fsm_kb()
    )

@router.message(AddProjectFSM.total_price)
async def process_project_price(message: Message, state: FSMContext, session: AsyncSession):
    raw_text = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        price = float(raw_text)
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "⚠️ Пожалуйста, введите положительное число (например: <code>350000</code>):",
            reply_markup=cancel_fsm_kb()
        )
        return

    data = await state.get_data()
    project_name = data["project_name"]
    client_name = data["client_name"]

    # Ищем или создаем клиента
    res_client = await session.execute(select(Client).where(Client.name == client_name))
    client = res_client.scalar_one_or_none()
    if not client:
        client = Client(name=client_name)
        session.add(client)
        await session.flush()

    new_project = Project(
        client_id=client.id,
        name=project_name,
        total_price=price,
        paid_amount=0.0,
        is_active=True
    )
    session.add(new_project)
    await session.commit()
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Открыть проект", callback_data=f"proj_view:{new_project.id}")],
        [InlineKeyboardButton(text="➕ Добавить еще один", callback_data="add_project")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await message.answer(
        f"🎉 <b>Проект успешно создан!</b>\n\n"
        f"🏗 Проект: <b>{project_name}</b>\n"
        f"👤 Клиент: <b>{client_name}</b>\n"
        f"💰 Сумма договора: <b>{format_currency(price)}</b>\n"
        f"🟢 Статус: В работе",
        reply_markup=kb
    )

# =========================================================================
# 6. FSM: ДОБАВЛЕНИЕ ЗАДАЧИ В ПРОЕКТ
# =========================================================================

@router.callback_query(F.data.startswith("proj_add_task:"))
async def start_add_task(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer()
    project_id = int(callback.data.split(":")[1])

    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        await callback.answer("Проект не найден", show_alert=True)
        return

    await state.update_data(project_id=project_id, project_name=project.name)
    await state.set_state(AddTaskFSM.description)

    text = (
        f"➕ <b>Новая задача для проекта {project.name}</b>\n\n"
        "Отправьте описание задачи сообщением:\n"
        "<i>Например: Заказать фасадные панели и утеплитель</i>"
    )
    await safe_edit_text(callback, text, reply_markup=cancel_fsm_kb())

@router.message(AddTaskFSM.description)
async def process_task_description(message: Message, state: FSMContext, session: AsyncSession):
    desc = message.text.strip()
    if not desc:
        await message.answer("⚠️ Описание не может быть пустым. Введите текст задачи:", reply_markup=cancel_fsm_kb())
        return

    data = await state.get_data()
    project_id = data["project_id"]
    project_name = data.get("project_name", "Проект")

    new_task = Task(
        project_id=project_id,
        description=desc,
        status=TaskStatus.waiting
    )
    session.add(new_task)
    await session.commit()
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список задач проекта", callback_data=f"proj_tasks:{project_id}")],
        [InlineKeyboardButton(text="📁 Карточка проекта", callback_data=f"proj_view:{project_id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await message.answer(
        f"✅ <b>Задача добавлена в проект {project_name}!</b>\n\n"
        f"⏳ <i>{desc}</i>",
        reply_markup=kb
    )

# =========================================================================
# 7. FSM: ВНЕСЕНИЕ ОПЛАТЫ
# =========================================================================

@router.callback_query(F.data.startswith("proj_add_pay:"))
async def start_add_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer()
    project_id = int(callback.data.split(":")[1])

    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        await callback.answer("Проект не найден", show_alert=True)
        return

    await state.update_data(project_id=project_id, project_name=project.name)
    await state.set_state(AddPaymentFSM.amount)

    remaining = max(0.0, project.total_price - project.paid_amount)
    text = (
        f"💳 <b>Внесение оплаты по проекту {project.name}</b>\n\n"
        f"• Стоимость договора: <b>{format_currency(project.total_price)}</b>\n"
        f"• Уже оплачено: <b>{format_currency(project.paid_amount)}</b>\n"
        f"• Остаток долга: <b>{format_currency(remaining)}</b>\n\n"
        "Введите <b>сумму полученной оплаты</b> (в рублях, например: <code>100000</code>):"
    )
    await safe_edit_text(callback, text, reply_markup=cancel_fsm_kb())

@router.message(AddPaymentFSM.amount)
async def process_payment_amount(message: Message, state: FSMContext, session: AsyncSession):
    raw_amount = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        amount = float(raw_amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительную сумму оплаты (например: <code>50000</code>):", reply_markup=cancel_fsm_kb())
        return

    data = await state.get_data()
    project_id = data["project_id"]

    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        await state.clear()
        await message.answer("⚠️ Проект не найден.", reply_markup=main_menu_kb())
        return

    project.paid_amount += amount
    await session.commit()
    await state.clear()

    progress = render_progress_bar(project.paid_amount, project.total_price)
    remaining = max(0.0, project.total_price - project.paid_amount)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Карточка проекта", callback_data=f"proj_view:{project.id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await message.answer(
        f"💰 <b>Оплата {format_currency(amount)} успешно зачислена!</b>\n\n"
        f"🏗 Проект: <b>{project.name}</b>\n"
        f"• Всего оплачено: <b>{format_currency(project.paid_amount)} / {format_currency(project.total_price)}</b>\n"
        f"• Остаток: <b>{format_currency(remaining)}</b>\n"
        f"• Прогресс: {progress}",
        reply_markup=kb
    )

# =========================================================================
# 8. FSM: РУЧНОЕ УКАЗАНИЕ ЧАСОВ ЗАДАЧИ
# =========================================================================

@router.callback_query(F.data.startswith("task_hours:"))
async def start_set_hours(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    task_id = int(callback.data.split(":")[1])
    await state.update_data(task_id=task_id)
    await state.set_state(SetHoursFSM.hours)

    text = "⏱ Введите <b>количество затраченных часов</b> на задачу (например: <code>2.5</code> или <code>5</code>):"
    await safe_edit_text(callback, text, reply_markup=cancel_fsm_kb())

@router.message(SetHoursFSM.hours)
async def process_set_hours(message: Message, state: FSMContext, session: AsyncSession):
    raw_hours = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        hours = float(raw_hours)
        if hours < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите числовое количество часов (например: <code>4</code> или <code>2.5</code>):", reply_markup=cancel_fsm_kb())
        return

    data = await state.get_data()
    task_id = data["task_id"]

    result = await session.execute(
        select(Task).options(selectinload(Task.project)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        await state.clear()
        await message.answer("Задача не найдена.", reply_markup=main_menu_kb())
        return

    task.hours_spent = hours
    await session.commit()
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Открыть задачу", callback_data=f"task_view:{task.id}")],
        [InlineKeyboardButton(text="📋 Все задачи проекта", callback_data=f"proj_tasks:{task.project_id}")]
    ])
    await message.answer(f"⏱ Затраченное время обновлено: <b>{hours:.1f} ч.</b>", reply_markup=kb)

# =========================================================================
# 9. БЫСТРЫЙ ТЕКСТОВЫЙ ПАРСЕР (+задача и +оплата)
# =========================================================================

@router.message(F.text.lower().startswith("+задача"))
async def quick_add_task(message: Message, session: AsyncSession):
    # Поддерживаем варианты:
    # +задача [Имя проекта] [Текст задачи]
    # +задача [Имя проекта] Текст задачи
    # +задача "Имя проекта" Текст задачи
    match = re.match(r'^\+задача\s+(?:\[(.*?)]|"(.*?)"|(\S+))\s+(?:\[(.*?)\]|(.*))$', message.text, re.IGNORECASE)
    
    if not match:
        await message.answer(
            "⚠️ Неверный формат команды.\n\n"
            "Используйте:\n"
            "<code>+задача [Имя проекта] [Текст задачи]</code>\n\n"
            "<i>Пример:</i> <code>+задача [CM-House] Провести электрику</code>"
        )
        return

    # Извлекаем проект и текст задачи
    project_name = (match.group(1) or match.group(2) or match.group(3) or "").strip()
    task_desc = (match.group(4) or match.group(5) or "").strip()

    if not project_name or not task_desc:
        await message.answer("⚠️ Не удалось распознать имя проекта или задачу. Проверьте формат.")
        return

    result = await session.execute(
        select(Project).where(func.lower(Project.name) == project_name.lower())
    )
    project = result.scalar_one_or_none()

    if not project:
        # Предлагаем существующие проекты
        all_proj = (await session.execute(select(Project.name).where(Project.is_active == True))).scalars().all()
        proj_list = "\n".join(f"• <code>{p}</code>" for p in all_proj) if all_proj else "Нет созданных проектов"
        await message.answer(
            f"⚠️ Проект <b>«{project_name}»</b> не найден.\n\n"
            f"<b>Активные проекты:</b>\n{proj_list}\n\n"
            f"Вы можете создать проект по кнопке ниже:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать проект", callback_data="add_project")]
            ])
        )
        return

    new_task = Task(project_id=project.id, description=task_desc, status=TaskStatus.waiting)
    session.add(new_task)
    await session.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Задачи проекта", callback_data=f"proj_tasks:{project.id}")],
        [InlineKeyboardButton(text="📁 Карточка проекта", callback_data=f"proj_view:{project.id}")]
    ])

    await message.answer(
        f"✅ <b>Задача добавлена в проект «{project.name}»!</b>\n\n"
        f"⏳ <i>{task_desc}</i>",
        reply_markup=kb
    )

@router.message(F.text.lower().startswith("+оплата"))
async def quick_add_payment(message: Message, session: AsyncSession):
    # Поддерживаем варианты:
    # +оплата [Имя проекта] [Сумма]
    # +оплата [Имя проекта] 150000
    # +оплата "Имя проекта" 150000
    match = re.match(r'^\+оплата\s+(?:\[(.*?)]|"(.*?)"|(\S+))\s+(?:\[?(\d+(?:[\.,]\d+)?)\]?)$', message.text, re.IGNORECASE)
    
    if not match:
        await message.answer(
            "⚠️ Неверный формат команды.\n\n"
            "Используйте:\n"
            "<code>+оплата [Имя проекта] [Сумма]</code>\n\n"
            "<i>Пример:</i> <code>+оплата [CM-House] 150000</code>"
        )
        return

    project_name = (match.group(1) or match.group(2) or match.group(3) or "").strip()
    raw_amount = match.group(4).replace(",", ".")
    amount = float(raw_amount)

    result = await session.execute(
        select(Project).where(func.lower(Project.name) == project_name.lower())
    )
    project = result.scalar_one_or_none()

    if not project:
        all_proj = (await session.execute(select(Project.name).where(Project.is_active == True))).scalars().all()
        proj_list = "\n".join(f"• <code>{p}</code>" for p in all_proj) if all_proj else "Нет созданных проектов"
        await message.answer(
            f"⚠️ Проект <b>«{project_name}»</b> не найден.\n\n"
            f"<b>Активные проекты:</b>\n{proj_list}"
        )
        return

    project.paid_amount += amount
    await session.commit()

    progress = render_progress_bar(project.paid_amount, project.total_price)
    remaining = max(0.0, project.total_price - project.paid_amount)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Карточка проекта", callback_data=f"proj_view:{project.id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await message.answer(
        f"💰 <b>Оплата {format_currency(amount)} добавлена к проекту «{project.name}»!</b>\n\n"
        f"• Всего оплачено: <b>{format_currency(project.paid_amount)} / {format_currency(project.total_price)}</b>\n"
        f"• Остаток: <b>{format_currency(remaining)}</b>\n"
        f"• Прогресс: {progress}",
        reply_markup=kb
    )
