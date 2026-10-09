function calendarDate(value: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function shiftDate(value: string, days: number): string {
  const shifted = new Date(`${value}T12:00:00Z`);
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted.toISOString().slice(0, 10);
}

export function todayInTimeZone(timeZone: string): string {
  return calendarDate(new Date(), timeZone);
}

export function daysAgoInTimeZone(days: number, timeZone: string): string {
  return shiftDate(todayInTimeZone(timeZone), -days);
}

export function mondayInTimeZone(timeZone: string): string {
  const today = todayInTimeZone(timeZone);
  const day = new Date(`${today}T12:00:00Z`).getUTCDay() || 7;
  return shiftDate(today, 1 - day);
}
