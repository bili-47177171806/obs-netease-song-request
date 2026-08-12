export function getFanLevel(message) {
  const value = Number(message?.fanLevel ?? 0);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

export function canUseCommand(command, message) {
  if (!command?.minFanLevel) return true;
  return getFanLevel(message) >= command.minFanLevel;
}
