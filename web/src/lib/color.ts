/** CIE L*a*b* (D65) to an sRGB CSS color. Used to paint litmus strips from measured tube color. */
export function labToRgb(l: number, a: number, b: number): [number, number, number] {
  const fy = (l + 16) / 116;
  const fx = fy + a / 500;
  const fz = fy - b / 200;
  const d = 6 / 29;
  const finv = (t: number) => (t > d ? t * t * t : 3 * d * d * (t - 4 / 29));
  const x = 0.95047 * finv(fx);
  const y = 1.0 * finv(fy);
  const z = 1.08883 * finv(fz);
  const lin = [
    3.2404542 * x - 1.5371385 * y - 0.4985314 * z,
    -0.969266 * x + 1.8760108 * y + 0.041556 * z,
    0.0556434 * x - 0.2040259 * y + 1.0572252 * z,
  ];
  const gamma = (c: number) => (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055);
  return lin.map((c) => Math.round(Math.min(1, Math.max(0, gamma(c))) * 255)) as [number, number, number];
}

export function labCss(l: number, a: number, b: number): string {
  const [r, g, bl] = labToRgb(l, a, b);
  return `rgb(${r} ${g} ${bl})`;
}

export interface StripStop {
  t: number; // seconds from run start
  color: string;
}
