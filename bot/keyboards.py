"""
Клавиатуры бота
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================
# Неавторизованный пользователь
# ============================================

def no_auth_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для неавторизованных"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Ввести код доступа", callback_data="enter_code")],
        [InlineKeyboardButton("💬 Написать в поддержку", callback_data="contact_support")]
    ])


# ============================================
# Главное меню
# ============================================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню авторизованного пользователя"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Текущий урок", callback_data="current_lesson")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
    ])


# ============================================
# Урок
# ============================================

def lesson_keyboard(has_homework: bool, lesson_id: int) -> InlineKeyboardMarkup:
    """Клавиатура урока"""
    buttons = []

    if has_homework:
        buttons.append([InlineKeyboardButton("📝 Сдать ДЗ", callback_data=f"submit_hw:{lesson_id}")])
    else:
        buttons.append([InlineKeyboardButton("✅ Материал изучен", callback_data=f"mark_done:{lesson_id}")])

    buttons.append([InlineKeyboardButton("💬 Вопрос куратору", callback_data=f"ask_curator:{lesson_id}")])
    buttons.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(buttons)


def back_to_lesson_keyboard(lesson_id: int) -> InlineKeyboardMarkup:
    """Кнопка возврата к уроку"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад к уроку", callback_data=f"view_lesson:{lesson_id}")]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])
