from source.tradelib import TimeFrame, SessionTimeFrame, Candle
from datetime import date, datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher.filters import Text
from aiogram.types import InputFile
from os import getcwd, remove
import asyncio
import logging
logging.basicConfig(filename="logger.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
idss = [-1002140502131]
groups = {}
for i in idss:
    groups[i] = {'swip': True, 'boss': True, 'day': True, 'sess': True, 'flow':True}
RUSSIAN = {"A": "азитская", "F":"франкфуртская",
            'NY': "нью - йоркская", 'L': "лондонская",
            'HL1': "высоко-ликвидная", 'HL2': "высоко-ликвидная"}
hoursdict = {1: "NY", 10: 'A', 11: "F", 12: "HL1", 14: "HL2", 16: "L"}
bot = Bot("6794894855:AAEhaoDIOwMZhNJjId5rZjvOnWnjzCastMY")
dp = Dispatcher(bot, loop=asyncio.get_event_loop())
skip = timedelta(days=1, hours=6, minutes=18)

@dp.message_handler(commands=['menu', 'start', 'setup', 'main'])
async def telemain(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(types.InlineKeyboardButton(f"свип {'✅' if groups[message.chat.id]['swip'] == True else '❌'}", callback_data="setup_swip"), \
                 types.InlineKeyboardButton(f"босс {'✅' if groups[message.chat.id]['boss'] == True else '❌'}", callback_data="setup_boss"))
    keyboard.add(types.InlineKeyboardButton(f"день {'✅' if groups[message.chat.id]['day'] == True else '❌'}", callback_data="setup_day"), \
                 types.InlineKeyboardButton(f"сессии {'✅' if groups[message.chat.id]['sess'] == True else '❌'}", callback_data="setup_sess"))
    keyboard.add(types.InlineKeyboardButton(f"направление цены {'✅' if groups[message.chat.id]['flow'] == True else '❌'}", callback_data="setup_flow"))
    keyboard.add(types.InlineKeyboardButton("удалить", callback_data='setup_del'))
    await message.answer("Настройки: (✅ - показывает, ❌ - не показывает)", reply_markup=keyboard)   

@dp.callback_query_handler(Text(startswith="setup"))
async def setups(query: types.CallbackQuery):
    global groups
    active = query.data.split("_")[1]
    value = groups[query.message.chat.id]
    await query.message.delete()
    if active != "del":
        value[active] = True if value[active] == False else False
        await telemain(query.message)
    
async def send_all_photoes(tfr: TimeFrame, item: str, text:str, boss = None, fractals=True, imbalance=True):
    tfr.screen(False, item, fractals, imbalance, swip=boss)
    for g in groups:
            if groups[g][item] == True:
                await bot.send_photo(g, InputFile(f"{getcwd()}/images/{item}.png"), \
                            caption=text, disable_notification=True, protect_content=True)
    remove(f"{getcwd()}/images/{item}.png")

async def get_info_day():
    y, m, d = tuple(map(int, (date.today() - timedelta(days = skip.days)).strftime("%Y %m %d").split()))
    last_week = TimeFrame("C:EURUSD", timeType="day", from_= datetime(y, m, d) - timedelta(days=7)\
                          , to=datetime(y, m, d))
    await last_week.do_request()
    pwh, pwl = last_week.candles[0].high, last_week.candles[0].low
    for candle in last_week.candles: 
        if candle.high > pwh:
            pwh = candle.high
        if candle.low < pwl:
            pwl = candle.low
    return {"pdh": last_week.candles[-1].high,
            "pdl": last_week.candles[-1].low,
            "pwl": pwl,
            "pwh": pwh,
            "tfr": last_week}

async def getInfo(queue: asyncio.Queue):
    lastWeek = await get_info_day()
    await queue.put(("WI", lastWeek))
    sessionbool: bool = False
    weekbool: bool = False 
    while True:
        datetimenow = datetime.now() - skip
        if datetimenow.hour == 0 and datetimenow.minute == 0 and datetimenow.second <= 30 and weekbool == False:
            weekbool = True
        elif weekbool == True and datetimenow.second > 30:
            lastWeek = await get_info_day()
            await queue.put(('WI', lastWeek))
            logging.info("Updated weekinfo")
            weekbool = False
        elif datetimenow.hour in hoursdict.keys() and  datetimenow.minute == 0 and datetimenow.second <= 30 and sessionbool == False:
            sessionbool = True
        elif sessionbool == True and datetimenow.second > 30:
            tf = SessionTimeFrame("C:EURUSD", hoursdict[datetimenow.hour], datetimenow.date().strftime('%Y_%m_%d'))
            await tf.do_request()
            tf.find_extremes()
            if tf.countCandles != 0:
                logging.info(f"{hoursdict[datetimenow.hour]} session")
                await queue.put((f'T{hoursdict[datetimenow.hour]}', tf))
            else:
                logging.info(f"{hoursdict[datetimenow.hour]} session pass")
            sessionbool = False
        elif datetimenow.minute % 10 == 0 and datetimenow.second == 0:
            to_ = datetimenow
            from_ = datetimenow - timedelta(hours=1)
            tf = TimeFrame("C:EURUSD", "minute", from_=from_, to=to_, multiplier=10)
            await tf.do_request()
            if tf.countCandles != 0:
                await queue.put((f'B', tf))
        await asyncio.sleep(1)

async def swip(candle: Candle, high: int, low: int, text: str, swip_bool) -> tuple:
    timec = datetime.fromtimestamp(float(candle.time/1000)) 
    b = '-'
    if candle.high > high:
        b = f'L{high}'
    elif candle.low < low:
        b = f'H{low}'
    if b != '-':
        tfr = TimeFrame("C:EURUSD", "minute", timec - timedelta(hours=4), timec, 10)
        await tfr.do_request()
        for fr in list(tfr.get_fractals())[::-1]:
            if b[0] in fr[1]: 
                logging.info("swip")
                if b[0] == 'H':
                    tx = f'была нисшая {b[1:]} в {text}\n сейчас {candle.low}'
                else:
                    tx = f'была высшая {b[1:]} в {text}\n сейчас {candle.high}'
                if swip_bool == 0 or swip_bool == 2:
                    await send_all_photoes(tfr, 'swip', f"Свип! {tx}")
                del tfr
                return fr
    return False
            
async def boss_f(candle: Candle, boss):
    temp = None
    if 'L' in boss[1] and candle.up == False and candle.close < boss[0].low:
        temp = 'd'
    elif 'H' in boss[1] and candle.up == True and candle.close > boss[0].high:
        temp = 'u' 
    if temp != None:
        logging.info("boss")
        timec = datetime.fromtimestamp(float(candle.time/1000))
        tfr = TimeFrame('C:EURUSD', "minute", timec-timedelta(hours=2), timec, 10)
        await tfr.do_request()
        await send_all_photoes(tfr, 'boss', f"БОСС! на по{'вышение' if temp == 'u' else 'нижение'}", boss)
        del tfr
        return temp
    return False



async def analise(queue: asyncio.Queue):
    boss, pel, peh = None, None, None
    pdl, pdh, pwh, pwl, count_boss, swip_count = 0, 0, 0, 0, 0, 0
    sessions = {"A": None, "F": None, 'L': None, "HL1": None, "HL2": None, "NY": None}
    while True:
        if not queue.empty():
            item = await queue.get()
            if item[0] == "WI":
                lastWeek: TimeFrame = item[1]["tfr"]
                pdh, pdl, pwh, pwl = item[1]["pdh"], item[1]["pdl"], item[1]["pwh"], item[1]["pwl"]
                boss = None
                count_boss, swip_count = 0, 0
                await send_all_photoes(lastWeek, 'day', 'информация прошлой недели', fractals=False, imbalance=False)

            elif item[0][0] == "T":
                nSes = item[0][1:]
                sessions[nSes]: SessionTimeFrame = item[1]
                if nSes[0] in 'AFLN':
                    peh, pel = sessions[nSes].highextreme.high, sessions[nSes].lowextreme.low
                await send_all_photoes(sessions[nSes], 'sess', f"{RUSSIAN[nSes]} сессия")
            
            elif item[0] == 'B':
                candle = item[1].candles[-1]
                if type(boss) == tuple:
                    t = await boss_f(candle, boss)
                    boss = boss if t == False else t
                    print(boss)
                elif type(boss) == str:
                    if boss == 'u' and candle.up == True:
                        count_boss += 1
                        print(count_boss)
                    elif boss == 'd' and candle.up == False:
                        count_boss -= 1
                        print(count_boss)
                    if abs(count_boss) > 2:
                        print(count_boss, boss)
                        boss, count_boss = None, 0
                        if count_boss > 2 and boss == 'u':
                            f = lambda x: candle[-1].high < x
                            text = 'возможно цена сейчас растет примерно до '
                            pois = (peh, pdh, pwh)
                        elif count_boss < -2 and boss == 'd':
                            f = lambda x: candle[-1].low > x
                            text = 'возможно цена сейчас падает примерно до '
                            pois = (pel, pdl, pwl)
                        for p in pois:
                            if f(p):
                                text += p
                                break
                        logging.info('flow!')
                        tframe_day = TimeFrame("C:EURUSD", 'minute', datetime.now() - skip - timedelta(hours=12), 
                        datetime.now() - skip, 10)
                        await tframe_day.do_request()
                        send_all_photoes(tframe_day, 'flow', text)
                        swip_count = 0
                checker = list()
                checker.append(await swip(candle, pwh, pwl, "прошлой неделе", swip_count))
                checker.append(await swip(candle, pdh, pdl, 'прошлом дне', swip_count))
                if pel is not None:
                    checker.append(await swip(candle, peh, pel, 'прошлой сессии', swip_count))
                for ch in checker:
                    if ch != False:
                        swip_count+=1
                        if swip_count > 3:
                            swip_count = 0
                        boss = ch
                        count_boss = 0
                        break
                    
        else:
            await asyncio.sleep(1)

if __name__ == "__main__":
    Queue = asyncio.Queue(20)
    dp.loop.create_task(getInfo(Queue))
    dp.loop.create_task(analise(Queue))
    executor.start_polling(dp, skip_updates=True)
