from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


BEIJING = timezone(timedelta(hours=8))


class ServiceCalendar(BaseModel):
    weekdays: list[Literal[0, 1, 2, 3, 4, 5, 6]] = Field(min_length=1, max_length=7)
    opens: time
    closes: time
    closed_dates: set[date] = Field(default_factory=set, max_length=128)

    @model_validator(mode="after")
    def valid_hours(self):
        if self.opens.tzinfo or self.closes.tzinfo or self.opens >= self.closes:
            raise ValueError("服务时段须使用北京时间的同日开关时间")
        return self

    def receipt(self, now: datetime) -> str:
        local = now.astimezone(BEIJING)
        day = local.date()
        in_day = day.weekday() in self.weekdays and day not in self.closed_dates
        if in_day and self.opens <= local.time() < self.closes:
            return "当前处于人工服务时段，处理进度以工单为准。"
        if not (in_day and local.time() < self.opens):
            day += timedelta(days=1)
            while day.weekday() not in self.weekdays or day in self.closed_dates:
                day += timedelta(days=1)
        return f"下一个人工服务时段从 {day.isoformat()} {self.opens:%H:%M}（北京时间）开始，处理进度以工单为准。"
