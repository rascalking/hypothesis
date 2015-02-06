from hypothesis.strategytable import StrategyTable
from hypothesis.searchstrategy import SearchStrategy
from datetime import datetime, MINYEAR, MAXYEAR
import hypothesis.params as params
from hypothesis.internal.compat import hrange, text_type
from hypothesis.internal.utils.fixers import equality
from hypothesis.internal.utils.hashitanyway import (
    hash_everything_method, normal_hash
)
from hypothesis.database.converter import (
    ConverterTable, Converter, check_type, check_data_type
)
import pytz


@equality.extend(datetime)
def equal_datetimes(x, y, fuzzy=False):
    return (x.tzinfo == y.tzinfo) and (x == y)

hash_everything_method.extend(datetime)(normal_hash)


def draw_day_for_month(random, year, month):
    while True:
        day = random.randint(1, 31)
        try:
            datetime(
                year=year, month=month, day=day
            )
            return day
        except ValueError as e:
            if e.args[0] != 'day is out of range for month':
                raise e


def maybe_zero_or(random, p, v):
    if random.random() <= p:
        return v
    else:
        return 0


class DatetimeConverter(Converter):

    def to_basic(self, dt):
        check_type(datetime, dt)
        return (
            dt.year, dt.month, dt.day,
            dt.hour, dt.minute, dt.second,
            dt.microsecond,
            dt.tzinfo.zone if dt.tzinfo else None
        )

    def from_basic(self, values):
        check_data_type(list, values)
        for d in values[:-1]:
            check_data_type(int, d)
        timezone = None
        if values[-1] is not None:
            check_data_type(text_type, values[-1])
            timezone = pytz.timezone(values[-1])
        base = datetime(
            year=values[0], month=values[1], day=values[2],
            hour=values[3], minute=values[4], second=values[5],
            microsecond=values[6]
        )
        if timezone is not None:
            base = timezone.localize(base)
        return base


class DatetimeStrategy(SearchStrategy):
    descriptor = datetime
    parameter = params.CompositeParameter(
        p_hour=params.UniformFloatParameter(0, 1),
        p_minute=params.UniformFloatParameter(0, 1),
        p_second=params.UniformFloatParameter(0, 1),
        month=params.NonEmptySubset(list(range(1, 13))),
        naive_chance=params.UniformFloatParameter(0, 0.5),
        utc_chance=params.UniformFloatParameter(0, 1),
        timezones=params.NonEmptySubset(
            list(map(pytz.timezone, pytz.all_timezones))
        )
    )

    def produce(self, random, pv):
        year = random.randint(MINYEAR, MAXYEAR)
        month = random.choice(pv.month)
        base = datetime(
            year=year,
            month=month,
            day=draw_day_for_month(random, year, month),
            hour=maybe_zero_or(random, pv.p_hour, random.randint(0, 23)),
            minute=maybe_zero_or(random, pv.p_minute, random.randint(0, 59)),
            second=maybe_zero_or(random, pv.p_second, random.randint(0, 59)),
            microsecond=random.randint(0, 1000000-1),
        )
        if random.random() <= pv.naive_chance:
            return base
        if random.random() <= pv.utc_chance:
            return pytz.UTC.localize(base)
        return random.choice(pv.timezones).localize(base)

    def simplify(self, value):
        if not value.tzinfo:
            yield pytz.UTC.localize(value)
        elif value.tzinfo != pytz.UTC:
            yield pytz.UTC.normalize(value.astimezone(pytz.UTC))
        s = {value}
        s.add(value.replace(microsecond=0))
        s.add(value.replace(second=0))
        s.add(value.replace(minute=0))
        s.add(value.replace(hour=0))
        s.add(value.replace(day=1))
        s.add(value.replace(month=1))
        s.remove(value)
        for t in s:
            yield t
        year = value.year
        if year == 2000:
            return
        yield value.replace(year=2000)
        # We swallow a bunch of value errors here.
        # These can happen if the original value was february 29 on a
        # leap year and the current year is not a leap year.
        # Note that 2000 was a leap year which is why we didn't need one above.
        mid = (year + 2000) // 2
        if mid != 2000 and mid != year:
            try:
                yield value.replace(year=mid)
            except ValueError:
                pass
        years = hrange(year, 2000, -1 if year > 2000 else 1)
        for year in years:
            if year == mid:
                continue
            try:
                yield value.replace(year)
            except ValueError:
                pass


def load():
    StrategyTable.default().define_specification_for(
        datetime, lambda s, d: DatetimeStrategy()
    )
    ConverterTable.default().define_specification_for(
        datetime, lambda s, d: DatetimeConverter()
    )
