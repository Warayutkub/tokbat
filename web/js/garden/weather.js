// Weather without the internet (decision D-1): day and night follow the clock; it rains once every hour for
// 15 minutes, starting at a minute picked from the date and hour, so reopening the app shows the same sky.
export const NIGHT_FROM = 18 * 60 + 30;
export const NIGHT_TO = 6 * 60;
export const RAIN_MIN = 15;

function hash(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

const pad = (n) => String(n).padStart(2, "0");
export function rainStart(d) {
  const key = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}`;
  return hash(key) % (60 - RAIN_MIN + 1); // 0…45
}

/** {night, rain, mode, rainLeft (min), nextRain (min)} for the given time. */
export function skyAt(d = new Date(), rainOn = true) {
  const m = d.getHours() * 60 + d.getMinutes();
  const night = m >= NIGHT_FROM || m < NIGHT_TO;
  const start = rainStart(d);
  const min = d.getMinutes();
  const rain = rainOn && min >= start && min < start + RAIN_MIN;
  let nextRain;
  if (rain) nextRain = 0;
  else if (min < start) nextRain = start - min;
  else {
    const next = new Date(d.getTime() + (60 - min) * 60000);
    nextRain = 60 - min + rainStart(next);
  }
  return { night, rain, mode: night ? (rain ? "night-rain" : "night") : (rain ? "rain" : "day"), rainLeft: rain ? start + RAIN_MIN - min : 0, nextRain };
}
