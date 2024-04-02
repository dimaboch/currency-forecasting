from matplotlib import pyplot
from datetime import datetime, timedelta
from os import getcwd
from aiohttp import ClientSession
from aiohttp.client_exceptions import ServerDisconnectedError, ClientConnectionError
from numba import prange
from pandas import DataFrame
import asyncio
import logging
logging.basicConfig(filename="logger.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
COMPARE = ["second", "minute", "hour", "day", "week",'month', "quater","year"]

with open(f"{getcwd()}/source/Tokens.txt", 'r') as ft:
    TOKEN = ft.read().split("\n")

n = 0

class Candle:
    def __init__(self, high: float, low: float, open_: float, close: float, time: int, index: int) -> None:
        self.high = high
        self.low = low
        self.open = open_
        self.close = close
        self.time = time
        self.i = index
        self.up: bool = self.open < self.close
    
    
class TimeFrame:
    def __init__(self, name: str, timeType: str, from_: datetime = (datetime.now()-timedelta(days=1)), \
                 to: datetime = datetime.now().strftime("%Y-%m-%d"), multiplier: int = 1, token: list = TOKEN, limit: int = 50000) -> None:
        self.__token = token
        self.__limit = limit
        self.timeType = timeType
        self.name = name
        self.from_ = round(int(from_.timestamp()*1000), -3)
        self.to = round(int(to.timestamp()*1000), -3)
        self.mult = multiplier
        self.candles = list()
        self.countCandles: int = 0
    
    def __add__(self, timeframe):
        to, from_, mult, timeType = None, None, None, None
        if self.name != timeframe.name:
            return None
        timeType = COMPARE[max(COMPARE.index(self.timeType), COMPARE.index(timeframe.timeType))]
        mult = min(self.mult, timeframe.mult)
        if self.from_ < timeframe.from_ or self.to < timeframe.to:
            to = timeframe.to
            from_ = self.from_
        else:
            to = self.to
            from_ = timeframe.from_
        return TimeFrame(self.name, timeType, datetime.fromtimestamp(from_/1000), datetime.fromtimestamp(to/1000), mult)
    
    def __iadd__(self, num):
        if COMPARE.index(self.timeType)+num < len(COMPARE):
            self.timeType = COMPARE[COMPARE.index(self.timeType)+num]
            return self
        logging.error("Problem with time in timframe")
        return None
    
    def __isub__(self, num):
        if COMPARE.index(self.timeType)-num >= 0:
            self.timeType = COMPARE[COMPARE.index(self.timeType)-num]
            return self
        logging.error("Problem with time in timeframe")
        return None
        

    async def do_request(self):
        global n
        try:
            async with ClientSession() as session:
                status = 0
                while status != 200:
                        async with session.get(self.__url_with_token(self.__token[n])) as req:
                            status = req.status
                            info = await req.json()
                            if status != 200:
                                try:
                                    logging.warning(f"TOKEN {n+1} DONT WORK ERROR:{info['error']}")
                                except KeyError:
                                    logging.warning(f"TOKEN {n+1} DONT WORK ERROR:{info['error']}")
                                await asyncio.sleep(1)
                                n += 1
                                if n == len(self.__token):
                                    n = 0
                                continue
                            self.__get_info__candles(info)
                        await session.close()
        except (ServerDisconnectedError, ClientConnectionError):
            logging.error("Disconect internet!")
            self.candles = []
            self.countCandles = 0
            logging.warning(f"NO CANDLES {self.name} {self.from_} {self.to} internet problem")
        
    
    def __url_with_token(self, token):
        self.__requrl = f"https://api.polygon.io/v2/aggs/ticker/{self.name}/range/{self.mult}/{self.timeType}/{self.from_}/{self.to}?adjusted=true&sort=asc&limit={self.__limit}&apiKey="
        return self.__requrl + token
    
    def __get_info__candles(self, req):
        self.countCandles = req["resultsCount"]
        if self.countCandles != 0:
            i = 0
            for candle in req["results"]:
                self.candles.append(Candle(candle['h'], candle['l'], candle['o'], candle['c'], candle['t'], i))
                i += 1
        else:
            logging.info(f"NO CANDLES {self.name} {self.from_} {self.to}")
    
    def get_fractals(self):
        for i in prange(1, len(self.candles) - 1):
            ttype = "NC"
            if self.candles[i].high > self.candles[i+1].high and self.candles[i].high > self.candles[i-1].high:
                ttype = "H"
            if self.candles[i].low < self.candles[i+1].low and self.candles[i].low < self.candles[i-1].low:
                ttype = "L" if ttype == "NC" else "HL" #хуй
            if ttype != "NC":
                yield (self.candles[i], ttype)
    
    def get_imbalance(self):
        low: int
        high: int
        for i in prange(self.countCandles-2, -1, -1):
            if self.candles[i].up == False:
                low = self.candles[i-1].low
                high = self.candles[i+1].high
            else:
                low = self.candles[i+1].low
                high = self.candles[i-1].high
            if low > high:
                yield self.candles[i]
    
    def screen(self, screen=True, save: str = None, fractals=False, imbalance=False, swip=None):
        if self.countCandles != 0:
            time_from = datetime.fromtimestamp(float(self.from_/1000)).strftime("%Y.%m.%d  %H:%M:%S")
            time_to = datetime.fromtimestamp(float(self.to/1000)).strftime("%Y.%m.%d  %H:%M:%S")
            pyplot.title(f"От {time_from} до {time_to}\n{self.name} время 1 свечи: {self.timeType} {self.mult}")
            pyplot.xlabel("time")
            pyplot.ylabel("cost")
            up_color = "green"
            down_color = "red"
            index, high, low, close, open_ = list(), list(), list(), list(), list()
            for candle in self.candles:
                index.append(candle.i)
                high.append(candle.high)
                low.append(candle.low)
                close.append(candle.close)
                open_.append(candle.open)
            dtfr = DataFrame({"open": open_, "close": close, "high": high, "low": low})
            up = dtfr[dtfr.close > dtfr.open]
            down = dtfr[dtfr.close < dtfr.open]
            equal = dtfr[dtfr.close == dtfr.open]
            width1 = 1
            width2 = 0.1
            pyplot.bar(dtfr.index+1, dtfr.high - dtfr.low, width2, bottom=dtfr.low, color="grey")
            pyplot.bar(up.index+1, up.close-up.open, width1, bottom=up.open, color=up_color) 
            pyplot.bar(down.index+1, down.close-down.open, width1, bottom=down.open, color=down_color) 
            pyplot.bar(equal.index+1, 0.0001, width=width1, bottom=equal.open, color='grey')
            highest_cost = max(high)
            if fractals == True:
                time = list()
                fractals = list()
                for candle in self.get_fractals():
                    time.append(candle[0].i+1)
                    if candle[1] == "H":
                        fractals.append(candle[0].close if candle[0].up else candle[0].open)
                    elif candle[1] == "L":
                        fractals.append(candle[0].open if candle[0].up else candle[0].close)
                    elif candle[1] == "HL":
                        time.append(candle[0].i+1)
                        fractals.append(candle[0].close if candle[0].up else candle[0].open)
                        fractals.append(candle[0].open if candle[0].up else candle[0].close)
                pyplot.scatter(time, fractals, color='yellow', s=10)
                pyplot.text(1, highest_cost, "fract", fontsize=6, color="yellow")
            if imbalance == True:
                time = list()
                cost = list()
                for candle in self.get_imbalance():
                    time.append(candle.i+1)
                    cost.append((candle.open+candle.close)/2)
                pyplot.scatter(time, cost, color = "purple", s=30)
                pyplot.text(self.countCandles, highest_cost, "imbal", fontsize=6, color="purple")
            if swip is not None:
                value = swip[0].low if swip[1] == "L" else swip[0].high
                pyplot.plot([swip[0].i , len(dtfr)], [value, value])
            if save != None:
                pyplot.savefig(f'{getcwd()}/images/{save}.png', format="png")
            if screen == True:
                pyplot.show()
            pyplot.close()
        else:
            logging.warn("NO CANDLES to screen")


class SessionTimeFrame(TimeFrame):
    def __init__(self, name: str, typeSession: str, year_mounth_day: str, timeType: str = "minute", multiplier: int = 10, token: str = TOKEN, limit: int = 50000) -> None:
        sessions = {"A": (2, 10),
            "F": (9, 11), 
            "L": (11, 16),
            "NY": (16, 1),
            "HL1": (11, 12),
            "HL2": (13, 14)}      
        hours = sessions[typeSession]  
        self.highextreme = None
        self.lowextreme = None
        year, mounth, day =  tuple(map(int, year_mounth_day.split('_')))
        self.date1 = datetime(year, mounth, day, hours[0], 0, 0)
        if typeSession == "NY":
            self.date2 = datetime(year, mounth, day, hours[1], 0, 0) + timedelta(days=1)
        else:
            self.date2 = datetime(year, mounth, day, hours[1], 0, 0)
        super().__init__(name, timeType, self.date1, self.date2, multiplier, token, limit)
    
    def __maxx_extr(self, candle):
        return candle.high
    
    def __minn_extr(self, candle):
        return candle.low

    def find_extremes(self):
        candles = self.candles
        try:
            self.highextreme = max(candles, key=self.__maxx_extr)
            self.lowextreme = min(candles, key=self.__minn_extr)
        except ValueError:
            self.highextreme = Candle(100, 100, 100, 100, 0, 0)
            self.lowextreme = Candle(0, 0, 0, 0, 0, 0)


