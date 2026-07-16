import type { CSSProperties } from "react";

const darkText = "#0f172a";
const lightText = "#f8fafc";

function parseHexColor(value: string): [number, number, number] | null {
  const raw = value.trim().replace(/^#/, "");
  const expanded =
    raw.length === 3
      ? raw
          .split("")
          .map((channel) => channel.repeat(2))
          .join("")
      : raw;
  if (!/^[0-9a-fA-F]{6}$/.test(expanded)) return null;
  return [
    Number.parseInt(expanded.slice(0, 2), 16),
    Number.parseInt(expanded.slice(2, 4), 16),
    Number.parseInt(expanded.slice(4, 6), 16),
  ];
}

function linear(channel: number): number {
  const normalized = channel / 255;
  return normalized <= 0.03928
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

function tagTextColor(color: string): string {
  const rgb = parseHexColor(color);
  if (!rgb) return darkText;
  const luminance =
    0.2126 * linear(rgb[0]) +
    0.7152 * linear(rgb[1]) +
    0.0722 * linear(rgb[2]);
  const contrastWithDark = (luminance + 0.05) / 0.05;
  const contrastWithLight = 1.05 / (luminance + 0.05);
  return contrastWithLight > contrastWithDark ? lightText : darkText;
}

export function tagColorStyle(color: string): CSSProperties {
  return {
    "--tag-color": color,
    "--tag-color-text": tagTextColor(color),
  } as CSSProperties;
}
