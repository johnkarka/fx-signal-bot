import os
import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    MessageHandler,
    filters,
)
import yfinance as yf
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, SMAIndicator, MACD
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator

from telegram.ext import Filters
from telegram.ext import MessageHandler, Filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("TG_BOT_TOKEN1") or "YOUR_BOT_TOKEN"  # Prefer env var

# ========== STATES ==========
(
    SELECT_INDICATOR,
    SET_PARAMS,
    SET_OPERATOR,
    SET_COMPARE_TO_TYPE,
    SET_COMPARE_TO_VALUE,
    SET_COMPARE_TO_INDICATOR,
    SET_COMPARE_TO_PARAMS,
    CONFIRM_CONDITION,
) = range(8)

# ========== GLOBALS ==========
strategies = {}
user_data = {}

# ========== Indicator Registry ==========
INDICATORS = {
    "RSI": {
        "class": RSIIndicator,
        "params": {"period": (int, 14, None), "source": (str, "Close", ["Close", "Open", "High", "Low", "HL2"])},
    },
    "EMA": {
        "class": EMAIndicator,
        "params": {"period": (int, 20, None), "source": (str, "Close", ["Close", "Open", "High", "Low", "HL2"])},
    },
    "SMA": {
        "class": SMAIndicator,
        "params": {"period": (int, 50, None), "source": (str, "Close", ["Close", "Open", "High", "Low", "HL2"])},
    },
    "MACD": {
        "class": MACD,
        "params": {
            "fast": (int, 12, None),
            "slow": (int, 26, None),
            "signal": (int, 9, None),
            "source": (str, "Close", ["Close", "Open", "High", "Low", "HL2"]),
        },
    },
    "Stochastic": {
        "class": StochasticOscillator,
        "params": {
            "k_period": (int, 14, None),
            "d_period": (int, 3, None),
            "source": (str, "High", ["Close", "Open", "High", "Low", "HL2"]),
        },
    },
    "BollingerBands": {
        "class": BollingerBands,
        "params": {
            "period": (int, 20, None),
            "stddev": (float, 2, None),
            "source": (str, "Close", ["Close", "Open", "High", "Low", "HL2"]),
        },
    },
    "ATR": {
        "class": AverageTrueRange,
        "params": {"period": (int, 14, None)},
    },
    "OBV": {
        "class": OnBalanceVolumeIndicator,
        "params": {"source": (str, "Close", ["Close", "Open", "High", "Low", "HL2"])},
    },
}

OPERATORS = ["<", ">", "==", "cross_above", "cross_below", "in_zone"]

# ========== HELPERS ==========

def build_indicator_keyboard():
    buttons = [[InlineKeyboardButton(ind, callback_data=ind)] for ind in INDICATORS.keys()]
    return InlineKeyboardMarkup(buttons)

def build_operator_keyboard():
    buttons = [[InlineKeyboardButton(op, callback_data=op)] for op in OPERATORS]
    return InlineKeyboardMarkup(buttons)

def build_source_keyboard(sources):
    buttons = [[InlineKeyboardButton(s, callback_data=s)] for s in sources]
    return InlineKeyboardMarkup(buttons)

def build_yes_no_keyboard():
    buttons = [[InlineKeyboardButton("Yes", callback_data="yes")], [InlineKeyboardButton("No", callback_data="no")]]
    return InlineKeyboardMarkup(buttons)

def get_user_strategy(user_id):
    return strategies.setdefault(user_id, {"logic": "AND", "conditions": []})

# ========== CONVERSATION HANDLERS ==========

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Use /newstrategy to create a new trading strategy.")

