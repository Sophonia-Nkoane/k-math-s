"""Report text formatting helpers for attendance dialog."""

from datetime import datetime
from typing import Any, Dict


def format_daily_report(data: Dict[str, Any]) -> str:
    """Format daily report for display."""
    text = f"""
================================================================================
                        DAILY ATTENDANCE REPORT
================================================================================

Date: {data.get('date', 'N/A')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

--------------------------------------------------------------------------------
                              SUMMARY
--------------------------------------------------------------------------------

Total Records:     {data.get('total_records', 0)}
Present:           {data.get('total_present', 0)}
Absent:            {data.get('total_absent', 0)}
Late:              {data.get('total_late', 0)}
Excused:           {data.get('total_excused', 0)}
Missing Records:   {data.get('missing_count', 0)}

--------------------------------------------------------------------------------
                           BY GRADE
--------------------------------------------------------------------------------
"""

    for grade, stats in data.get('by_grade', {}).items():
        text += f"""
Grade {grade}:
  Total: {stats.get('total', 0)}  |  Present: {stats.get('present', 0)}  |  
  Absent: {stats.get('absent', 0)}  |  Late: {stats.get('late', 0)}
"""

    return text


def format_monthly_report(data: Dict[str, Any]) -> str:
    """Format monthly report for display."""
    text = f"""
================================================================================
                       MONTHLY ATTENDANCE REPORT
================================================================================

Period: {data.get('start_date', 'N/A')} to {data.get('end_date', 'N/A')}
Grade: {data.get('grade', 'All Grades')}
Total Records: {data.get('total_records', 0)}

--------------------------------------------------------------------------------
                          DAILY STATISTICS
--------------------------------------------------------------------------------

Day   | Present | Absent | Late | Excused
------|---------|--------|------|--------
"""

    daily_stats = data.get('daily_statistics', {})
    for day in sorted(daily_stats.keys()):
        stats = daily_stats[day]
        text += (
            f"{day:5} | {stats.get('present', 0):7} | {stats.get('absent', 0):6} | "
            f"{stats.get('late', 0):4} | {stats.get('excused', 0):7}\n"
        )

    return text


def format_trends_report(data: Dict[str, Any]) -> str:
    """Format trends report for display."""
    text = f"""
================================================================================
                       ATTENDANCE TRENDS REPORT
================================================================================

Period: {data.get('period_start', 'N/A')} to {data.get('period_end', 'N/A')}
Grade: {data.get('grade', 'All Grades')}
Total Records: {data.get('total_records', 0)}
Average Attendance Rate: {data.get('average_attendance_rate', 0):.2f}%

--------------------------------------------------------------------------------
                           DAILY DATA
--------------------------------------------------------------------------------

Date         | Present | Absent | Late | Total
-------------|---------|--------|------|-------
"""

    daily_data = data.get('daily_data', {})
    for date_str in sorted(daily_data.keys()):
        stats = daily_data[date_str]
        text += (
            f"{date_str} | {stats.get('present', 0):7} | {stats.get('absent', 0):6} | "
            f"{stats.get('late', 0):4} | {stats.get('total', 0):5}\n"
        )

    return text
