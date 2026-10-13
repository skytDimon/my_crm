from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .models import Project, Task, TaskStatus
from .utils import format_currency, task_status_info

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📂 Мои проекты", callback_data="my_projects"),
            InlineKeyboardButton(text="➕ Новый проект", callback_data="add_project")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика и Финансы", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Помощь и команды", callback_data="help")
        ]
    ])

def projects_list_kb(projects: list[Project], show_all: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    
    # Кнопки для каждого проекта
    for proj in projects:
        status_dot = "🟢" if proj.is_active else "⚪"
        paid_text = format_currency(proj.paid_amount)
        text = f"{status_dot} {proj.name} ({paid_text})"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"proj_view:{proj.id}")])
    
    # Кнопка переключения фильтра (активные / все)
    if show_all:
        filter_btn = InlineKeyboardButton(text="🟢 Показать только активные", callback_data="proj_filter:active")
    else:
        filter_btn = InlineKeyboardButton(text="⚪ Показать все (включая закрытые)", callback_data="proj_filter:all")
    
    buttons.append([filter_btn])
    buttons.append([
        InlineKeyboardButton(text="➕ Создать проект", callback_data="add_project"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def project_details_kb(project: Project) -> InlineKeyboardMarkup:
    tasks_count = len(project.tasks) if project.tasks else 0
    toggle_text = "⚪ Завершить проект" if project.is_active else "🟢 Возобновить проект"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"📋 Список задач ({tasks_count})", callback_data=f"proj_tasks:{project.id}")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить задачу", callback_data=f"proj_add_task:{project.id}"),
            InlineKeyboardButton(text="💳 Внести оплату", callback_data=f"proj_add_pay:{project.id}")
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"proj_toggle:{project.id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"proj_del_ask:{project.id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К проектам", callback_data="my_projects"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")
        ]
    ])

def tasks_list_kb(project_id: int, tasks: list[Task]) -> InlineKeyboardMarkup:
    buttons = []
    
    for task in tasks:
        emoji, _ = task_status_info(task.status)
        desc = task.description.strip().replace("\n", " ")
        if len(desc) > 30:
            desc = desc[:27] + "..."
        buttons.append([
            InlineKeyboardButton(text=f"{emoji} {desc}", callback_data=f"task_view:{task.id}")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить задачу", callback_data=f"proj_add_task:{project_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 К проекту", callback_data=f"proj_view:{project_id}"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def task_details_kb(task: Task) -> InlineKeyboardMarkup:
    # Кнопки смены статуса (выделяем галочкой текущий)
    w_mark = "• " if task.status == TaskStatus.waiting else ""
    p_mark = "• " if task.status == TaskStatus.in_progress else ""
    d_mark = "• " if task.status == TaskStatus.done else ""
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{w_mark}⏳ В ожидание", callback_data=f"task_st:{task.id}:waiting"),
            InlineKeyboardButton(text=f"{p_mark}🔄 В работу", callback_data=f"task_st:{task.id}:in_progress"),
            InlineKeyboardButton(text=f"{d_mark}✅ Готово", callback_data=f"task_st:{task.id}:done")
        ],
        [
            InlineKeyboardButton(text="⏱ Указать часы", callback_data=f"task_hours:{task.id}"),
            InlineKeyboardButton(text="🗑 Удалить задачу", callback_data=f"task_del_ask:{task.id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"proj_tasks:{task.project_id}")
        ]
    ])

def confirm_delete_kb(item_type: str, item_id: int, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Да, подтверждаю удаление", callback_data=f"del_confirm:{item_type}:{item_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_cb)
        ]
    ])

def cancel_fsm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")
        ]
    ])

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