def new_strategy(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_data[user_id] = {}
    update.message.reply_text("Choose indicator for your first condition:", reply_markup=build_indicator_keyboard())
    return SELECT_INDICATOR

def select_indicator(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    indicator = query.data
    user_data[user_id]["indicator"] = indicator
    user_data[user_id]["params"] = {}
    params = INDICATORS[indicator]["params"]
    if params:
        user_data[user_id]["param_keys"] = list(params.keys())
        user_data[user_id]["param_index"] = 0
        return ask_param(update, context)
    else:
        query.edit_message_text(f"Selected indicator: {indicator}")
        query.message.reply_text("Choose operator:", reply_markup=build_operator_keyboard())
        return SET_OPERATOR

def ask_param(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    idx = user_data[user_id]["param_index"]
    param_name = user_data[user_id]["param_keys"][idx]
    param_type, default, options = INDICATORS[user_data[user_id]["indicator"]]["params"][param_name]
    prompt = f"Set value for '{param_name}' (default={default}):"
    if options:
        update.callback_query.edit_message_text(prompt, reply_markup=build_source_keyboard(options))
    else:
        update.callback_query.edit_message_text(prompt)
    return SET_PARAMS

def set_param(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    data = query.data
    idx = user_data[user_id]["param_index"]
    param_name = user_data[user_id]["param_keys"][idx]
    param_type, default, options = INDICATORS[user_data[user_id]["indicator"]]["params"][param_name]

    if options:
        val = data
    else:
        try:
            val = param_type(data)
        except Exception:
            val = default

    user_data[user_id]["params"][param_name] = val
    user_data[user_id]["param_index"] += 1

    if user_data[user_id]["param_index"] < len(user_data[user_id]["param_keys"]):
        return ask_param(update, context)
    else:
        query.edit_message_text(f"Parameters set: {json.dumps(user_data[user_id]['params'])}")
        query.message.reply_text("Choose operator:", reply_markup=build_operator_keyboard())
        return SET_OPERATOR

def set_operator(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    operator = query.data
    user_data[user_id]["operator"] = operator

    if operator in ["cross_above", "cross_below"]:
        query.edit_message_text("Select indicator to compare to:")
        query.message.reply_text("Choose compare-to indicator:", reply_markup=build_indicator_keyboard())
        return SET_COMPARE_TO_INDICATOR
    else:
        query.edit_message_text(
            f"Operator set: {operator}\nCompare to value or another indicator?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Value", callback_data="value"),
                        InlineKeyboardButton("Indicator", callback_data="indicator"),
                    ]
                ]
            ),
        )
        return SET_COMPARE_TO_TYPE

def set_compare_to_type(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    choice = query.data
    if choice == "value":
        query.edit_message_text("Send the numeric value to compare to:")
        return SET_COMPARE_TO_VALUE
    else:
        query.edit_message_text("Choose compare-to indicator:")
        query.message.reply_text("Select compare-to indicator:", reply_markup=build_indicator_keyboard())
        return SET_COMPARE_TO_INDICATOR

def set_compare_to_value(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    try:
        val = float(text)
    except ValueError:
        update.message.reply_text("Please send a valid number.")
        return SET_COMPARE_TO_VALUE
    user_data[user_id]["compare_to"] = {"value": val}

    condition = build_condition_summary(user_id)
    update.message.reply_text(
        "Condition added:\n" + condition + "\nAdd more? Use /newstrategy to add another or /done to finish."
    )
    user_strategy = get_user_strategy(user_id)
    user_strategy["conditions"].append(user_data[user_id])
    user_data.pop(user_id, None)
    return ConversationHandler.END

def set_compare_to_indicator(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    indicator = query.data
    user_data[user_id]["compare_to"] = {"indicator": indicator, "params": {}}
    params = INDICATORS[indicator]["params"]
    if params:
        user_data[user_id]["compare_param_keys"] = list(params.keys())
        user_data[user_id]["compare_param_index"] = 0
        query.edit_message_text(f"Set parameters for compare-to indicator '{indicator}':")
        return ask_compare_param(update, context)
    else:
        # No params - done
        condition = build_condition_summary(user_id)
        query.edit_message_text("Condition added:\n" + condition)
        user_strategy = get_user_strategy(user_id)
        user_strategy["conditions"].append(user_data[user_id])
        user_data.pop(user_id, None)
        return ConversationHandler.END

def ask_compare_param(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    idx = user_data[user_id]["compare_param_index"]
    param_name = user_data[user_id]["compare_param_keys"][idx]
    indicator = user_data[user_id]["compare_to"]["indicator"]
    param_type, default, options = INDICATORS[indicator]["params"][param_name]
    prompt = f"Set value for compare-to param '{param_name}' (default={default}):"
    if options:
        update.callback_query.edit_message_text(prompt, reply_markup=build_source_keyboard(options))
    else:
        update.callback_query.edit_message_text(prompt)
    return SET_COMPARE_TO_PARAMS

def set_compare_param(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    data = query.data
    idx = user_data[user_id]["compare_param_index"]
    param_name = user_data[user_id]["compare_param_keys"][idx]
    indicator = user_data[user_id]["compare_to"]["indicator"]
    param_type, default, options = INDICATORS[indicator]["params"][param_name]

    if options:
        val = data
    else:
        try:
            val = param_type(data)
        except Exception:
            val = default

    user_data[user_id]["compare_to"]["params"][param_name] = val
    user_data[user_id]["compare_param_index"] += 1

    if user_data[user_id]["compare_param_index"] < len(user_data[user_id]["compare_param_keys"]):
        return ask_compare_param(update, context)
    else:
        condition = build_condition_summary(user_id)
        query.edit_message_text("Condition added:\n" + condition)
        user_strategy = get_user_strategy(user_id)
        user_strategy["conditions"].append(user_data[user_id])
        user_data.pop(user_id, None)
        return ConversationHandler.END

def build_condition_summary(user_id):
    d = user_data[user_id]
    ind = d["indicator"]
    params = d.get("params", {})
    op = d.get("operator", "?")
    comp = d.get("compare_to")
    pstr = ", ".join(f"{k}={v}" for k, v in params.items())
    cond = f"{ind}({pstr}) {op} "
    if comp is None:
        cond += "???"
    elif "value" in comp:
        cond += str(comp["value"])
    elif "indicator" in comp:
        cind = comp["indicator"]
        cparams = comp.get("params", {})
        cstr = ", ".join(f"{k}={v}" for k, v in cparams.items())
        cond += f"{cind}({cstr})"
    else:
        cond += "???"
    return cond

def done(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    strat = get_user_strategy(user_id)
    if not strat["conditions"]:
        update.message.reply_text("No conditions defined yet. Use /newstrategy to add.")
        return
    text = "Your strategy conditions:\n"
    for i, cond in enumerate(strat["conditions"], 1):
        text += f"{i}. {json.dumps(cond)}\n"
    update.message.reply_text(text)

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Strategy building canceled.")
    user_id = update.message.from_user.id
    user_data.pop(user_id, None)
    return ConversationHandler.END

# ========== MAIN ==========

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newstrategy", new_strategy)],
        states={
            SELECT_INDICATOR: [CallbackQueryHandler(select_indicator)],
            SET_PARAMS: [CallbackQueryHandler(set_param)],
            SET_OPERATOR: [CallbackQueryHandler(set_operator)],
            SET_COMPARE_TO_TYPE: [CallbackQueryHandler(set_compare_to_type)],
            SET_COMPARE_TO_VALUE: [MessageHandler(Filters.text & ~Filters.command, set_compare_to_value)],
            SET_COMPARE_TO_INDICATOR: [CallbackQueryHandler(set_compare_to_indicator)],
            SET_COMPARE_TO_PARAMS: [CallbackQueryHandler(set_compare_param)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("done", done))
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("cancel", cancel))

    updater.start_polling()
    logger.info("Bot started")
    updater.idle()


if __name__ == "__main__":
    main()
