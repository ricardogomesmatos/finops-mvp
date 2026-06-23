"""Testes unitários do DateUtil."""

from __future__ import annotations

from datetime import date, datetime

from billing_common.dates.date_util import DateUtil


def test_get_first_day_of_this_month_with_explicit_date():
    result = DateUtil.get_first_day_of_this_month(date(2024, 4, 17))

    assert result == date(2024, 4, 1)


def test_get_first_day_of_this_month_defaults_to_today():
    result = DateUtil.get_first_day_of_this_month()

    today = date.today()
    assert result == date(today.year, today.month, 1)


def test_get_last_day_of_this_month_regular_month():
    result = DateUtil.get_last_day_of_this_month(date(2024, 4, 1))

    assert result == date(2024, 4, 30)


def test_get_last_day_of_this_month_handles_december_year_rollover():
    result = DateUtil.get_last_day_of_this_month(date(2024, 12, 5))

    assert result == date(2024, 12, 31)


def test_get_last_day_of_this_month_handles_leap_february():
    result = DateUtil.get_last_day_of_this_month(date(2024, 2, 10))

    assert result == date(2024, 2, 29)


def test_get_last_month_from_mid_month_date():
    result = DateUtil.get_last_month(datetime(2024, 4, 17))

    assert result == datetime(2024, 3, 1)


def test_get_last_month_handles_january_year_rollover():
    result = DateUtil.get_last_month(datetime(2024, 1, 15))

    assert result == datetime(2023, 12, 1)


def test_months_in_range_returns_ordered_unique_months():
    result = DateUtil.months_in_range("2024-01-15", "2024-03-10")

    assert result == ["202401", "202402", "202403"]


def test_months_in_range_single_day_within_same_month():
    result = DateUtil.months_in_range("2024-04-01", "2024-04-02")

    assert result == ["202404"]
